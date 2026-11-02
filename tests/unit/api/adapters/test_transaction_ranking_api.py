"""Tests of ``deweloperuch_mcp.api.adapters.transaction_ranking_api``."""

import copy
import dataclasses
from typing import Any

import pytest
import respx

from deweloperuch_mcp.allowlist import match_api, match_dump
from deweloperuch_mcp.api.adapters.transaction_ranking_api import (
    CITY_RANKING,
    POWIAT_RANKING,
    TransactionRankingApi,
)
from deweloperuch_mcp.api.dto.city_transactions_list_dto import CityTransactionsListDto
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.powiat_map_stats_dto import PowiatMapStatsDto
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError
from deweloperuch_mcp.models.location_ranking import (
    LocationTransactions,
    RankingMarket,
    TransactionPeriod,
)
from deweloperuch_mcp.usecases.ports import TransactionRankingSource
from support.checks.golden import requests_sent
from support.providers.routes.rankings import POWIATS_2026_11_02, captured
from support.providers.samples import body, envelope, request_target
from support.providers.service import BASE

SAMPLES = {CITY_RANKING: "api.city_tx_stats", POWIAT_RANKING: "api.powiat_map_stats"}


WARSZAWA = LocationTransactions(
    name="Warszawa",
    city_slug="warszawa",
    transaction_count=3606,
    price_per_m2=16413.0,
    area_m2=48.8,
    price=780000.0,
)


def serve(service: respx.MockRouter, path: str, **answer: Any) -> respx.Route:
    return service.get(BASE + path).respond(200, **answer)


def test_the_requests_are_the_samples_without_a_query() -> None:
    """Any query string on ``powiat-map-stats`` is a 404 [P 2026-11-01]: none is sent."""
    for path, sample in SAMPLES.items():
        assert envelope(sample)["_request"] == f"GET {path}"
        assert request_target(sample) == path
        assert match_api(path) == path
        assert match_dump(path) is None


def test_the_samples_as_dtos() -> None:
    cities = Dto.validated(CityTransactionsListDto, body("api.city_tx_stats"), CITY_RANKING).root
    powiats = Dto.validated(PowiatMapStatsDto, body("api.powiat_map_stats"), POWIAT_RANKING)

    assert [(city.city, city.city_slug, city.transaction_count) for city in cities] == [
        ("Warszawa", "warszawa", 3606),
        ("Kraków", "krakow", 1492),
        ("Wrocław", "wroclaw", 1443),
    ]
    assert (powiats.periodStart, powiats.periodEndMonth) == ("2025-11-01", "2026-10")
    assert [row.id for row in powiats.rows] == [1, 2, 3]


def test_the_cities_of_the_sample(service: respx.MockRouter, http: HttpClient) -> None:
    serve(service, CITY_RANKING, json=body("api.city_tx_stats"))
    source: TransactionRankingSource = TransactionRankingApi(http)

    places = source.cities()

    assert len(places) == 3
    assert places[0] == WARSZAWA
    assert requests_sent(service) == [f"GET {BASE}{CITY_RANKING} [accept: application/json]"]


def test_the_powiats_of_the_capture_named_from_the_packaged_table(
    service: respx.MockRouter, http: HttpClient
) -> None:
    """tests/fixtures/api/powiat_map_stats_20261102.json: powiat Warszawa (302) on each
    market, Sopot (208) without the primary market."""
    serve(service, POWIAT_RANKING, json=captured(POWIATS_2026_11_02))

    powiats = TransactionRankingApi(http).powiats()

    assert powiats.period == TransactionPeriod(start="2025-11-01", end="2026-10")
    assert powiats.powiats == 380
    assert {market: len(powiats.on(market)) for market in RankingMarket} == {
        RankingMarket.SECONDARY: 364,
        RankingMarket.PRIMARY: 310,
        RankingMarket.ALL: 377,
    }
    warszawa = {
        market: next(p for p in powiats.on(market) if p.powiat_id == 302)
        for market in RankingMarket
    }
    assert warszawa[RankingMarket.SECONDARY] == LocationTransactions(
        name="powiat Warszawa",
        powiat_id=302,
        transaction_count=14563,
        price_per_m2=16395.0,
        area_m2=48.6,
        price=779000.0,
    )
    assert warszawa[RankingMarket.PRIMARY].transaction_count == 17531
    assert warszawa[RankingMarket.ALL].transaction_count == 32095
    assert 208 not in [p.powiat_id for p in powiats.on(RankingMarket.PRIMARY)]
    assert requests_sent(service) == [f"GET {BASE}{POWIAT_RANKING} [accept: application/json]"]


