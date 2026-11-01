"""``GovernmentStatsPageDto``: the government statistics (GUS, NBP, Eurostat) of
``/statystyki/{location}/dane-rzadowe`` (RSC), read from the page's props
(``from_payload``) and mapped to the models (``to_model``, ``models.government_statistics``).

The page is an internal channel of the site's UI, not an API: its props may change at any
deploy, without notice (D21). Its 2.0 props [P 2026-10-31, the pages of ``warszawa``,
``polska`` and ``7-miast``, tests/fixtures/rsc/stats_gov_*_20261031.rsc]:

- ``blocks.govSections``: the ids of the page's sections. They differ per location
  (``polska`` has ``eurostat-demografia`` and ``nbp-grid`` instead of ``gus-demografia``
  and ``nbp``; ``7-miast`` has no ``gus-wynagrodzenia``), so a table's section, the anchor
  of its link (``links``), is one this page lists (``SECTIONS``);
- props of rows, told apart by their keys (``STATS_SHAPES``): the quarterly and monthly
  dwellings (``data``, ``monthlyData``), the population (``data``) and the NBP prices
  (``data``; ``polska`` has none, it shows a grid of cities);
- chart specs (``spec``), told apart by their ``id`` (``CHARTS``): the average area, the
  demography, the unemployment rate and the wages;
- ``citySlug`` and ``cityName``: the location (the page of ``polska`` has neither).

The values of the eight datasets are those of the 1.0 page [P 2026-10-31: every period
both pages have, ``warszawa`` and ``polska`` against the captures of 2026-10-11,
tests/fixtures/rsc/stats_gov_{warszawa,polska}.rsc]. Names of the backend (``oddane``,
``govSections``...) stay in ``api``.

A section the page lists tells a dataset it shows from one it does not have: when the data
of a listed section cannot be read, the service changed (``UnexpectedResponseError``),
unless the page fills that section with other data (``CHARTS_WITHOUT_SERIES``); a dataset
without its section is one the location lacks (``NotFoundError`` from the domain).
"""

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Self

from pydantic import BeforeValidator, Field

from deweloperuch_mcp.api.dto.dto import Dto, MonthText, Number, QuarterText
from deweloperuch_mcp.flight import NOT_FOUND_DIGEST, component_props, error_digests
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError
from deweloperuch_mcp.models.government_statistics import (
    Dataset,
    Frequency,
    LocationStatistics,
    SeriesPoint,
    StatisticsTable,
    TimeSeries,
)
from deweloperuch_mcp.models.values import LocationSlug

_log = logging.getLogger(__name__)

# --- the rows of the data props ----------------------------------------------------------

YEAR_MIN, YEAR_MAX = 1900, 2200


def _check_year(value: object) -> int:
    """``2025`` or ``"2025"`` -> 2025, within ``YEAR_MIN``..``YEAR_MAX``."""
    if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or not YEAR_MIN <= value <= YEAR_MAX:
        raise ValueError(f"oczekiwano roku {YEAR_MIN}–{YEAR_MAX}, podano {value!r}")
    return value


Year = Annotated[int, BeforeValidator(_check_year)]


class StatsRowDto(Dto):
    """A row of a data prop; a table reads its columns by name (``_Rows.columns``)."""

    def number(self, field: str) -> float | None:
        """The value of ``field`` as a number; ``None`` for no value."""
        value: int | float | str | None = getattr(self, field)
        return self._number(value)


class DwellingsCountsDto(StatsRowDto):
    """Dwellings completed (``oddane``) and started (``rozpoczete``) by form [P].

    The totals are the keys the rows are recognized by (``STATS_SHAPES``), so they
    are required; the forms may be missing (``None``): every form is [P] on the three
    pages seen, [W] on the others, and a series without values is left out of the table.
    """

    oddane: Number | None
    oddaneDeweloperskie: Number | None = None
    oddaneIndywidualne: Number | None = None
    oddaneSpoldzielcze: Number | None = None
    oddaneKomunalne: Number | None = None
    oddaneSpoleczne: Number | None = None
    oddaneZakladowe: Number | None = None
    rozpoczete: Number | None
    rozpoczeteDeweloperskie: Number | None = None
    rozpoczeteIndywidualne: Number | None = None
    rozpoczeteSpoldzielcze: Number | None = None
    rozpoczeteKomunalne: Number | None = None
    rozpoczeteSpoleczne: Number | None = None
    rozpoczeteZakladowe: Number | None = None
    rozpoczeteNaWynajem: Number | None = None
    """``null`` before the statistics existed (2005-Q1..2018-Q4 [P])."""


