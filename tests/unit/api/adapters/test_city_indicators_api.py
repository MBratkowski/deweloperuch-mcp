"""Tests of ``deweloperuch_mcp.api.adapters.city_indicators_api``."""

import copy
from typing import Any

import pytest
import respx

from deweloperuch_mcp.allowlist import match_api, match_dump
from deweloperuch_mcp.api.adapters.city_indicators_api import CITY_INDICATORS, CityIndicatorsApi
from deweloperuch_mcp.api.dto.place_names_dto import PlaceNamesDto
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError
from deweloperuch_mcp.models.indicator_ranking import CityIndicator, Indicator
from deweloperuch_mcp.models.location_ranking import PlaceNames
from deweloperuch_mcp.usecases.ports import CityIndicatorSource
from support.checks.golden import requests_sent
from support.providers.routes.rankings import INDICATORS_2026_11_02, captured
from support.providers.samples import body, envelope, request_target
from support.providers.service import BASE


def serve(service: respx.MockRouter, **answer: Any) -> respx.Route:
    return service.get(BASE + CITY_INDICATORS).respond(200, **answer)


def test_the_request_is_the_samples_without_a_query() -> None:
    assert envelope("api.gov_map_stats")["_request"] == f"GET {CITY_INDICATORS}"
    assert request_target("api.gov_map_stats") == CITY_INDICATORS
    assert match_api(CITY_INDICATORS) == CITY_INDICATORS
    assert match_dump(CITY_INDICATORS) is None


def test_the_sample_as_the_values_of_the_domain(
    service: respx.MockRouter, http: HttpClient
) -> None:
    serve(service, json=body("api.gov_map_stats"))
    source: CityIndicatorSource = CityIndicatorsApi(http)

    wages = source.indicator(Indicator.AVERAGE_WAGE)

    assert (wages.indicator, wages.period, wages.section) == (
        Indicator.AVERAGE_WAGE,
        "2025",
        "gus-wynagrodzenia",
    )
    assert wages.cities == (
        CityIndicator(city_slug="warszawa", name="Warszawa", value=11677.57),
        CityIndicator(city_slug="bialystok", name="Białystok", value=9084.99),
        CityIndicator(city_slug="bydgoszcz", name="Bydgoszcz", value=9207.5),
    )
    assert requests_sent(service) == [f"GET {BASE}{CITY_INDICATORS} [accept: application/json]"]


@pytest.mark.parametrize(
    ("indicator", "period", "section"),
    [
        (Indicator.UNEMPLOYMENT_RATE, "2026-08", "gus-bezrobocie"),
        (Indicator.AVERAGE_WAGE, "2025", "gus-wynagrodzenia"),
        (Indicator.DWELLINGS_COMPLETED, "2026-08", "gus-mieszkania"),
        (Indicator.DWELLINGS_STARTED, "2026-08", "gus-mieszkania"),
        (Indicator.AVERAGE_DWELLING_AREA, "2026-08", "gus-srednia-powierzchnia"),
        (Indicator.NATURAL_INCREASE, "2025", "gus-demografia"),
        (Indicator.NBP_PRICE_PER_M2, "2026-Q2", "nbp"),
    ],
)
def test_every_indicator_of_the_capture_with_its_period_and_section(
    service: respx.MockRouter,
    http: HttpClient,
    indicator: Indicator,
    period: str,
    section: str,
) -> None:
    """One request for the seven: the others come from the cache."""
    route = serve(service, json=captured(INDICATORS_2026_11_02))
    source = CityIndicatorsApi(http)

    found = source.indicator(indicator)
    source.indicator(Indicator.NBP_PRICE_PER_M2)

    assert (found.period, found.section, len(found.cities)) == (period, section, 66)
    missing = sum(city.value is None for city in found.cities)
    assert missing == (49 if indicator is Indicator.NBP_PRICE_PER_M2 else 0)
    assert route.call_count == 1


def test_every_city_of_the_capture_is_named() -> None:
    """The packaged table names each of the 66 cities of 2026-11-02 (a missing one would be
    shown by its slug)."""
    slugs = {row["slug"] for row in captured(INDICATORS_2026_11_02)["rows"]}
    table = PlaceNamesDto.packaged().to_model()

    assert len(slugs) == 66
    assert {slug for slug in slugs if PlaceNames.fold(slug) not in table.cities} == set()


def changed(**changes: Any) -> dict[str, Any]:
    answer: dict[str, Any] = copy.deepcopy(body("api.gov_map_stats"))
    answer.update(changes)
    return answer


def test_a_missing_value_or_key_is_no_value(service: respx.MockRouter, http: HttpClient) -> None:
    """The NBP price is ``null`` for 49 cities [P 2026-11-01]; an absent key reads the same."""
    answer = changed()
    answer["rows"][0]["values"]["nbpCena"] = None
    del answer["rows"][1]["values"]["nbpCena"]
    serve(service, json=answer)

    values = CityIndicatorsApi(http).indicator(Indicator.NBP_PRICE_PER_M2)

    assert [city.value for city in values.cities] == [None, None, 8342.0]


def test_an_unknown_key_of_any_type_is_ignored(service: respx.MockRouter, http: HttpClient) -> None:
    """[W] the service may add an indicator: no row had another key on 2026-11-02, so this is
    a test of the rule on hand-edited real rows (the capture's Warszawa, an extra key in
    ``values`` and in ``asOf``, of types no indicator has)."""
    answer = captured(INDICATORS_2026_11_02)
    answer["asOf"]["nowyWskaznik"] = {"od": 2026}
    answer["rows"][0]["values"]["nowyWskaznik"] = ["dużo", None]
    answer["rows"][1]["values"]["inny"] = "brak"
    serve(service, json=answer)

    values = CityIndicatorsApi(http).indicator(Indicator.UNEMPLOYMENT_RATE)

    assert (values.period, len(values.cities)) == ("2026-08", 66)
    assert values.cities[0] == CityIndicator(city_slug="warszawa", name="Warszawa", value=1.6)


@pytest.mark.parametrize(
    ("as_of", "period"),
    [("08.2026", "2026-08"), (" Q2 2026 ", "2026-Q2"), ("2025", "2025"), ("sierpień", None)],
)
def test_the_period_is_read_into_a_label(
    service: respx.MockRouter, http: HttpClient, as_of: str, period: str | None
) -> None:
    answer = changed()
    answer["asOf"]["bezrobocie"] = as_of
    serve(service, json=answer)

    assert CityIndicatorsApi(http).indicator(Indicator.UNEMPLOYMENT_RATE).period == period


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param({"json": []}, id="not-an-object"),
        pytest.param({"json": changed(rows=None)}, id="rows-null"),
        pytest.param({"json": changed(asOf={})}, id="period-missing"),
        pytest.param(
            {"json": changed(rows=[{"slug": "warszawa", "values": {"bezrobocie": "dużo"}}])},
            id="value-not-a-number",
        ),
        pytest.param(
            {"text": "<html></html>", "headers": {"Content-Type": "text/html"}}, id="html"
        ),
    ],
)
def test_answers_off_the_contract_are_refused(
    service: respx.MockRouter, http: HttpClient, answer: dict[str, Any]
) -> None:
    serve(service, **answer)

    with pytest.raises(UnexpectedResponseError) as caught:
        CityIndicatorsApi(http).indicator(Indicator.UNEMPLOYMENT_RATE)

    assert str(caught.value).endswith(SERVICE_CHANGED)
    assert caught.value.detail is not None and CITY_INDICATORS in caught.value.detail
