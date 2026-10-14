"""Tests of ``deweloperuch_mcp.models.government_statistics``."""

import dataclasses
from collections.abc import Mapping

import pytest

from deweloperuch_mcp.models.errors import (
    InvalidValueError,
    NotFoundError,
    OneOf,
    ValueName,
    WholeNumber,
)
from deweloperuch_mcp.models.government_statistics import (
    DEFAULT_PERIODS,
    PERIODS_MAX,
    Dataset,
    Frequency,
    LocationStatistics,
    PeriodCount,
    SeriesPoint,
    StatisticsLocation,
    StatisticsTable,
    TimeSeries,
    Unit,
)
from deweloperuch_mcp.models.values import LocationSlug


def series(
    series_id: str, points: Mapping[str, float | None], unit: Unit = Unit.PERCENT
) -> TimeSeries:
    return TimeSeries(
        series_id,
        series_id,
        unit,
        tuple(SeriesPoint(period, value) for period, value in points.items()),
    )


def table(dataset: Dataset, frequency: Frequency, *items: TimeSeries) -> StatisticsTable:
    return StatisticsTable(dataset, frequency, "GUS", items, f"section-{dataset}")


YEARS = {str(year): float(year - 2000) for year in range(2005, 2027)}  # 22 years


RATE = table(Dataset.UNEMPLOYMENT, Frequency.YEAR, series("rate", YEARS))


def location(*tables: StatisticsTable, slug: str = "warszawa") -> LocationStatistics:
    return LocationStatistics(
        location=LocationSlug(slug),
        name="Warszawa",
        tables={item.dataset: item for item in tables},
        locations=(
            StatisticsLocation("7-miast", "Top 7 miast Polski", True, True),
            StatisticsLocation("warszawa", "Warszawa", False, True),
            StatisticsLocation("sopot", "Sopot", False, False),
        ),
    )


def dwellings(frequency: Frequency, periods: list[str]) -> StatisticsTable:
    dataset = (
        Dataset.DWELLINGS_QUARTERLY if frequency is Frequency.QUARTER else Dataset.DWELLINGS_MONTHLY
    )
    return table(
        dataset, frequency, series("completed_total", dict.fromkeys(periods, 1.0), Unit.DWELLINGS)
    )


@pytest.mark.parametrize("value", [Dataset.WAGES, "wages", " wages "])
def test_datasets(value: object) -> None:
    assert Dataset.parse(value) is Dataset.WAGES