class DwellingsQuarterDto(DwellingsCountsDto):
    """A row of the quarterly ``data`` prop: a quarter, the sum of its months [P]."""

    quarter: QuarterText


class DwellingsMonthDto(DwellingsCountsDto):
    """A row of prop ``monthlyData`` [P]."""

    month: MonthText


class PopulationYearDto(StatsRowDto):
    """Women and men on 31 December (the age pyramid's totals; its ``cohorts`` are not
    read) [P]: their sum is the population the page states."""

    year: Year
    totalKobiety: Number | None
    totalMezczyzni: Number | None


class NbpQuarterDto(StatsRowDto):
    """NBP's average prices per m² (PLN), asking and transaction, primary and secondary
    market [P warszawa, 7-miast]; the whole country has no such series, only a grid of
    cities."""

    quarter: QuarterText
    pierwotnyOfertowa: Number | None
    pierwotnyTransakcyjna: Number | None
    wtornyOfertowa: Number | None
    wtornyTransakcyjna: Number | None


RawRows = list[dict[str, Any]]
"""The rows of one data prop as the page has them; ``STATS_ROWS`` checks them."""

STATS_ROWS: Mapping[str, type[StatsRowDto]] = {
    "dwellings_quarterly": DwellingsQuarterDto,
    "dwellings_monthly": DwellingsMonthDto,
    "population_yearly": PopulationYearDto,
    "nbp_quarterly": NbpQuarterDto,
}
"""The row of each data field of ``GovernmentStatsPageDto``."""

# --- telling the data props apart by their rows --------------------------------------------


@dataclass(frozen=True)
class StatsShape:
    """How rows of one kind of data prop look: every row has ``keys``; ``field`` is where
    ``GovernmentStatsPageDto`` keeps them."""

    field: str
    keys: frozenset[str]


def _shape(field: str, *keys: str) -> StatsShape:
    return StatsShape(field, frozenset(keys))


# [P 2026-10-31] tests/fixtures/rsc/stats_gov_*_20261031.rsc: the page has several props
# called `data` (and `monthlyData`); each kind has keys no other kind has. A prop whose rows
# match none of these is not read (e.g. the NBP grid of cities on `polska`).
STATS_SHAPES = (
    _shape("dwellings_quarterly", "quarter", "oddane", "rozpoczete"),
    _shape("dwellings_monthly", "month", "oddane", "rozpoczete"),
    _shape("population_yearly", "year", "totalKobiety", "totalMezczyzni"),
    _shape(
        "nbp_quarterly",
        "quarter",
        "pierwotnyOfertowa",
        "pierwotnyTransakcyjna",
        "wtornyOfertowa",
        "wtornyTransakcyjna",
    ),
)

# --- the chart specs ----------------------------------------------------------------------------


class ChartPointDto(Dto):
    """A point of a chart: its period (``2025``, ``2025-08``), the values of its series by
    key and the texts the page shows with them (``notes``) [P]. Only what the client reads
    is checked: the values of the series of ``CHARTS`` (``ChartValueDto``) and the notes
    ``_ratios`` reads, so an unread series or notes off the contract (a city's national
    comparison as "n/d", ``notes: null``) do not make the dataset unreadable."""

    period: str
    values: dict[str, Any]
    notes: Any = None


class ChartValueDto(Dto):
    """A value of a series the client reads, as the page sends it: ``Number`` or no value."""

    value: Number | None = None

    def number(self) -> float | None:
        return self._number(self.value)


class ChartDataDto(Dto):
    """One dataset of a chart, a choice of its switches (``""`` for a chart without them,
    ``ruch|mies`` for "births and deaths, monthly") [P]: its points."""

    points: list[ChartPointDto]


