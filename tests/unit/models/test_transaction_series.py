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
    INCOMPLETE_SHARE,
    MIN_REFERENCE_PERIODS,
    MIN_USUAL_TRANSACTIONS,
    Granularity,
    TransactionCity,
    TransactionPeriod,
    TransactionSeries,
    TransactionStatistics,
)
from support.builders.transactions import (
    WARSZAWA,
    WARSZAWA_LAST_7_QUARTERS,
    WARSZAWA_LAST_16_MONTHS,
    counted,
    period,
    series,
)


def flagged(result: TransactionStatistics) -> list[str]:
    return [item.period for item in result.periods if item.incomplete]


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
    assert result.note.endswith("Nie porównuj ich z okresami o zwykłej liczbie transakcji.")


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


# --- incomplete periods at the end of a series ---------------------------------------------


def test_the_rule_of_incomplete_periods_is_named() -> None:
    assert (INCOMPLETE_SHARE, MIN_REFERENCE_PERIODS, MIN_USUAL_TRANSACTIONS) == (0.5, 3, 10)
    assert Granularity.MONTH.reference_periods == 12
    assert Granularity.QUARTER.reference_periods == 4


def test_the_real_tail_of_warsaw_has_three_incomplete_months() -> None:
    """tests/fixtures/api/monthly_tx_warszawa_20261015.json: 2026-05 (22), 2026-06 (0)
    and 2026-07 (35) are below half of the median of the year before them (1178);
    2026-04 (987) is usual."""
    result = counted("2025-04", *WARSZAWA_LAST_16_MONTHS).latest(PeriodCount(12))

    assert flagged(result) == ["2026-05", "2026-06", "2026-07"]
    assert result.last_complete_period == "2026-04"
    assert [item.incomplete for item in result.periods[:-3]] == [False] * 9
    assert result.few_transactions is False


def test_periods_are_judged_on_the_whole_series_before_the_cut() -> None:
    """One period shown still has the year before it as its reference."""
    result = counted("2025-04", *WARSZAWA_LAST_16_MONTHS).latest(PeriodCount(1))

    assert [(item.period, item.incomplete) for item in result.periods] == [("2026-07", True)]
    assert result.last_complete_period == "2026-04"


def test_every_shown_period_may_be_incomplete_with_the_last_complete_one_older() -> None:
    result = counted("2025-04", *WARSZAWA_LAST_16_MONTHS).latest(PeriodCount(2))

    assert flagged(result) == ["2026-06", "2026-07"]
    assert result.last_complete_period == "2026-04"


def test_the_series_is_not_changed_by_judging_it() -> None:
    whole = counted("2025-04", *WARSZAWA_LAST_16_MONTHS)

    whole.latest(PeriodCount(12))

    assert not any(item.incomplete for item in whole.periods)


def test_a_series_without_a_short_tail_flags_nothing() -> None:
    """The fixture's months up to 2026-04: its newest month is the last complete one."""
    result = counted("2025-04", *WARSZAWA_LAST_16_MONTHS[:-3]).latest(PeriodCount(12))

    assert flagged(result) == []
    assert result.last_complete_period == "2026-04"


def test_a_dip_inside_the_series_is_never_flagged() -> None:
    """The fixture's months up to 2026-04 with 2025-10 edited down to 22 (a rule test):
    only a run at the end is incomplete, and the newest month is usual."""
    counts = list(WARSZAWA_LAST_16_MONTHS[:-3])
    counts[6] = 22

    result = counted("2025-04", *counts).latest(PeriodCount(12))

    assert flagged(result) == []
    assert result.last_complete_period == "2026-04"


def test_a_low_period_followed_by_a_usual_one_is_not_in_the_tail() -> None:
    """The fixture's tail with 2026-06 edited to 1180 (a rule test): 2026-07 is
    incomplete, 2026-06 is not, so 2026-05 (22) stays unflagged before it."""
    counts = list(WARSZAWA_LAST_16_MONTHS)
    counts[-2] = 1180

    result = counted("2025-04", *counts).latest(PeriodCount(12))

    assert flagged(result) == ["2026-07"]
    assert result.last_complete_period == "2026-06"


@pytest.mark.parametrize(("newest", "incomplete"), [(589, False), (588, True)])
def test_a_period_is_incomplete_below_half_the_median_of_the_year_before(
    newest: int, incomplete: bool
) -> None:
    """The year before 2026-04 in the fixture has the median 1178; half of it is 589 (a
    rule test: the count of 2026-04 edited). Below it, 2026-03 is the last complete."""
    counts = [*WARSZAWA_LAST_16_MONTHS[:12], newest]

    result = counted("2025-04", *counts).latest(PeriodCount(1))

    assert result.periods[0].incomplete is incomplete
    assert result.last_complete_period == ("2026-03" if incomplete else "2026-04")


def test_the_shape_of_2026_10_13_flags_april_too() -> None:
    """docs/discovery/endpoints.md: on 2026-10-13 Warsaw's 2026-04 had 29 transactions,
    2026-05 and 2026-06 none, and 2026-07 had 2 on 2026-10-09 (the fixture's tail edited
    to those counts)."""
    counts = [*WARSZAWA_LAST_16_MONTHS[:-4], 29, 0, 0, 2]

    result = counted("2025-04", *counts).latest(PeriodCount(12))

    assert flagged(result) == ["2026-04", "2026-05", "2026-06", "2026-07"]
    assert result.last_complete_period == "2026-03"