def test_changes_over_time_are_not_read() -> None:
    """[H] T10: the period and base of ``*_change`` are unknown, so the domain has none."""
    assert "transaction_count_change" in envelope("api.city_tx_stats")["response"][0]
    fields = {field.name for field in dataclasses.fields(LocationTransactions)}
    assert not [name for name in fields if "change" in name]


def test_numbers_as_text_and_missing_values_are_tolerated(
    service: respx.MockRouter, http: HttpClient
) -> None:
    row = dict(
        body("api.city_tx_stats")[0],
        transaction_count="3606",
        avg_price_sqm="16413",
        avg_size=None,
        avg_amount="",
        city_slug="",
    )
    serve(service, CITY_RANKING, json=[row])

    (place,) = TransactionRankingApi(http).cities()

    assert place == LocationTransactions(
        name="Warszawa", transaction_count=3606, price_per_m2=16413.0
    )


def broken_cities(**changes: Any) -> list[Any]:
    rows: list[Any] = copy.deepcopy(body("api.city_tx_stats"))
    rows[0].update(changes)
    return rows


def broken_powiats(**changes: Any) -> dict[str, Any]:
    answer: dict[str, Any] = copy.deepcopy(body("api.powiat_map_stats"))
    answer["rows"][0]["wtorny"].update(changes)
    return answer


@pytest.mark.parametrize(
    ("path", "answer"),
    [
        pytest.param(CITY_RANKING, {"json": {"places": []}}, id="cities-not-a-list"),
        pytest.param(
            CITY_RANKING, {"json": broken_cities(transaction_count=None)}, id="cities-count-null"
        ),
        pytest.param(
            CITY_RANKING, {"json": broken_cities(avg_price_sqm="dużo")}, id="cities-price"
        ),
        pytest.param(POWIAT_RANKING, {"json": []}, id="powiats-not-an-object"),
        pytest.param(POWIAT_RANKING, {"json": broken_powiats(n=None)}, id="powiats-count-null"),
        pytest.param(POWIAT_RANKING, {"json": broken_powiats(n=12.5)}, id="powiats-fraction"),
        pytest.param(POWIAT_RANKING, {"json": broken_powiats(m2="dużo")}, id="powiats-price"),
        pytest.param(
            POWIAT_RANKING,
            {"json": dict(body("api.powiat_map_stats"), periodEndMonth="10.2026")},
            id="powiats-period",
        ),
        pytest.param(
            POWIAT_RANKING,
            {"text": "<html></html>", "headers": {"Content-Type": "text/html"}},
            id="powiats-html",
        ),
    ],
)
def test_answers_off_the_contract_are_refused(
    service: respx.MockRouter, http: HttpClient, path: str, answer: dict[str, Any]
) -> None:
    serve(service, path, **answer)
    source = TransactionRankingApi(http)

    with pytest.raises(UnexpectedResponseError) as caught:
        source.cities() if path == CITY_RANKING else source.powiats()

    assert str(caught.value).endswith(SERVICE_CHANGED)
    assert caught.value.detail is not None and path in caught.value.detail


@pytest.mark.parametrize("market", ["wtorny", "pierwotny", "oba"])
def test_a_row_without_a_market_key_is_refused(
    service: respx.MockRouter, http: HttpClient, market: str
) -> None:
    """The three keys are in every row [P 2026-11-01]; a missing one is a changed service,
    not a powiat without that market (which is ``null``)."""
    answer = copy.deepcopy(body("api.powiat_map_stats"))
    del answer["rows"][0][market]
    serve(service, POWIAT_RANKING, json=answer)

    with pytest.raises(UnexpectedResponseError):
        TransactionRankingApi(http).powiats()


def test_a_repeat_within_the_ttl_comes_from_the_cache(
    service: respx.MockRouter, http: HttpClient
) -> None:
    route = serve(service, POWIAT_RANKING, json=body("api.powiat_map_stats"))
    source = TransactionRankingApi(http)

    assert source.powiats() == source.powiats()
    assert route.call_count == 1


@pytest.mark.parametrize(("sent", "slug"), [(" warszawa ", "warszawa"), ("  ", None)])
def test_city_slugs_are_trimmed(
    service: respx.MockRouter, http: HttpClient, sent: str, slug: str | None
) -> None:
    serve(service, CITY_RANKING, json=[dict(body("api.city_tx_stats")[0], city_slug=sent)])

    (place,) = TransactionRankingApi(http).cities()

    assert place.city_slug == slug