class ChartSpecDto(Dto):
    """A chart of the page (prop ``spec``) [P]: its ``id`` and its datasets by key, each
    checked when it is read (``ChartDataDto``), so a dataset the client does not read does
    not matter."""

    id: str
    datasets: dict[str, Any]


# --- the rows and the charts as series of the models ---------------------------------------

WHOLE_COUNTRY_NAME = "Polska"
"""The name of ``polska``: its page has no ``cityName`` [P 2026-10-31]."""

# Sections of each dataset among the page's `govSections` (the link's anchor): the ids of the
# 1.0 table of contents [P 2026-10-11], which the 2.0 pages list per location [P 2026-10-31]:
# `polska` shows its demography as `eurostat-demografia`, `warszawa` and `7-miast` as
# `gus-demografia`; `polska` has `nbp-grid` (prices of cities), not `nbp`.
SECTIONS: Mapping[Dataset, tuple[str, ...]] = {
    Dataset.DWELLINGS_QUARTERLY: ("gus-mieszkania",),
    Dataset.DWELLINGS_MONTHLY: ("gus-mieszkania",),
    Dataset.AVERAGE_AREA: ("gus-srednia-powierzchnia",),
    Dataset.DEMOGRAPHY: ("gus-demografia", "eurostat-demografia"),
    Dataset.POPULATION: ("gus-wiek",),
    Dataset.UNEMPLOYMENT: ("gus-bezrobocie",),
    Dataset.WAGES: ("gus-wynagrodzenia",),
    Dataset.NBP_PRICES: ("nbp",),
}

GUS, NBP = "GUS", "NBP"
# [P 2026-10-31] stats_gov_polska_20261031.rsc: the monthly demography of `polska` is the
# chart `eurostat-demografia-wykres`, whose `source` is "Eurostat", in the section
# headed „EUROSTAT · DEMOGRAFIA”; the cities' yearly charts give „GUS — Bank Danych
# Lokalnych”.
EUROSTAT = "Eurostat"

RowValue = Callable[[StatsRowDto], float | None]
Entries = list[tuple[str, dict[str, float | None]]]
"""A dataset as (period, series id -> value), one entry per row or point, in any order."""


@dataclass(frozen=True)
class _Reading:
    """How the page gives one dataset: its period (``frequency``) and ``source``."""

    dataset: Dataset
    frequency: Frequency
    source: str

    def _table(
        self, entries: Entries, series_ids: Sequence[str], section: str | None, where: str
    ) -> StatisticsTable:
        """The entries as series, oldest period first; series without any value are left
        out (e.g. a ratio the page does not give, or a form it does not list).

        Raises ``UnexpectedResponseError`` for an inconsistent table (``where`` in its
        detail): the caller decides whether that dataset was the one asked for.
        """
        ordered = sorted(entries, key=lambda entry: entry[0])
        definitions = {definition.series_id: definition for definition in self.dataset.series}
        series = []
        for series_id in series_ids:
            points = tuple(SeriesPoint(period, values.get(series_id)) for period, values in ordered)
            if any(point.value is not None for point in points):
                definition = definitions[series_id]
                series.append(TimeSeries(series_id, definition.label, definition.unit, points))
        try:
            return StatisticsTable(
                dataset=self.dataset,
                frequency=self.frequency,
                source=self.source,
                series=tuple(series),
                section=section,
            )
        except ValueError as err:  # e.g. a period twice, or no values at all
            raise _inconsistent(where, str(err)) from err


@dataclass(frozen=True)
class _Rows(_Reading):
    """A data prop of rows (``field`` of ``GovernmentStatsPageDto``) -> one dataset."""

    field: str
    columns: Sequence[tuple[str, RowValue]]

    def found(self, page: "GovernmentStatsPageDto") -> Any:
        return getattr(page, self.field)

    def table(self, raw: Any, section: str | None, path: str) -> StatisticsTable:
        """Raises ``UnexpectedResponseError`` for rows off the contract or an inconsistent
        table."""
        where = f"{path} ({self.field})"
        rows = Dto.validated_rows(STATS_ROWS[self.field], raw, where)
        entries = [
            (_period(row), {series_id: value(row) for series_id, value in self.columns})
            for row in rows
        ]
        return self._table(entries, [series_id for series_id, _ in self.columns], section, where)


