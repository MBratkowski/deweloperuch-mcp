"""Government statistics (GUS, NBP, Eurostat) of a location as time series (D3, D13).

Plain Python: frozen dataclasses and enums, no I/O, no pydantic, no backend names. The
values come through the port ``domain.ports.GovernmentStatisticsSource``; this module
says what they mean and how a result is cut (D4)::

    location = LocationSlug.parse("warszawa")          # InvalidInputError if not a slug
    dataset = Dataset.parse("nbp_prices")               # InvalidInputError if unknown
    periods = PeriodCount.parse(12)                     # InvalidInputError if out of range
    published = source.location_statistics(location, dataset)
    result = published.statistics(dataset, periods)    # NotFoundError if not published

Periods are labels that sort in time order within one frequency: ``2025`` (year),
``2025-Q3`` (quarter), ``2025-08`` (month). Values are ``float``; ``None`` is a period
without data (e.g. dwellings started for rent before the statistics existed).

A table knows the ``section`` of the service's page that shows it (an id of the page's
table of contents), so the application can link to it (``ports.PageLinks``); the domain
holds no addresses.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from deweloperuch_mcp.domain.errors import InvalidValueError, NotFoundError, OneOf, ValueName
from deweloperuch_mcp.domain.values import LocationSlug, whole

DEFAULT_PERIODS = 12
"""Periods a result holds unless asked otherwise: the latest ones."""
PERIODS_MAX = 1_000
"""Most periods one may ask for; more than any series has (357 months, [P 2026-10-11])."""

# --- value objects ---------------------------------------------------------------------------
# (``LocationSlug``, the location of these statistics, is in ``domain.values`` with the
# other slugs.)


@dataclass(frozen=True)
class PeriodCount:
    """How many of the latest periods a result shows: 1..``PERIODS_MAX``."""

    value: int = DEFAULT_PERIODS

    def __post_init__(self) -> None:
        whole(ValueName.PERIODS, self.value, 1, PERIODS_MAX)

    @classmethod
    def parse(cls, value: object) -> "PeriodCount":
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


class Frequency(StrEnum):
    """How often a series has a value; its periods are labelled accordingly."""

    YEAR = "year"
    QUARTER = "quarter"
    MONTH = "month"

    def label_pattern(self) -> re.Pattern[str]:
        return _PERIOD_PATTERNS[self]

    @property
    def polish(self) -> str:
        return _FREQUENCY_NAMES[self]


_PERIOD_PATTERNS = {
    Frequency.YEAR: re.compile(r"\d{4}"),
    Frequency.QUARTER: re.compile(r"\d{4}-Q[1-4]"),
    Frequency.MONTH: re.compile(r"\d{4}-(?:0[1-9]|1[0-2])"),
}
_FREQUENCY_NAMES = {
    Frequency.YEAR: "rocznie",
    Frequency.QUARTER: "kwartalnie",
    Frequency.MONTH: "miesięcznie",
}


class Unit(StrEnum):
    DWELLINGS = "mieszkania"
    SQUARE_METRES = "m²"
    PEOPLE = "osoby"
    PERCENT = "%"
    PLN = "PLN"
    PLN_PER_M2 = "PLN/m²"


@dataclass(frozen=True)
class SeriesDefinition:
    """What one series measures: its id (stable, for programs), label and unit."""

    series_id: str
    label: str
    unit: Unit


def _series(unit: Unit, *pairs: tuple[str, str]) -> tuple[SeriesDefinition, ...]:
    return tuple(SeriesDefinition(series_id, label, unit) for series_id, label in pairs)


# Forms of construction as the statistics name them (GUS "formy budownictwa"; the page
# shows them in its section "Formy budownictwa" [P 2026-10-11]).
_FORMS = (
    ("developer", "deweloperskie"),
    ("individual", "indywidualne"),
    ("cooperative", "spółdzielcze"),
    ("municipal", "komunalne"),
    ("social", "społeczne"),
    ("company", "zakładowe"),
)
_DWELLINGS = _series(
    Unit.DWELLINGS,
    ("completed_total", "Oddane do użytkowania: razem"),
    *((f"completed_{key}", f"Oddane: {name}") for key, name in _FORMS),
    ("started_total", "Rozpoczęte budowy: razem"),
    *((f"started_{key}", f"Rozpoczęte: {name}") for key, name in _FORMS),
    ("started_for_rent", "Rozpoczęte: na wynajem"),
)


class Dataset(StrEnum):
    """A set of series the service publishes for a location (one section of its page)."""

    DWELLINGS_QUARTERLY = "dwellings_quarterly"
    DWELLINGS_MONTHLY = "dwellings_monthly"
    AVERAGE_AREA = "average_area"
    DEMOGRAPHY = "demography"
    POPULATION = "population"
    UNEMPLOYMENT = "unemployment"
    WAGES = "wages"
    NBP_PRICES = "nbp_prices"

    @classmethod
    def parse(cls, value: object) -> "Dataset":
        """A ``Dataset`` or its value (spaces around it ignored)."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str) and value.strip() in cls._value2member_map_:
            return cls(value.strip())
        raise InvalidValueError(ValueName.DATASET, OneOf(tuple(d.value for d in cls)), value)

    @property
    def label(self) -> str:
        """What the dataset holds, in Polish."""
        return _TITLES[self]

    @property
    def series(self) -> tuple[SeriesDefinition, ...]:
        """Every series the dataset may have, in the order results show them."""
        return _DATASET_SERIES[self]


