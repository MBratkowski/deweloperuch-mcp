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
from deweloperuch_mcp.api.dto.powiat_transactions_list_dto import PowiatTransactionsListDto
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError
from deweloperuch_mcp.models.location_ranking import LocationTransactions, RankingLevel
from deweloperuch_mcp.usecases.ports import TransactionRankingSource
from support.checks.golden import requests_sent
from support.providers.samples import body, envelope, request_target
from support.providers.service import BASE

SAMPLES = {RankingLevel.CITY: "api.city_tx_stats", RankingLevel.POWIAT: "api.powiat_stats"}


PATHS = {RankingLevel.CITY: CITY_RANKING, RankingLevel.POWIAT: POWIAT_RANKING}


WARSZAWA = LocationTransactions(
    name="Warszawa",
    city_slug="warszawa",
    transaction_count=3606,
    price_per_m2=16413.0,
    area_m2=48.8,
    price=780000.0,
)


POWIAT_WARSZAWA = LocationTransactions(
    name="powiat Warszawa",
    powiat_id=302,
    transaction_count=351314,
    price_per_m2=16367.0,
    area_m2=48.6,
    price=780000.0,
)


def serve(service: respx.MockRouter, level: RankingLevel, **answer: Any) -> respx.Route:
    return service.get(BASE + PATHS[level]).respond(200, **answer)


def broken(sample: str, **changes: Any) -> list[Any]:
    rows: list[Any] = copy.deepcopy(body(sample))
    rows[0].update(changes)
    return rows


def test_the_requests_are_the_samples_without_a_query() -> None:
    for level, sample in SAMPLES.items():
        assert envelope(sample)["_request"] == f"GET {PATHS[level]}"
        assert request_target(sample) == PATHS[level]
        assert match_api(PATHS[level]) == PATHS[level]
        assert match_dump(PATHS[level]) is None


def test_the_samples_as_dtos() -> None:
    cities = Dto.validated(CityTransactionsListDto, body("api.city_tx_stats"), CITY_RANKING).root
    powiats = Dto.validated(
        PowiatTransactionsListDto, body("api.powiat_stats"), POWIAT_RANKING
    ).root

    assert [(city.city, city.city_slug, city.transaction_count) for city in cities] == [
        ("Warszawa", "warszawa", 3606),
        ("Kraków", "krakow", 1492),
        ("Wrocław", "wroclaw", 1443),
    ]
    assert [(powiat.powiat_rcn_id, powiat.nazwa) for powiat in powiats] == [
        (302, "powiat Warszawa"),
        (14, "powiat Kraków"),
        (33, "powiat Wrocław"),
    ]


@pytest.mark.parametrize(
    ("level", "first", "count"),
    [(RankingLevel.CITY, WARSZAWA, 3), (RankingLevel.POWIAT, POWIAT_WARSZAWA, 3)],
)
def test_the_samples_as_the_places_of_the_domain(
    service: respx.MockRouter,
    http: HttpClient,
    level: RankingLevel,
    first: LocationTransactions,
    count: int,
) -> None:
    serve(service, level, json=body(SAMPLES[level]))
    source: TransactionRankingSource = TransactionRankingApi(http)

    places = source.locations(level)

    assert len(places) == count
    assert places[0] == first
    assert requests_sent(service) == [f"GET {BASE}{PATHS[level]} [accept: application/json]"]


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
    serve(service, RankingLevel.CITY, json=[row])

    (place,) = TransactionRankingApi(http).locations(RankingLevel.CITY)

    assert place == LocationTransactions(
        name="Warszawa", transaction_count=3606, price_per_m2=16413.0
    )


@pytest.mark.parametrize("level", list(RankingLevel))
@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(lambda sample: {"json": {"places": body(sample)}}, id="not-a-list"),
        pytest.param(
            lambda sample: {"json": broken(sample, transaction_count=None)}, id="count-null"
        ),
        pytest.param(
            lambda sample: {"json": broken(sample, transaction_count=12.5)}, id="count-fraction"
        ),
        pytest.param(lambda sample: {"json": broken(sample, avg_price_sqm="dużo")}, id="price"),
        pytest.param(
            lambda sample: {"text": "<html></html>", "headers": {"Content-Type": "text/html"}},
            id="html",
        ),
    ],
)
def test_answers_off_the_contract_are_refused(
    service: respx.MockRouter, http: HttpClient, level: RankingLevel, answer: Any
) -> None:
    serve(service, level, **answer(SAMPLES[level]))

    with pytest.raises(UnexpectedResponseError) as caught:
        TransactionRankingApi(http).locations(level)

    assert str(caught.value).endswith(SERVICE_CHANGED)
    assert caught.value.detail is not None and PATHS[level] in caught.value.detail


def test_a_row_without_its_count_is_refused(service: respx.MockRouter, http: HttpClient) -> None:
    rows = broken("api.powiat_stats")
    del rows[0]["transaction_count"]
    serve(service, RankingLevel.POWIAT, json=rows)

    with pytest.raises(UnexpectedResponseError):
        TransactionRankingApi(http).locations(RankingLevel.POWIAT)


def test_a_repeat_within_the_ttl_comes_from_the_cache(
    service: respx.MockRouter, http: HttpClient
) -> None:
    route = serve(service, RankingLevel.CITY, json=body("api.city_tx_stats"))
    source = TransactionRankingApi(http)

    assert source.locations(RankingLevel.CITY) == source.locations(RankingLevel.CITY)
    assert route.call_count == 1


@pytest.mark.parametrize(("sent", "slug"), [(" warszawa ", "warszawa"), ("  ", None)])
def test_city_slugs_are_trimmed(
    service: respx.MockRouter, http: HttpClient, sent: str, slug: str | None
) -> None:
    serve(service, RankingLevel.CITY, json=[dict(body("api.city_tx_stats")[0], city_slug=sent)])

    (place,) = TransactionRankingApi(http).locations(RankingLevel.CITY)

    assert place.city_slug == slug