@dataclass(frozen=True)
class _Chart(_Reading):
    """A chart (``chart_id``) -> one dataset: each series is read from the points of one of
    the chart's datasets (``columns``: series id, dataset key, key of the points' values,
    or ``None`` for the ratio in their notes, ``_ratios``)."""

    chart_id: str
    columns: Sequence[tuple[str, str, str | None]]

    def found(self, page: "GovernmentStatsPageDto") -> Any:
        return page.charts.get(self.chart_id)

    def table(self, raw: Any, section: str | None, path: str) -> StatisticsTable:
        """The points of the chart's datasets joined by period. Raises
        ``UnexpectedResponseError`` for a chart off the contract (a dataset missing, a
        point without its period, a value read that is no number), a period twice in one
        dataset or an inconsistent table."""
        where = f"{path} (spec {self.chart_id})"
        chart = Dto.validated(ChartSpecDto, raw, where)
        joined: dict[str, dict[str, float | None]] = {}
        for key in dict.fromkeys(key for _, key, _ in self.columns):
            for period, values in self._entries(chart, key, where):
                joined.setdefault(period, {}).update(values)
        series_ids = [series_id for series_id, _, _ in self.columns]
        return self._table(list(joined.items()), series_ids, section, where)

    def _entries(self, chart: ChartSpecDto, key: str, where: str) -> Entries:
        """The series of the chart's dataset ``key``, one entry per point."""
        source = f"{where} [{key!r}]"
        data = Dto.validated(ChartDataDto, chart.datasets.get(key), source)
        periods = [point.period for point in data.points]
        if len(set(periods)) < len(periods):
            raise _inconsistent(where, f"zbiór {key!r}: okres występuje dwa razy")
        entries: Entries = [(period, {}) for period in periods]
        for series_id, column, values_key in self.columns:
            if column == key:
                found = _series_of(data.points, values_key, source)
                for (_, values), value in zip(entries, found, strict=True):
                    values[series_id] = value
        return entries


def _period(row: Any) -> str:
    for name in ("quarter", "month"):
        label = getattr(row, name, None)
        if isinstance(label, str):
            return label
    return str(row.year)


def _attr(name: str) -> RowValue:
    return lambda row: row.number(name)


def _sum(*names: str) -> RowValue:
    """The sum of ``names``; ``None`` when any of them is missing."""

    def total(row: StatsRowDto) -> float | None:
        values = [row.number(name) for name in names]
        present = [value for value in values if value is not None]
        return sum(present) if len(present) == len(values) else None

    return total


def _series_of(
    points: Sequence[ChartPointDto], values_key: str | None, source: str
) -> list[float | None]:
    """The values ``values_key`` of the points, each checked (``ChartValueDto``; one off the
    contract raises ``UnexpectedResponseError``); ``None``: the ratios in their notes."""
    if values_key is None:
        return _ratios(points, source)
    rows = [{"value": point.values.get(values_key)} for point in points]
    checked = Dto.validated_rows(ChartValueDto, rows, f"{source} {values_key}")
    return [value.number() for value in checked]


# [P 2026-10-31] the yearly wages of `warszawa` (chart `gus-wynagrodzenia-roczne-wykres`): each
# of the 21 points has one note, "124,6 % średniej krajowej" (a no-break space before "%"),
# which the section's own text calls the wage's ratio to the national average (Polska =
# 100 %); every one equals the 1.0 page's `relacjaPolska` [P 2026-10-11]. A note in any other
# form is no value (the series is left out when no point has one).
_RATIO = re.compile(r"(\d+(?:,\d+)?)\s*% średniej krajowej")


def _ratios(points: Sequence[ChartPointDto], source: str) -> list[float | None]:
    """The ratio to the national average in each point's notes (``_ratio``).

    Text notes of which none is a ratio mean their wording changed (D21: the text of the
    site's UI): the series is left out, and a WARNING says so in the log of the server,
    where the live suite and a person find it.
    """
    ratios = [_ratio(point.notes) for point in points]
    texts = [note for point in points for note in _texts(point.notes)]
    if texts and all(ratio is None for ratio in ratios):
        _log.warning(
            "%s: %d notatek, żadna nie jest relacją do średniej krajowej, np. %r",
            source,
            len(texts),
            texts[0][:60],
        )
    return ratios


