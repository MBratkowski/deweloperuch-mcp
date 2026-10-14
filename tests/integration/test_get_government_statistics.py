"""``get_government_statistics`` through the session: the real use case and adapters, the
service mocked (respx), no network.
"""

from typing import Any

import pytest
import respx

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.errors import (
    SERVICE_CHANGED,
    InvalidInputError,
    NotFoundError,
    ServiceError,
    UnexpectedResponseError,
)
from support.providers import operations
from support.providers.routes.government_statistics import (
    STATS_PATH,
    UNKNOWN_LOCATION,
    stats_routes,
    unknown_location_route,
)
from support.providers.rsc import (
    STATS_POLSKA,
    raw,
)
from support.providers.service import BASE

NBP_LOCATIONS = (
    "7-miast, 10-miast, 6-miast-bez-warszawy, warszawa, krakow, gdansk, wroclaw, gdynia, "
    "poznan, katowice, opole, szczecin, bialystok, lublin, bydgoszcz, olsztyn, kielce, "
    "rzeszow, lodz, zielona-gora"
)


def test_government_statistics_the_latest_periods_of_a_dataset(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    routes = stats_routes(service)

    result = operations.get_government_statistics(session, "warszawa", "nbp_prices", periods=2)

    assert (result.location_slug, result.location_name, result.dataset) == (
        "warszawa",
        "Warszawa",
        "nbp_prices",
    )
    assert (result.source, result.frequency) == ("NBP", "quarter")
    assert (result.total, result.returned, result.truncated) == (80, 2, True)
    assert result.periods == ("2026-Q1", "2026-Q2")
    assert result.available_from == "2006-Q3"
    assert result.stats_url == BASE + "/statystyki/statystyki-rzadowe/warszawa#nbp"
    assert [(s.series_id, [p.value for p in s.points]) for s in result.series] == [
        ("primary_asking", [18056.0, 18488.0]),
        ("primary_transaction", [16471.0, 16783.0]),
        ("secondary_asking", [18914.0, 19059.0]),
        ("secondary_transaction", [16523.0, 16723.0]),
    ]
    assert routes["warszawa"].call_count == 1


def test_government_statistics_default_to_12_periods(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    stats_routes(service)

    result = operations.get_government_statistics(session, "polska", "average_area")

    assert result.returned == 12 and result.periods[0] == "2015" and result.periods[-1] == "2026"
    assert result.title == (
        "Średnia powierzchnia użytkowa mieszkania lub domu oddanego przez deweloperów"
    )


def test_government_statistics_of_one_location_take_one_request(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """Every dataset of a location is on one page: the next ones come from the cache."""
    routes = stats_routes(service)

    for dataset in ("dwellings_quarterly", "unemployment", "wages", "population"):
        operations.get_government_statistics(session, "polska", dataset)

    assert routes["polska"].call_count == 1


@pytest.mark.parametrize("location", ["polska", "warszawa"])
def test_government_statistics_note_the_incomplete_last_quarter(
    session: bootstrap.Session, service: respx.MockRouter, location: str
) -> None:
    """[P 2026-10-11] both pages: 2026-Q3 is July and August only."""
    stats_routes(service)

    result = operations.get_government_statistics(session, location, "dwellings_quarterly")

    assert result.periods[-1] == "2026-Q3"
    assert result.note == (
        "Ostatni kwartał (2026-Q3) obejmuje tylko 2 z 3 miesięcy (dane miesięczne do "
        "2026-08); nie porównuj go z pełnymi kwartałami."
    )
    monthly = operations.get_government_statistics(session, location, "dwellings_monthly")
    assert monthly.note is None


def test_government_nbp_prices_of_the_whole_country_point_to_cities(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    stats_routes(service)

    with pytest.raises(NotFoundError) as caught:
        operations.get_government_statistics(session, "polska", "nbp_prices")

    assert str(caught.value) == (
        "NBP nie podaje jednej ceny dla całej Polski, tylko dla miast i agregatów. Podaj jedną "
        f"z lokalizacji: {NBP_LOCATIONS}."
    )


def test_government_statistics_of_an_unknown_location_are_not_found(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    unknown_location_route(service)

    with pytest.raises(NotFoundError) as caught:
        operations.get_government_statistics(session, UNKNOWN_LOCATION, "average_area")

    assert str(caught.value) == (
        f"Serwis nie ma statystyk rządowych dla lokalizacji {UNKNOWN_LOCATION!r}. Podaj "
        "polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo slug miasta na "
        "prawach powiatu bez polskich znaków, np. warszawa, krakow. Jeśli nie znasz sluga "
        "miasta, spróbuj city_slug z search_locations (zwykle jest taki sam, ale nie "
        "zawsze, np. dla Jastrzębia-Zdroju użyj jastrzebie). Statystyki są tylko dla miast "
        "na prawach powiatu."
    )
    assert caught.value.detail is not None and "NEXT_HTTP_ERROR_FALLBACK;404" in caught.value.detail


def test_government_statistics_of_a_page_about_another_location_are_unexpected(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """The root page served for an unknown location (a fallback, [H]): never its data."""
    service.get(path=STATS_PATH + "krakow").respond(200, content=raw(STATS_POLSKA))

    with pytest.raises(UnexpectedResponseError) as caught:
        operations.get_government_statistics(session, "krakow", "average_area")

    assert str(caught.value).startswith(
        "Statystyki rządowe dla 'krakow': Serwis zwrócił statystyki innej lokalizacji"
    )
    assert SERVICE_CHANGED in str(caught.value)
    assert "currentSlug" not in str(caught.value)


def test_government_statistics_errors_name_the_location(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    service.get(path=STATS_PATH + "warszawa").respond(503, headers={"Retry-After": "10"})

    with pytest.raises(ServiceError) as caught:
        operations.get_government_statistics(session, "warszawa", "wages")

    assert str(caught.value).startswith(
        "Statystyki rządowe dla 'warszawa': Serwis odpowiedział błędem HTTP 503."
    )
    assert "/statystyki" not in str(caught.value)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"location": "Kraków"}, "location: oczekiwano polska"),
        ({"location": ""}, "location"),
        ({"location": "../api/cities"}, "location"),
        ({"dataset": "prices"}, "dataset musi być jedną z wartości"),
        ({"dataset": ""}, "dataset"),
        ({"periods": 0}, "periods musi być liczbą całkowitą z zakresu 1–1000"),
        ({"periods": 1001}, "periods"),
        ({"periods": True}, "periods"),
        ({"periods": "12"}, "periods"),
    ],
)
def test_government_statistics_reject_bad_input_without_requests(
    session: bootstrap.Session, service: respx.MockRouter, arguments: dict[str, Any], message: str
) -> None:
    arguments = {"location": "warszawa", "dataset": "wages", **arguments}

    with pytest.raises(InvalidInputError, match=message):
        operations.get_government_statistics(session, **arguments)

    assert service.calls.call_count == 0
