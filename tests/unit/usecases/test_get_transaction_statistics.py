"""Tests of ``deweloperuch_mcp.usecases.get_transaction_statistics``."""

from typing import Any

import pytest

from deweloperuch_mcp.models.errors import (
    InvalidInputError,
    NotFoundError,
    ServiceError,
)
from deweloperuch_mcp.models.government_statistics import PeriodCount
from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionSeries,
)
from deweloperuch_mcp.usecases.get_transaction_statistics import (
    GetTransactionStatistics,
    GetTransactionStatisticsRequest,
)
from support.builders.transactions import WARSZAWA, series
from support.fakes.transactions import FakeTransactionLinks, FakeTransactionSource


def use_case(source: FakeTransactionSource) -> GetTransactionStatistics:
    return GetTransactionStatistics(source, FakeTransactionLinks())


def request(granularity: Granularity, periods: int) -> GetTransactionStatisticsRequest:
    return GetTransactionStatisticsRequest(
        city=WARSZAWA, granularity=granularity, periods=PeriodCount(periods)
    )


def test_the_arguments_default_to_12_months() -> None:
    given = GetTransactionStatisticsRequest.parse(city="warszawa")

    assert (given.city, given.granularity, given.periods) == (
        WARSZAWA,
        Granularity.MONTH,
        PeriodCount(12),
    )


@pytest.mark.parametrize(
    ("kw", "message"),
    [
        (
            {"city": "polska"},
            "city: oczekiwano slug miasta bez polskich znaków, np. warszawa, krakow (nie polska: "
            "cała Polska nie jest obsługiwana); slug podaje search_locations (city_slug); "
            "podano 'polska'.",
        ),
        ({"city": "Kraków", "granularity": "year"}, "city: oczekiwano slug miasta"),
        (
            {"city": "warszawa", "granularity": "year"},
            "granularity musi być jedną z wartości month, quarter, podano 'year'.",
        ),
        (
            {"city": "warszawa", "periods": 0},
            "periods musi być liczbą całkowitą z zakresu 1–1000 (liczba ostatnich okresów), "
            "podano 0.",
        ),
        ({"city": "warszawa", "periods": True}, "periods musi być liczbą całkowitą"),
    ],
)
def test_each_refusal_names_the_parameter_in_the_order_they_are_checked(
    kw: dict[str, Any], message: str
) -> None:
    city = kw.pop("city")
    with pytest.raises(InvalidInputError) as caught:
        GetTransactionStatisticsRequest.parse(city=city, **kw)

    assert str(caught.value).startswith(message)


def test_the_use_case_cuts_the_series_and_says_how_to_see_older_periods() -> None:
    source = FakeTransactionSource(series("2026-05", "2026-06", "2026-07"))

    found = use_case(source).execute(request(Granularity.MONTH, 1))

    assert source.asked == [(WARSZAWA, Granularity.MONTH)]
    assert [item.period for item in found.statistics.periods] == ["2026-07"]
    assert found.hint == (
        "Pokazano ostatnie 1 z 3 okresów (dane od 2026-05); starsze pokaże większa wartość periods."
    )
    assert found.stats_url == "link:warszawa"


def test_the_use_case_has_no_hint_when_nothing_is_cut() -> None:
    found = use_case(FakeTransactionSource(series("2026-07"))).execute(
        request(Granularity.MONTH, 12)
    )

    assert found.hint is None


@pytest.mark.parametrize(
    "found", [series(), NotFoundError("Serwis nie zna żądanych danych (HTTP 404).")]
)
def test_a_city_without_data_points_to_search_locations(
    found: TransactionSeries | Exception,
) -> None:
    with pytest.raises(NotFoundError) as caught:
        use_case(FakeTransactionSource(found)).execute(request(Granularity.MONTH, 12))

    assert str(caught.value) == (
        "Serwis nie ma cen transakcyjnych mieszkań dla miasta 'warszawa'. Sprawdź city_slug w "
        "search_locations (np. warszawa, krakow); statystyki są dla całych miast, nie dla "
        "dzielnic ani ulic."
    )
    assert "search_locations" in str(caught.value)
    assert "HTTP" not in str(caught.value)


def test_a_failure_of_the_service_says_what_it_was_about() -> None:
    failed = ServiceError("Serwis odpowiedział błędem HTTP 503.", 10, detail="/api/x")

    with pytest.raises(ServiceError) as caught:
        use_case(FakeTransactionSource(failed)).execute(request(Granularity.QUARTER, 1))

    assert str(caught.value).startswith("Ceny transakcyjne dla 'warszawa': Serwis odpowiedział")
    assert (caught.value.pause_seconds, caught.value.detail) == (10, "/api/x")