def _ratio(notes: Any) -> float | None:
    """The ratio to the national average among ``notes`` (the whole note, ``fullmatch``);
    ``None`` without one."""
    for note in _texts(notes):
        found = _RATIO.fullmatch(note.strip())
        if found:
            return float(found[1].replace(",", "."))
    return None


def _texts(notes: Any) -> list[str]:
    """The notes of a point that are texts: the strings of a list, nothing else."""
    return [note for note in notes if isinstance(note, str)] if isinstance(notes, list) else []


def _inconsistent(where: str, problem: str) -> UnexpectedResponseError:
    return UnexpectedResponseError(
        f"Dane statystyk na stronie serwisu są niespójne. {SERVICE_CHANGED}",
        detail=f"{where}: {problem}",
    )


_FORMS = (
    ("developer", "Deweloperskie"),
    ("individual", "Indywidualne"),
    ("cooperative", "Spoldzielcze"),
    ("municipal", "Komunalne"),
    ("social", "Spoleczne"),
    ("company", "Zakladowe"),
)
_DWELLINGS: Sequence[tuple[str, RowValue]] = (
    ("completed_total", _attr("oddane")),
    *((f"completed_{key}", _attr(f"oddane{name}")) for key, name in _FORMS),
    ("started_total", _attr("rozpoczete")),
    *((f"started_{key}", _attr(f"rozpoczete{name}")) for key, name in _FORMS),
    ("started_for_rent", _attr("rozpoczeteNaWynajem")),
)

ROWS = (
    _Rows(Dataset.DWELLINGS_QUARTERLY, Frequency.QUARTER, GUS, "dwellings_quarterly", _DWELLINGS),
    _Rows(Dataset.DWELLINGS_MONTHLY, Frequency.MONTH, GUS, "dwellings_monthly", _DWELLINGS),
    _Rows(
        Dataset.POPULATION,
        Frequency.YEAR,
        GUS,
        "population_yearly",
        (
            # [P 2026-10-31] the page states the population as this sum (2025: 37 332 510
            # for polska, 1 866 729 for warszawa, 5 258 113 for 7-miast).
            ("total", _sum("totalKobiety", "totalMezczyzni")),
            ("women", _attr("totalKobiety")),
            ("men", _attr("totalMezczyzni")),
        ),
    ),
    _Rows(
        Dataset.NBP_PRICES,
        Frequency.QUARTER,
        NBP,
        "nbp_quarterly",
        (
            ("primary_asking", _attr("pierwotnyOfertowa")),
            ("primary_transaction", _attr("pierwotnyTransakcyjna")),
            ("secondary_asking", _attr("wtornyOfertowa")),
            ("secondary_transaction", _attr("wtornyTransakcyjna")),
        ),
    ),
)
"""The datasets in data props (``STATS_SHAPES``)."""

# [P 2026-10-31] tests/fixtures/rsc/stats_gov_*_20261031.rsc: the chart ids and the keys of
# their datasets and series. The demography of `polska` has four datasets: births and
# deaths (`ruch`) or the natural increase (`przyrost`), monthly (`mies`) or as sums of 12
# months (`krocz`); the monthly ones are the dataset. The unemployment chart of a city also
# has the national rate (`polska`), which is not this location's. [W] the other cities and
# aggregates use the template of `warszawa` and `7-miast`: the same ids and keys.
CHARTS = (
    _Chart(
        Dataset.AVERAGE_AREA,
        Frequency.YEAR,
        GUS,
        "gus-powierzchnia-wykres",
        (("average_area", "", "powierzchnia"),),
    ),
    _Chart(
        Dataset.DEMOGRAPHY,
        Frequency.YEAR,
        GUS,
        "gus-demografia-wykres",
        (
            ("births", "ruch", "urodzenia"),
            ("deaths", "ruch", "zgony"),
            ("natural_increase", "przyrost", "przyrost"),
        ),
    ),
    _Chart(
        Dataset.DEMOGRAPHY,
        Frequency.MONTH,
        EUROSTAT,
        "eurostat-demografia-wykres",
        (
            ("births", "ruch|mies", "urodzenia"),
            ("deaths", "ruch|mies", "zgony"),
            ("natural_increase", "przyrost|mies", "przyrost"),
        ),
    ),
    _Chart(
        Dataset.UNEMPLOYMENT,
        Frequency.MONTH,
        GUS,
        "gus-bezrobocie-wykres",
        (("rate", "", "miejsce"),),
    ),
    _Chart(
        Dataset.WAGES,
        Frequency.MONTH,
        GUS,
        "gus-wynagrodzenia-wykres",
        (("gross", "", "brutto"),),
    ),
    _Chart(
        Dataset.WAGES,
        Frequency.YEAR,
        GUS,
        "gus-wynagrodzenia-roczne-wykres",
        (("gross", "", "brutto"), ("relative_to_poland", "", None)),
    ),
)
"""The datasets in chart specs, by the chart's ``id``."""