@pytest.mark.parametrize(("april", "first", "last"), [(987, 5, "2026-04"), (29, 4, "2026-03")])
def test_a_long_tail_is_judged_against_the_year_before_it(
    april: int, first: int, last: str
) -> None:
    """The fixture's months (2026-04 as sent, or as on 2026-10-13), then five made-up low
    months (10..30, a rule test): the newest of them are not below half of their own
    year, full of low months, but the whole run of 8 or 9 months is below half of the
    year before it."""
    counts = [*WARSZAWA_LAST_16_MONTHS[:-4], april, 22, 0, 35, 10, 15, 20, 25, 30]

    result = counted("2025-04", *counts).latest(PeriodCount(12))

    assert flagged(result) == [f"2026-{month:02d}" for month in range(first, 13)]
    assert result.last_complete_period == last


def test_a_lasting_drop_older_than_a_year_is_not_a_tail() -> None:
    """Made-up counts (a rule test): 2000 a month for a year, then 800 a month for two
    years. Each month of the second year is usual against the year before it, and a run
    of incomplete periods is at most a year long, so nothing is flagged."""
    result = counted("2023-01", *([2000] * 12), *([800] * 24)).latest(PeriodCount(12))

    assert flagged(result) == []
    assert result.last_complete_period == "2025-12"


def test_the_reference_is_the_year_right_before_a_period() -> None:
    """Months older than a year before do not count (a rule test, made-up counts): the
    year before the newest month had 1000 transactions a month, the year before that
    200; 450 is below half of 1000, but not below half of the median of both years
    (600)."""
    result = counted("2024-01", *([200] * 12), *([1000] * 12), 450).latest(PeriodCount(1))

    assert flagged(result) == ["2026-01"]
    assert result.last_complete_period == "2025-12"


def test_quarters_are_judged_against_the_four_before() -> None:
    """tests/fixtures/api/avg_trend_city_warszawa_20261016.json: 2026-Q2 (1,034) and
    2026-Q3 (37) are incomplete, 2026-Q1 (3,721) is not."""
    quarters = counted("2025-Q1", *WARSZAWA_LAST_7_QUARTERS, granularity=Granularity.QUARTER)

    result = quarters.latest(PeriodCount(12))

    assert flagged(result) == ["2026-Q2", "2026-Q3"]
    assert result.last_complete_period == "2026-Q1"


def test_with_too_little_history_nothing_is_judged() -> None:
    """The fixture's 2026-03..2026-05 alone: fewer than three periods before the newest
    one, so nothing is flagged, and no period is known to be complete."""
    result = counted("2026-03", 1390, 987, 22).latest(PeriodCount(12))

    assert flagged(result) == []
    assert result.last_complete_period is None
    assert result.few_transactions is False


def test_when_every_period_that_can_be_judged_is_incomplete_none_is_complete() -> None:
    """The fixture's 2026-02..2026-06 alone: 2026-05 and 2026-06 are below half of the
    periods before them, and 2026-04 has too little history to be judged itself."""
    result = counted("2026-02", 1180, 1390, 987, 22, 0).latest(PeriodCount(12))

    assert flagged(result) == ["2026-05", "2026-06"]
    assert result.last_complete_period is None


@pytest.mark.parametrize(
    "counts",
    [
        # 2024-12..2025-12 of tests/fixtures/api/monthly_tx_karpacz_20261016.json.
        (3, 0, 1, 3, 2, 7, 0, 1, 2, 2, 1, 7, 1),
        # No transaction at all.
        (0,) * 13,
    ],
)
def test_too_few_transactions_are_not_judged(counts: tuple[int, ...]) -> None:
    """A usual number below MIN_USUAL_TRANSACTIONS: a low month at the end is chance as
    often as the register's lag, so nothing is flagged and no period is known to be
    complete."""
    result = counted("2024-12", *counts).latest(PeriodCount(12))

    assert flagged(result) == []
    assert result.last_complete_period is None
    assert result.few_transactions is True


def test_a_big_city_with_a_year_of_empty_months_flags_them_all() -> None:
    """Made-up counts (a rule test): two years of 1200 transactions a month, then twelve
    months without any. They are incomplete, not a city of too few transactions."""
    result = counted("2023-01", *([1200] * 24), *([0] * 12)).latest(PeriodCount(12))

    assert flagged(result) == [f"2025-{month:02d}" for month in range(1, 13)]
    assert result.last_complete_period == "2024-12"
    assert result.few_transactions is False


def test_a_tail_judged_against_just_enough_transactions_is_not_too_few() -> None:
    """Made-up counts (a rule test): the usual number right before the tail is 10 (the
    floor), one period earlier it is 8. The tail is flagged; the period before it is not
    judged, so none is known complete, yet the series is not one of too few."""
    counts = (0, *([8] * 6), *([12] * 6), 0, 0)

    result = counted("2025-01", *counts).latest(PeriodCount(12))

    assert flagged(result) == ["2026-02", "2026-03"]
    assert result.last_complete_period is None
    assert result.few_transactions is False


def test_a_usual_number_at_the_floor_is_judged() -> None:
    """Made-up counts (a rule test): 10 transactions every month, the floor itself."""
    result = counted("2025-01", *([10] * 13)).latest(PeriodCount(12))

    assert flagged(result) == []
    assert result.last_complete_period == "2026-01"
    assert result.few_transactions is False


@pytest.mark.parametrize(("usual", "judged"), [(10, True), (9, False)])
def test_the_floor_is_the_usual_number_of_transactions(usual: int, judged: bool) -> None:
    """Made-up counts (a rule test): a year of ``usual`` transactions a month, then a
    month without any."""
    result = counted("2025-01", *([usual] * 12), 0).latest(PeriodCount(12))

    assert flagged(result) == (["2026-01"] if judged else [])
    assert result.last_complete_period == ("2025-12" if judged else None)
    assert result.few_transactions is not judged