_TITLES = {
    Dataset.DWELLINGS_QUARTERLY: "Mieszkania oddane do użytkowania i rozpoczęte (kwartalnie)",
    Dataset.DWELLINGS_MONTHLY: "Mieszkania oddane do użytkowania i rozpoczęte (miesięcznie)",
    Dataset.AVERAGE_AREA: (
        "Średnia powierzchnia użytkowa mieszkania lub domu oddanego przez deweloperów"
    ),
    Dataset.DEMOGRAPHY: "Urodzenia żywe, zgony i przyrost naturalny",
    Dataset.POPULATION: "Ludność według płci (stan na 31 grudnia)",
    Dataset.UNEMPLOYMENT: "Stopa bezrobocia rejestrowanego",
    Dataset.WAGES: "Przeciętne miesięczne wynagrodzenie brutto w sektorze przedsiębiorstw",
    Dataset.NBP_PRICES: "Średnie ceny mieszkań za m² według NBP",
}
_DATASET_SERIES = {
    Dataset.DWELLINGS_QUARTERLY: _DWELLINGS,
    Dataset.DWELLINGS_MONTHLY: _DWELLINGS,
    Dataset.AVERAGE_AREA: _series(Unit.SQUARE_METRES, ("average_area", "Średnia powierzchnia")),
    Dataset.DEMOGRAPHY: _series(
        Unit.PEOPLE,
        ("births", "Urodzenia żywe"),
        ("deaths", "Zgony"),
        ("natural_increase", "Przyrost naturalny"),
    ),
    Dataset.POPULATION: _series(
        Unit.PEOPLE, ("total", "Razem"), ("women", "Kobiety"), ("men", "Mężczyźni")
    ),
    Dataset.UNEMPLOYMENT: _series(Unit.PERCENT, ("rate", "Stopa bezrobocia")),
    Dataset.WAGES: (
        SeriesDefinition("gross", "Wynagrodzenie brutto", Unit.PLN),
        SeriesDefinition(
            "relative_to_poland", "Relacja do średniej krajowej (Polska = 100)", Unit.PERCENT
        ),
    ),
    Dataset.NBP_PRICES: _series(
        Unit.PLN_PER_M2,
        ("primary_asking", "Rynek pierwotny: cena ofertowa"),
        ("primary_transaction", "Rynek pierwotny: cena transakcyjna"),
        ("secondary_asking", "Rynek wtórny: cena ofertowa"),
        ("secondary_transaction", "Rynek wtórny: cena transakcyjna"),
    ),
}


# --- series and tables ---------------------------------------------------------------------


@dataclass(frozen=True)
class SeriesPoint:
    period: str
    value: float | None


@dataclass(frozen=True)
class TimeSeries:
    """One measure over time, oldest period first."""

    series_id: str
    label: str
    unit: Unit
    points: tuple[SeriesPoint, ...]

    @property
    def periods(self) -> tuple[str, ...]:
        return tuple(point.period for point in self.points)

    def latest(self, count: int) -> "TimeSeries":
        """The last ``count`` points (all of them if there are fewer)."""
        return TimeSeries(self.series_id, self.label, self.unit, self.points[-count:])