# [P 2026-10-31] tests/fixtures/rsc/stats_gov_7_miast_20261031.rsc: the aggregate lists the
# section `gus-bezrobocie` with a chart of one rate per city of the aggregate (its series are
# keyed by the cities' slugs) and no rate of its own: it does not publish the dataset.
CHARTS_WITHOUT_SERIES: Mapping[str, Dataset] = {
    "gus-bezrobocie-miasta-wykres": Dataset.UNEMPLOYMENT,
}
"""Charts that fill a dataset's section without a series of the location."""

READINGS: tuple[_Rows | _Chart, ...] = (*ROWS, *CHARTS)

# --- the page --------------------------------------------------------------------------------


class GovernmentStatsPageDto(Dto):
    """The data of ``/statystyki/{location}/dane-rzadowe`` (RSC).

    ``govSections`` (of the prop ``blocks``) and ``cityName`` are the page's; every row
    field holds the rows of a data prop recognized by its rows and ``charts`` the chart
    specs the client knows, by ``id`` (``None`` or absent: the page has no such data). Each
    is checked one dataset at a time (``_Rows.table``, ``_Chart.table``), so data off the
    contract makes only its own dataset unreadable.
    """

    govSections: list[str]
    cityName: str | None = None
    dwellings_quarterly: RawRows | None = None
    dwellings_monthly: RawRows | None = None
    population_yearly: RawRows | None = None
    nbp_quarterly: RawRows | None = None
    charts: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: str | bytes, *, path: str, location: LocationSlug) -> Self:
        """The sections, the location and the data of the page at ``path``, the page of
        ``location``.

        Raises ``NotFoundError`` for a page Next.js answers with ``notFound()`` and
        ``UnexpectedResponseError`` for a page without its list of sections, one that is
        about another location (``citySlug``), or one whose data props are ambiguous.
        """
        props = _PageProps(path)
        for name, value in component_props(payload):
            props.add(name, value)
        return Dto.validated(cls, props.data(payload, location), f"{path} (dane rządowe)")

    def to_model(
        self, location: LocationSlug, dataset: Dataset, *, path: str
    ) -> LocationStatistics:
        """Every dataset the page shows, as a table.

        A table that cannot be read fails only when it is ``dataset``'s (the port's
        contract: the other datasets do not matter for it), and so does a section of
        ``dataset`` the page lists without its data: ``UnexpectedResponseError``, with the
        page's ``path`` in its detail.
        """
        tables = self._tables(dataset, path)
        if dataset not in tables and self._shown_without_data(dataset, tables):
            raise UnexpectedResponseError(
                f"Serwis pokazuje zestaw {dataset.value!r}, ale jego dane są nieczytelne. "
                f"{SERVICE_CHANGED}",
                detail=f"{path}: sekcja {SECTIONS[dataset]} w govSections, brak jej danych",
            )
        return LocationStatistics(location=location, name=self._name(location), tables=tables)

    def _tables(self, dataset: Dataset, path: str) -> dict[Dataset, StatisticsTable]:
        tables: dict[Dataset, StatisticsTable] = {}
        for reading in READINGS:
            raw = reading.found(self)
            if raw is None:
                continue
            section = next((s for s in SECTIONS[reading.dataset] if s in self.govSections), None)
            try:
                tables[reading.dataset] = reading.table(raw, section, path)
            except UnexpectedResponseError:
                if reading.dataset is dataset:
                    raise
                # Another dataset of the page: the one asked for does not depend on it (the
                # port's contract; "isolation" in
                # tests/contract/api/adapters/test_government_statistics_api.py).
        return tables

    def _shown_without_data(
        self, dataset: Dataset, tables: Mapping[Dataset, StatisticsTable]
    ) -> bool:
        """The page lists a section of ``dataset``, and nothing it read explains it.

        ``gus-mieszkania`` is the section of both quarterly and monthly dwellings: a page
        with only one of them lists it for that one, so the other is not published there
        (the domain's ``NotFoundError``), not unreadable. [W] every page seen has both. A
        chart of ``CHARTS_WITHOUT_SERIES`` fills its section without the dataset.
        """
        shown = {section for section in SECTIONS[dataset] if section in self.govSections}
        explained = any(other is not dataset and shown & set(SECTIONS[other]) for other in tables)
        filled = any(CHARTS_WITHOUT_SERIES.get(chart) is dataset for chart in self.charts)
        return bool(shown) and not explained and not filled

    def _name(self, location: LocationSlug) -> str:
        if location.whole_country:
            return WHOLE_COUNTRY_NAME
        return (self.cityName or "").strip() or location.value


