"""Tests of ``deweloperuch_mcp.models.transaction_series``."""

import pytest

from deweloperuch_mcp.models.errors import (
    InvalidValueError,
    NotFoundError,
    OneOf,
    SlugText,
    ValueName,
)
from deweloperuch_mcp.models.government_statistics import Frequency, PeriodCount
from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionCity,
    TransactionPeriod,
    TransactionSeries,
)
from support.builders.transactions import WARSZAWA, period, series


@pytest.mark.parametrize(
    ("given", "slug"),
    [("warszawa", "warszawa"), (" Warszawa ", "warszawa"), ("bielsko-biala", "bielsko-biala")],
)
def test_a_transactions_city_is_a_lowercase_slug(given: str, slug: str) -> None:
    assert TransactionCity.parse(given).value == slug


@pytest.mark.parametrize(
    ("given", "repeated"),
    [
        ("polska", "polska"),
        (" Polska ", "polska"),
        ("Kraków", "Kraków"),
        ("a/b", "a/b"),
        ("", ""),
        (None, None),
        (5, 5),
    ],
)
def test_a_transactions_city_is_never_the_whole_country_nor_text(
    given: object, repeated: object
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        TransactionCity.parse(given)

    assert caught.value.value is ValueName.TRANSACTIONS_CITY
    assert caught.value.rule == SlugText()
    assert caught.value.given == repeated


def test_the_whole_country_is_refused_also_when_made_directly() -> None:
    with pytest.raises(InvalidValueError):
        TransactionCity("polska")


@pytest.mark.parametrize(
    ("given", "granularity"),
    [
        ("month", Granularity.MONTH),
        (" quarter ", Granularity.QUARTER),
        (Granularity.QUARTER, Granularity.QUARTER),
    ],
)
def test_granularity_parses_its_values(given: object, granularity: Granularity) -> None:
    assert Granularity.parse(given) is granularity


@pytest.mark.parametrize("given", ["year", "Month", "", None, 1])
def test_granularity_refuses_anything_else(given: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        Granularity.parse(given)

    assert caught.value.value is ValueName.GRANULARITY
    assert caught.value.rule == OneOf(("month", "quarter"))


def test_granularity_labels_its_periods_as_the_government_statistics() -> None:
    assert Granularity.MONTH.frequency is Frequency.MONTH
    assert Granularity.QUARTER.frequency is Frequency.QUARTER


def test_the_latest_periods_are_cut_explicitly() -> None:
    result = series("2026-05", "2026-06", "2026-07").latest(PeriodCount(2))

    assert [item.period for item in result.periods] == ["2026-06", "2026-07"]
    assert (result.total, result.returned, result.truncated) == (3, 2, True)
    assert result.available_from == "2026-05"
    assert (result.city_slug, result.granularity) == ("warszawa", Granularity.MONTH)


def test_asking_for_more_periods_than_there_are_returns_all() -> None:
    result = series("2017-Q1", "2017-Q2", granularity=Granularity.QUARTER).latest(PeriodCount(12))

    assert (result.total, result.returned, result.truncated) == (2, 2, False)


@pytest.mark.parametrize("granularity", list(Granularity))
def test_every_result_says_that_its_latest_periods_are_incomplete(
    granularity: Granularity,
) -> None:
    label = "2026-07" if granularity is Granularity.MONTH else "2026-Q3"
    result = series(label, granularity=granularity).latest(PeriodCount(1))

    assert result.note == granularity.lag_note()
    assert "niepełne" in result.note and "opóźnieniem" in result.note
    word = "miesiące" if granularity is Granularity.MONTH else "kwartały"
    assert result.note.startswith(f"Ostatnie {word} są niepełne")


def test_a_city_without_periods_is_not_found() -> None:
    with pytest.raises(NotFoundError, match="'warszawa'"):
        series().latest(PeriodCount(12))


@pytest.mark.parametrize(
    ("labels", "granularity"),
    [
        (("2026-Q1",), Granularity.MONTH),
        (("2026-01",), Granularity.QUARTER),
        (("2026-13",), Granularity.MONTH),
        (("2026-02", "2026-01"), Granularity.MONTH),
        (("2026-01", "2026-01"), Granularity.MONTH),
    ],
)
def test_a_series_refuses_inconsistent_periods(
    labels: tuple[str, ...], granularity: Granularity
) -> None:
    with pytest.raises(ValueError):
        series(*labels, granularity=granularity)


def test_a_series_refuses_a_negative_count() -> None:
    with pytest.raises(ValueError):
        TransactionSeries(WARSZAWA, Granularity.MONTH, (period("2026-01", -1),))


@pytest.mark.parametrize(
    "item",
    [
        period("2026-05", 0, median_price_per_m2=16000.0),
        period("2026-05", 10, median_price=0.0),
        period("2026-05", 10, average_area_m2=-1.0),
    ],
)
def test_a_series_refuses_zero_measures_and_prices_without_transactions(
    item: TransactionPeriod,
) -> None:
    with pytest.raises(ValueError, match="2026-05"):
        TransactionSeries(WARSZAWA, Granularity.MONTH, (item,))


def test_a_period_without_transactions_and_measures_is_kept() -> None:
    kept = TransactionSeries(WARSZAWA, Granularity.MONTH, (period("2026-05", 0),))

    assert kept.periods[0].measures == (None,) * 6