@dataclass(frozen=True)
class StatisticsTable:
    """All series of one dataset for one location; they share their periods.

    ``section``: where the service's page shows this data (an id of its table of
    contents), the anchor of a link for people (D12); ``None`` when the page has none.
    It is knowledge of the service's page passing through the domain on purpose: which
    section holds a dataset depends on the page itself (``polska`` shows its demography in
    another section than a city), so only the adapter that read the page can say, and
    the domain carries it as an opaque identity for ``ports.PageLinks``.
    """

    dataset: Dataset
    frequency: Frequency
    source: str
    series: tuple[TimeSeries, ...]
    section: str | None = None

    def __post_init__(self) -> None:
        if not self.series:
            raise ValueError(f"{self.dataset}: zestaw bez szeregów")
        periods = self.periods
        pattern = self.frequency.label_pattern()
        if not all(pattern.fullmatch(period) for period in periods):
            raise ValueError(f"{self.dataset}: okresy niezgodne z częstotliwością {periods!r}")
        if any(later <= earlier for earlier, later in zip(periods, periods[1:], strict=False)):
            raise ValueError(f"{self.dataset}: okresy nie rosną albo się powtarzają")
        if any(series.periods != periods for series in self.series):
            raise ValueError(f"{self.dataset}: szeregi o różnych okresach")
        known = {definition.series_id for definition in self.dataset.series}
        if not {series.series_id for series in self.series} <= known:
            raise ValueError(f"{self.dataset}: nieznany szereg")

    @property
    def periods(self) -> tuple[str, ...]:
        return self.series[0].periods


@dataclass(frozen=True)
class StatisticsLocation:
    """A location of the service's list of these statistics."""

    slug: str
    name: str
    is_aggregate: bool
    has_nbp_prices: bool
    """NBP publishes prices only for some big cities and their aggregates [P 2026-10-11]."""


@dataclass(frozen=True)
class GovernmentStatistics:
    """The latest periods of one dataset for one location (D4: the cut is explicit)."""

    location_slug: str
    location_name: str
    dataset: Dataset
    title: str
    source: str
    frequency: Frequency
    total: int
    """Periods the service has for this dataset and location."""
    returned: int
    truncated: bool
    """Older periods exist than the ones shown."""
    available_from: str
    """The oldest period the service has."""
    note: str | None
    """A caveat about the data, e.g. a last quarter that holds only some of its months."""
    section: str | None
    """Where the service's page shows the data (``StatisticsTable.section``)."""
    series: tuple[TimeSeries, ...]

    @property
    def periods(self) -> tuple[str, ...]:
        return self.series[0].periods


@dataclass(frozen=True)
class LocationStatistics:
    """What the service publishes for one location: a table per dataset it shows.

    ``locations``: the service's list of locations of these statistics (for hints).
    """

    location: LocationSlug
    name: str
    tables: Mapping[Dataset, StatisticsTable]
    locations: tuple[StatisticsLocation, ...] = field(default=())

    def statistics(self, dataset: Dataset, periods: PeriodCount) -> GovernmentStatistics:
        """The last ``periods`` periods of ``dataset``; ``NotFoundError`` when the service
        does not publish it for this location."""
        table = self.tables.get(dataset)
        if table is None:
            raise NotFoundError(self._not_published(dataset))
        total = len(table.periods)
        series = tuple(item.latest(periods.value) for item in table.series)
        returned = len(series[0].points)
        return GovernmentStatistics(
            location_slug=self.location.value,
            location_name=self.name,
            dataset=dataset,
            title=dataset.label,
            source=table.source,
            frequency=table.frequency,
            total=total,
            returned=returned,
            truncated=returned < total,
            available_from=table.periods[0],
            note=self._note(dataset, table),
            section=table.section,
            series=series,
        )

    def _not_published(self, dataset: Dataset) -> str:
        where = f"lokalizacji {self.location.value!r}"
        if dataset is Dataset.NBP_PRICES:
            with_prices = [loc.slug for loc in self.locations if loc.has_nbp_prices]
            if self.location.whole_country:
                head = "NBP nie podaje jednej ceny dla całej Polski, tylko dla miast i agregatów."
            else:
                head = f"NBP nie publikuje cen mieszkań dla {where}."
            if with_prices:
                return f"{head} Podaj jedną z lokalizacji: {', '.join(with_prices)}."
            return head
        return f"Serwis nie publikuje zestawu {dataset.value!r} ({dataset.label}) dla {where}."

    def _note(self, dataset: Dataset, table: StatisticsTable) -> str | None:
        """Quarters are sums of months [P 2026-10-11: every quarter of both fixtures]; the
        last quarter is incomplete when the monthly data ends before its last month."""
        if dataset is not Dataset.DWELLINGS_QUARTERLY:
            return None
        monthly = self.tables.get(Dataset.DWELLINGS_MONTHLY)
        if monthly is None:
            return None
        quarter = table.periods[-1]
        months = set(monthly.periods) & set(_months_of(quarter))
        if len(months) == 3:
            return None
        return (
            f"Ostatni kwartał ({quarter}) obejmuje tylko {len(months)} z 3 miesięcy "
            f"(dane miesięczne do {monthly.periods[-1]}); nie porównuj go z pełnymi kwartałami."
        )


def _months_of(quarter: str) -> Iterable[str]:
    year, number = quarter.split("-Q")
    first = 3 * (int(number) - 1) + 1
    return (f"{year}-{month:02d}" for month in range(first, first + 3))