_READ_CHARTS: Mapping[str, Dataset] = {chart.chart_id: chart.dataset for chart in CHARTS}
_KNOWN_CHARTS: Mapping[str, Dataset] = {**_READ_CHARTS, **CHARTS_WITHOUT_SERIES}


class _PageProps:
    """The props of one page, collected in the order of its stream (``add``): the list of
    sections, each ``citySlug``, ``cityName``, the data props recognized by their rows
    (``STATS_SHAPES``) and the known charts; ``data`` checks them and gives the DTO's
    data."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._sections: list[Any] | None = None
        self._city_slugs: list[str] = []
        self._city_name: str | None = None
        self._rows: dict[str, list[Any]] = {}
        self._charts: dict[str, dict[str, Any]] = {}
        self._found: list[str] = []

    def add(self, name: str, value: Any) -> None:
        if isinstance(value, dict | list) and name not in self._found:
            self._found.append(name)
        if name == "blocks":
            self._add_sections(value)
        elif name in ("citySlug", "cityName"):
            self._add_city(name, value)
        elif name == "spec":
            self._add_chart(value)
        elif shape := self._shape(name, value):
            self._add_rows(shape, name, value)

    def data(self, payload: str | bytes, location: LocationSlug) -> dict[str, Any]:
        """The props under the DTO's field names, once the page proves to be the one of
        ``location`` (its ``payload`` tells a page Next.js does not know)."""
        if self._sections is None:
            raise self._without_sections(payload)
        self._check_location(location)
        return {
            "govSections": self._sections,
            "cityName": self._city_name,
            "charts": self._charts,
            **self._rows,
        }

    def _add_rows(self, shape: StatsShape, name: str, rows: list[Any]) -> None:
        """Rows of a shape; other rows of the same shape make the page ambiguous, the same
        ones again do not: [W] the stream may write a value out again instead of
        referencing it (the ``gus-prs`` section of ``polska`` gets ``monthlyData`` as a
        reference [P 2026-10-31])."""
        earlier = self._rows.get(shape.field)
        if earlier is not None and earlier != rows:
            raise self._ambiguous(f"dwa propsy z danymi {shape.field}: {name}")
        self._rows[shape.field] = rows

    # The props of the page's identity (`govSections`, `cityName`; `citySlug` in
    # `_check_location`) follow the policy of the rows and the charts above: the same value
    # again is no conflict, another value makes the page ambiguous, never a silent pick of
    # the first (the policy the round-2 review of the core sets for the plain values of
    # `RscPage.props`, which this page does not use: its several `data` and `spec` props
    # need a reader of their own).

    def _add_sections(self, blocks: Any) -> None:
        """The list ``govSections`` of a prop ``blocks`` [P 2026-10-31: one per page]."""
        sections = blocks.get("govSections") if isinstance(blocks, dict) else None
        if not isinstance(sections, list):
            return
        if self._sections is not None and sections != self._sections:
            raise self._ambiguous("dwie listy sekcji govSections")
        self._sections = sections

    def _add_city(self, name: str, value: Any) -> None:
        """Every ``citySlug`` (each must be the location's) and the ``cityName``."""
        if not _is_text(value):
            return
        if name == "citySlug":
            self._city_slugs.append(value)
            return
        if self._city_name is not None and value != self._city_name:
            raise self._ambiguous(f"dwie nazwy lokalizacji: {self._city_name!r}, {value!r}")
        self._city_name = value

    def _add_chart(self, spec: Any) -> None:
        """A chart the client knows (``_KNOWN_CHARTS``); the same id with other data, or
        another chart the client reads for the same dataset (``CHARTS``), makes the page
        ambiguous. Other charts are left out."""
        chart_id = spec.get("id") if isinstance(spec, dict) else None
        if not isinstance(chart_id, str) or chart_id not in _KNOWN_CHARTS:
            return
        earlier = self._charts.get(chart_id)
        if earlier is not None and earlier != spec:
            raise self._ambiguous(f"dwa wykresy {chart_id}")
        rival = self._rival(chart_id)
        if rival is not None:
            raise self._ambiguous(f"wykresy {chart_id} i {rival} jednego zestawu")
        self._charts[chart_id] = spec

    def _rival(self, chart_id: str) -> str | None:
        """Another chart the client reads (``CHARTS``) for the dataset of ``chart_id``."""
        dataset = _READ_CHARTS.get(chart_id)
        if dataset is None:
            return None
        others = (c for c in self._charts if c != chart_id and _READ_CHARTS.get(c) is dataset)
        return next(others, None)

    def _shape(self, name: str, value: Any) -> StatsShape | None:
        """The one shape whose keys every row of ``value`` has; ``None`` for anything else."""
        if not isinstance(value, list) or not value or not all(isinstance(r, dict) for r in value):
            return None
        shapes = [s for s in STATS_SHAPES if all(s.keys <= row.keys() for row in value)]
        if len(shapes) > 1:
            raise self._ambiguous(f"prop {name} pasuje do {[s.field for s in shapes]}")
        return shapes[0] if shapes else None

    def _without_sections(self, payload: str | bytes) -> NotFoundError | UnexpectedResponseError:
        """A page Next.js does not know (its 404 marker), or one that changed."""
        if NOT_FOUND_DIGEST in error_digests(payload):
            return NotFoundError(
                "Serwis nie zna żądanych danych (strona nie istnieje).",
                detail=(
                    f"{self._path}: brak propsa 'blocks.govSections', strona zgłasza "
                    f"{NOT_FOUND_DIGEST}"
                ),
            )
        names = ", ".join(self._found[:10]) or "brak"
        return UnexpectedResponseError(
            f"Na stronie serwisu brakuje oczekiwanych danych. {SERVICE_CHANGED}",
            detail=(
                f"{self._path} nie zawiera listy sekcji 'blocks.govSections' (propsy z "
                f"danymi: {names})"
            ),
        )

    def _check_location(self, location: LocationSlug) -> None:
        # [P 2026-10-31] `citySlug` is the requested location on the pages of `warszawa` and
        # `7-miast`; the page of `polska` has none. [W] the other cities and aggregates use
        # the template of these pages, so their `citySlug` is theirs (the live suite reads a
        # few). A page about another location (e.g. a fallback, [H]) is not this one's.
        allowed: set[str | None] = {location.value}
        if location.whole_country:
            allowed.add(None)
        found: list[str | None] = [*self._city_slugs] or [None]
        if any(slug not in allowed for slug in found):
            raise UnexpectedResponseError(
                f"Serwis zwrócił statystyki innej lokalizacji niż żądana. {SERVICE_CHANGED}",
                detail=(
                    f"{self._path}: citySlug {self._city_slugs!r}, oczekiwano {location.value!r}"
                ),
            )

    def _ambiguous(self, what: str) -> UnexpectedResponseError:
        return UnexpectedResponseError(
            f"Dane na stronie serwisu są niejednoznaczne. {SERVICE_CHANGED}",
            detail=f"{self._path}: {what}",
        )


def _is_text(value: object) -> bool:
    """A prop's text value: a string that is no reference of the stream (``$…``)."""
    return isinstance(value, str) and not value.startswith("$")