@pytest.mark.parametrize("value", ["Wages", "wage", "", None, 3, "nbp"])
def test_unknown_datasets_list_the_known_ones(value: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        Dataset.parse(value)

    assert caught.value.value is ValueName.DATASET
    assert caught.value.rule == OneOf(
        (
            "dwellings_quarterly",
            "dwellings_monthly",
            "average_area",
            "demography",
            "population",
            "unemployment",
            "wages",
            "nbp_prices",
        )
    )
    assert caught.value.given == value


@pytest.mark.parametrize("value", [1, DEFAULT_PERIODS, PERIODS_MAX])
def test_period_counts(value: int) -> None:
    assert PeriodCount.parse(value).value == value


@pytest.mark.parametrize("value", [0, -1, PERIODS_MAX + 1, True, 1.5, "12", None])
def test_period_counts_out_of_range(value: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        PeriodCount.parse(value)

    assert (caught.value.value, caught.value.rule) == (
        ValueName.PERIODS,
        WholeNumber(1, PERIODS_MAX),
    )


def test_every_dataset_has_a_polish_label_and_its_series() -> None:
    for dataset in Dataset:
        assert dataset.label and dataset.label[0].isupper()
        ids = [definition.series_id for definition in dataset.series]
        assert ids and len(set(ids)) == len(ids)
    assert len(Dataset.DWELLINGS_QUARTERLY.series) == 15
    assert Dataset.DWELLINGS_QUARTERLY.series == Dataset.DWELLINGS_MONTHLY.series


def test_values_are_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        RATE.source = "NBP"  # type: ignore[misc]


def test_the_latest_periods_and_the_counters() -> None:
    result = location(RATE).statistics(Dataset.UNEMPLOYMENT, PeriodCount(3))

    assert result.periods == ("2024", "2025", "2026")
    assert [p.value for p in result.series[0].points] == [24.0, 25.0, 26.0]
    assert (result.total, result.returned, result.truncated) == (22, 3, True)
    assert result.available_from == "2005"


@pytest.mark.parametrize("count", [22, 23, PERIODS_MAX])
def test_every_period_is_not_truncated(count: int) -> None:
    result = location(RATE).statistics(Dataset.UNEMPLOYMENT, PeriodCount(count))

    assert (result.total, result.returned, result.truncated) == (22, 22, False)
    assert result.periods[0] == "2005"


def test_the_result_carries_what_the_table_says() -> None:
    result = location(RATE).statistics(Dataset.UNEMPLOYMENT, PeriodCount())

    assert (result.location_slug, result.location_name) == ("warszawa", "Warszawa")
    assert (result.dataset, result.title) == (
        Dataset.UNEMPLOYMENT,
        "Stopa bezrobocia rejestrowanego",
    )
    assert (result.source, result.frequency) == ("GUS", Frequency.YEAR)
    assert result.section == "section-unemployment"
    assert result.returned == DEFAULT_PERIODS == 12


def test_every_series_is_cut_to_the_same_periods() -> None:
    nbp = table(
        Dataset.NBP_PRICES,
        Frequency.QUARTER,
        series("primary_asking", {"2025-Q4": 1.0, "2026-Q1": 2.0, "2026-Q2": 3.0}),
        series("secondary_asking", {"2025-Q4": None, "2026-Q1": 5.0, "2026-Q2": None}),
    )

    result = location(nbp).statistics(Dataset.NBP_PRICES, PeriodCount(2))

    assert [s.periods for s in result.series] == [("2026-Q1", "2026-Q2")] * 2
    assert [p.value for p in result.series[1].points] == [5.0, None]


@pytest.mark.parametrize(
    ("months", "note"),
    [
        (
            ["2026-06", "2026-07", "2026-08"],
            "Ostatni kwartał (2026-Q3) obejmuje tylko 2 z 3 miesięcy (dane miesięczne do "
            "2026-08); nie porównuj go z pełnymi kwartałami.",
        ),
        (
            ["2026-06", "2026-07"],
            "Ostatni kwartał (2026-Q3) obejmuje tylko 1 z 3 miesięcy (dane miesięczne do "
            "2026-07); nie porównuj go z pełnymi kwartałami.",
        ),
        (["2026-07", "2026-08", "2026-09"], None),
    ],
)
def test_an_incomplete_last_quarter_is_noted(months: list[str], note: str | None) -> None:
    quarterly = dwellings(Frequency.QUARTER, ["2026-Q2", "2026-Q3"])
    monthly = dwellings(Frequency.MONTH, months)

    result = location(quarterly, monthly).statistics(Dataset.DWELLINGS_QUARTERLY, PeriodCount())

    assert result.note == note


def test_no_note_without_monthly_data_or_for_other_datasets() -> None:
    quarterly = dwellings(Frequency.QUARTER, ["2026-Q3"])
    monthly = dwellings(Frequency.MONTH, ["2026-07"])

    assert location(quarterly).statistics(Dataset.DWELLINGS_QUARTERLY, PeriodCount()).note is None
    both = location(quarterly, monthly)
    assert both.statistics(Dataset.DWELLINGS_MONTHLY, PeriodCount()).note is None


def test_a_dataset_the_location_does_not_have_is_not_found() -> None:
    with pytest.raises(NotFoundError) as caught:
        location(RATE).statistics(Dataset.WAGES, PeriodCount())

    assert str(caught.value) == (
        "Serwis nie publikuje zestawu 'wages' (Przeciętne miesięczne wynagrodzenie brutto w "
        "sektorze przedsiębiorstw) dla lokalizacji 'warszawa'."
    )


def test_nbp_prices_of_the_whole_country_point_to_the_locations_that_have_them() -> None:
    with pytest.raises(NotFoundError) as caught:
        location(RATE, slug="polska").statistics(Dataset.NBP_PRICES, PeriodCount())

    assert str(caught.value) == (
        "NBP nie podaje jednej ceny dla całej Polski, tylko dla miast i agregatów. Podaj jedną "
        "z lokalizacji: 7-miast, warszawa."
    )


def test_nbp_prices_of_a_city_without_them() -> None:
    with pytest.raises(NotFoundError) as caught:
        location(RATE, slug="sopot").statistics(Dataset.NBP_PRICES, PeriodCount())

    assert str(caught.value).startswith("NBP nie publikuje cen mieszkań dla lokalizacji 'sopot'.")
    assert str(caught.value).endswith("Podaj jedną z lokalizacji: 7-miast, warszawa.")


@pytest.mark.parametrize(
    ("frequency", "items", "problem"),
    [
        (Frequency.YEAR, (), "bez szeregów"),
        (Frequency.QUARTER, (series("rate", {"2025": 1.0}),), "częstotliwością"),
        (Frequency.MONTH, (series("rate", {"2025-13": 1.0}),), "częstotliwością"),
        (Frequency.YEAR, (series("rate", {"2026": 1.0, "2025": 2.0}),), "nie rosną"),
        (
            Frequency.YEAR,
            (series("rate", {"2025": 1.0}), series("rate", {"2026": 1.0})),
            "różnych okresach",
        ),
        (Frequency.YEAR, (series("gross", {"2025": 1.0}),), "nieznany szereg"),
    ],
)
def test_a_table_keeps_its_invariants(
    frequency: Frequency, items: tuple[TimeSeries, ...], problem: str
) -> None:
    with pytest.raises(ValueError, match=problem):
        StatisticsTable(Dataset.UNEMPLOYMENT, frequency, "GUS", items)
