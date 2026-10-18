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
from support.builders.transactions import (
    WARSZAWA,
    WARSZAWA_LAST_7_QUARTERS,
    WARSZAWA_LAST_16_MONTHS,
    counted,
    series,
)
from support.fakes.transactions import FakeTransactionLinks, FakeTransactionSource

WARSZAWA_TAIL = counted("2025-04", *WARSZAWA_LAST_16_MONTHS)
"""2025-04..2026-07 of tests/fixtures/api/monthly_tx_warszawa_20261015.json: 2026-05,
2026-06 and 2026-07 incomplete, 2026-04 the last complete month."""

LAST_COMPLETE = (
    "Ostatni okres ze zwykłą liczbą transakcji: 2026-04 (jego dane też mogą się jeszcze zmienić)."
)


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


def test_the_hint_names_the_incomplete_periods_and_the_last_complete_one() -> None:
    found = use_case(FakeTransactionSource(WARSZAWA_TAIL)).execute(request(Granularity.MONTH, 16))

    assert found.statistics.last_complete_period == "2026-04"
    assert found.latest_periods_hint == (
        "Okresy 2026-05, 2026-06 i 2026-07 mają mniej niż połowę zwykłej liczby transakcji "
        "(dane RCN jeszcze niepełne): nie wyciągaj wniosków z ich cen ani liczby transakcji. "
        + LAST_COMPLETE
    )
    assert found.hint == found.latest_periods_hint


def test_a_cut_result_with_incomplete_periods_says_both() -> None:
    found = use_case(FakeTransactionSource(WARSZAWA_TAIL)).execute(request(Granularity.MONTH, 12))

    assert found.hint == (
        "Pokazano ostatnie 12 z 16 okresów (dane od 2025-04); starsze pokaże większa wartość "
        f"periods. {found.latest_periods_hint}"
    )


@pytest.mark.parametrize(
    ("periods", "named"),
    [
        (
            1,
            "Okres 2026-07 ma mniej niż połowę zwykłej liczby transakcji (dane RCN jeszcze "
            "niepełne): nie wyciągaj wniosków z jego cen ani liczby transakcji.",
        ),
        (
            2,
            "Okresy 2026-06 i 2026-07 mają mniej niż połowę zwykłej liczby transakcji (dane "
            "RCN jeszcze niepełne): nie wyciągaj wniosków z ich cen ani liczby transakcji.",
        ),
    ],
)
def test_the_hint_names_only_the_incomplete_periods_shown(periods: int, named: str) -> None:
    found = use_case(FakeTransactionSource(WARSZAWA_TAIL)).execute(
        request(Granularity.MONTH, periods)
    )

    assert found.latest_periods_hint == f"{named} {LAST_COMPLETE}"


def test_without_a_complete_period_the_hint_does_not_name_one() -> None:
    """2026-02..2026-06 of the fixture alone: 2026-05 and 2026-06 are incomplete, and
    there is too little history to judge any period complete."""
    source = FakeTransactionSource(counted("2026-02", 1180, 1390, 987, 22, 0))

    found = use_case(source).execute(request(Granularity.MONTH, 12))

    assert found.statistics.last_complete_period is None
    assert found.hint == (
        "Okresy 2026-05 i 2026-06 mają mniej niż połowę zwykłej liczby transakcji (dane RCN "
        "jeszcze niepełne): nie wyciągaj wniosków z ich cen ani liczby transakcji."
    )


def test_quarters_are_named_as_periods_too() -> None:
    quarters = counted("2025-Q1", *WARSZAWA_LAST_7_QUARTERS, granularity=Granularity.QUARTER)

    found = use_case(FakeTransactionSource(quarters)).execute(request(Granularity.QUARTER, 12))

    assert found.latest_periods_hint == (
        "Okresy 2026-Q2 i 2026-Q3 mają mniej niż połowę zwykłej liczby transakcji (dane RCN "
        "jeszcze niepełne): nie wyciągaj wniosków z ich cen ani liczby transakcji. Ostatni "
        "okres ze zwykłą liczbą transakcji: 2026-Q1 (jego dane też mogą się jeszcze zmienić)."
    )


def test_without_incomplete_periods_there_is_nothing_to_say_about_them() -> None:
    """The fixture's months up to 2026-04: none is incomplete."""
    source = FakeTransactionSource(counted("2025-04", *WARSZAWA_LAST_16_MONTHS[:-3]))

    found = use_case(source).execute(request(Granularity.MONTH, 13))

    assert found.statistics.last_complete_period == "2026-04"
    assert (found.latest_periods_hint, found.hint) == (None, None)


def test_too_few_transactions_to_judge_are_a_hint_of_their_own() -> None:
    """2024-12..2025-12 of tests/fixtures/api/monthly_tx_karpacz_20261016.json (a median
    of 1 transaction a month), cut to the last 12."""
    source = FakeTransactionSource(counted("2024-12", 3, 0, 1, 3, 2, 7, 0, 1, 2, 2, 1, 7, 1))

    found = use_case(source).execute(request(Granularity.MONTH, 12))

    assert found.statistics.last_complete_period is None
    assert found.hint == (
        "Pokazano ostatnie 12 z 13 okresów (dane od 2024-12); starsze pokaże większa wartość "
        "periods. Transakcji jest za mało, by ocenić, które najnowsze okresy są niepełne: "
        "każdy może jeszcze urosnąć, a ceny z kilku transakcji są przypadkowe; nie wyciągaj "
        "z nich trendu."
    )


def test_a_big_city_with_a_year_of_empty_months_names_them_all() -> None:
    """Made-up counts (a rule test): two years of 1200 transactions a month, then twelve
    months without any; the hint names them, not too few transactions."""
    source = FakeTransactionSource(counted("2023-01", *([1200] * 24), *([0] * 12)))

    found = use_case(source).execute(request(Granularity.MONTH, 12))

    assert found.latest_periods_hint == (
        "Okresy 2025-01, 2025-02, 2025-03, 2025-04, 2025-05, 2025-06, 2025-07, 2025-08, "
        "2025-09, 2025-10, 2025-11 i 2025-12 mają mniej niż połowę zwykłej liczby transakcji "
        "(dane RCN jeszcze niepełne): nie wyciągaj wniosków z ich cen ani liczby transakcji. "
        "Ostatni okres ze zwykłą liczbą transakcji: 2024-12 (jego dane też mogą się jeszcze "
        "zmienić)."
    )
    assert found.hint is not None and "za mało" not in found.hint
