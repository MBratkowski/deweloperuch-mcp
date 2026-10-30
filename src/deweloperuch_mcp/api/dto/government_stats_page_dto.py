"""``GovernmentStatsPageDto``: the data of ``/statystyki/statystyki-rzadowe/{location}``
(RSC) [P], since the 2.0 build (2026-10-29) ``/statystyki/{location}/dane-rzadowe``, read
from the page's props (``from_payload``) and mapped to the models (``to_model``,
``models.government_statistics``).

The 2.0 page [P 2026-10-30, live RSC payloads of the package client, ``wroclaw`` and
``polska``] keeps the ``data`` rows of the dwellings (quarterly; ``monthlyData`` monthly),
of the population and of NBP's prices, but shows the average area, the demography, the
unemployment and the wages only as chart specs (prop ``spec``: ``datasets`` of
``points`` ``{period, values}``); ``SPEC_ROWS`` turns those into rows of the old shapes.
Its table of contents is ``blocks.govSections`` (the same section ids), its location
``citySlug`` (absent on ``polska``) and its name ``cityName`` (kept as the one entry of
``sortedLocations``); there is no ``tocItems``, ``sortedLocations`` or ``currentSlug``.
The wages' ratio to the national average is only a note of each point
(``"108,3 % średniej krajowej"``) and is not read.

Several props of the page are called ``data``; they are told apart by the keys of their
rows (``STATS_SHAPES``) and kept under the field names of the DTO, which are this
client's own. Every shape is [P 2026-10-11] in the real payloads
(tests/fixtures/rsc/stats_gov_*.rsc); which locations have which shape is [W].

``to_model`` maps backend fields to series (``MAPPINGS``), period labels, sources and
the section of the page that shows each table (``SECTIONS``, the anchor of its link,
``links``). Names of the backend (``oddane``, ``tocItems``...) stay in ``api``.

Sections of the page (ids of its table of contents, [P 2026-10-11] in both fixtures,
``polska`` and ``warszawa``) tell a dataset the page does not have (``NotFoundError``
from the domain) from one it shows but whose data cannot be read: the latter means the
service changed (``UnexpectedResponseError``), not that the location lacks the data.
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
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
    StatisticsLocation,
    StatisticsTable,
    TimeSeries,
)
from deweloperuch_mcp.models.values import LocationSlug

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


class TocItemDto(Dto):
    """An entry of the page's table of contents (prop ``tocItems`` [P]): a section id."""

    id: str
    label: str | None = None


class StatsLocationDto(Dto):
    """A location of prop ``sortedLocations`` [P]; ``nbp`` is ``null`` for the cities NBP
    does not cover."""

    slug: str
    displayName: str
    isAggregate: bool = False
    nbp: dict[str, Any] | None = None

    def to_model(self) -> StatisticsLocation:
        return StatisticsLocation(
            slug=self.slug,
            name=self.displayName,
            is_aggregate=self.isAggregate,
            has_nbp_prices=self.nbp is not None,
        )


class StatsRowDto(Dto):
    """A row of a data prop; a table reads its columns by name (``_Mapping.columns``)."""

    def number(self, field: str) -> float | None:
        """The value of ``field`` as a number; ``None`` for no value."""
        value: int | float | str | None = getattr(self, field)
        return self._number(value)


class DwellingsCountsDto(StatsRowDto):
    """Dwellings completed (``oddane``) and started (``rozpoczete``) by form [P].

    The totals are the keys the rows are recognized by (``STATS_SHAPES``), so they
    are required; the forms may be missing (``None``): every form is [P] on both pages
    seen, [W] on the others, and a series without values is left out of the table.
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
    """A row of the first ``data`` prop: a quarter, the sum of its months [P]."""

    quarter: QuarterText


class DwellingsMonthDto(DwellingsCountsDto):
    """A row of prop ``monthlyData`` [P]."""

    month: MonthText


class AverageAreaYearDto(StatsRowDto):
    """Average usable area (m²) of what developers completed in a year [P]."""

    year: Year
    averageSizeM2: Number | None


class DemographyYearDto(StatsRowDto):
    """Live births, deaths, natural increase in a year: cities (GUS) [P warszawa]."""

    year: Year
    urodzenia: Number | None
    zgony: Number | None
    przyrostNaturalny: Number | None


class DemographyMonthDto(StatsRowDto):
    """The same per month: the whole country (section ``eurostat-demografia``) [P polska]."""

    month: MonthText
    urodzeniaZywe: Number | None
    zgony: Number | None
    przyrostNaturalny: Number | None


class PopulationYearDto(StatsRowDto):
    """Women and men on 31 December (the age pyramid's totals; its ``cohorts`` are not
    read) [P]: their sum is the population the page states."""

    year: Year
    totalKobiety: Number | None
    totalMezczyzni: Number | None


class UnemploymentMonthDto(StatsRowDto):
    """Registered unemployment rate (%) [P]."""

    month: MonthText
    rate: Number | None


class WagesMonthDto(StatsRowDto):
    """Average gross monthly wage (PLN) per month: the whole country [P polska]."""

    month: MonthText
    brutto: Number | None


class WagesYearDto(StatsRowDto):
    """The same per year, with the ratio to the national average (Poland = 100) [P
    warszawa]; whether every city has the ratio is [W], so it may be missing."""

    year: Year
    brutto: Number | None
    relacjaPolska: Number | None = None


class NbpQuarterDto(StatsRowDto):
    """NBP's average prices per m² (PLN), asking and transaction, primary and secondary
    market [P warszawa]; the whole country has no such series, only a grid of cities."""

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
    "average_area_yearly": AverageAreaYearDto,
    "demography_yearly": DemographyYearDto,
    "demography_monthly": DemographyMonthDto,
    "population_yearly": PopulationYearDto,
    "unemployment_monthly": UnemploymentMonthDto,
    "wages_monthly": WagesMonthDto,
    "wages_yearly": WagesYearDto,
    "nbp_quarterly": NbpQuarterDto,
}
"""The row of each data field of ``GovernmentStatsPageDto``."""

# --- telling the data props apart by their rows --------------------------------------------


@dataclass(frozen=True)
class StatsShape:
    """How rows of one kind of data prop look: every row has ``keys``.

    ``field``: where ``GovernmentStatsPageDto`` keeps them; ``group``: one table of the
    page (a page with two props of one group is ambiguous).
    """

    field: str
    group: str
    keys: frozenset[str]


def _shape(field: str, group: str, *keys: str) -> StatsShape:
    return StatsShape(field, group, frozenset(keys))


# [P 2026-10-11] tests/fixtures/rsc/stats_gov_polska.rsc and stats_gov_warszawa.rsc: the
# page has several props called `data`; each kind has keys no other kind has. A prop
# whose rows match none of these is not read (e.g. the NBP grid of cities on `polska`).
STATS_SHAPES = (
    _shape("dwellings_quarterly", "dwellings_quarterly", "quarter", "oddane", "rozpoczete"),
    _shape("dwellings_monthly", "dwellings_monthly", "month", "oddane", "rozpoczete"),
    _shape("average_area_yearly", "average_area", "year", "averageSizeM2"),
    _shape("demography_yearly", "demography", "year", "urodzenia", "zgony", "przyrostNaturalny"),
    _shape(
        "demography_monthly", "demography", "month", "urodzeniaZywe", "zgony", "przyrostNaturalny"
    ),
    _shape("population_yearly", "population", "year", "totalKobiety", "totalMezczyzni"),
    _shape("unemployment_monthly", "unemployment", "month", "rate"),
    _shape("wages_monthly", "wages", "month", "brutto"),
    _shape("wages_yearly", "wages", "year", "brutto"),
    _shape(
        "nbp_quarterly",
        "nbp",
        "quarter",
        "pierwotnyOfertowa",
        "pierwotnyTransakcyjna",
        "wtornyOfertowa",
        "wtornyTransakcyjna",
    ),
)

# [P 2026-10-30] the chart specs of the 2.0 page that carry a dataset with no `data` prop:
# spec id -> (the period key of its rows, {dataset key of the spec: {value key: row key}}).
# The rows merge the datasets by period, so they match `STATS_SHAPES` like the old props.
SPEC_ROWS: Mapping[str, tuple[str, Mapping[str, Mapping[str, str]]]] = {
    "gus-powierzchnia-wykres": ("year", {"": {"powierzchnia": "averageSizeM2"}}),
    "gus-demografia-wykres": (
        "year",
        {
            "ruch": {"urodzenia": "urodzenia", "zgony": "zgony"},
            "przyrost": {"przyrost": "przyrostNaturalny"},
        },
    ),
    "eurostat-demografia-wykres": (
        "month",
        {
            "ruch|mies": {"urodzenia": "urodzeniaZywe", "zgony": "zgony"},
            "przyrost|mies": {"przyrost": "przyrostNaturalny"},
        },
    ),
    # `miejsce` is the page's location; `polska` the country, for comparison.
    "gus-bezrobocie-wykres": ("month", {"": {"miejsce": "rate"}}),
    "gus-wynagrodzenia-wykres": ("month", {"": {"brutto": "brutto"}}),
    "gus-wynagrodzenia-roczne-wykres": ("year", {"": {"brutto": "brutto"}}),
}


def _spec_rows(spec: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    """The rows of a ``SPEC_ROWS`` chart spec, oldest period first; ``None`` for another
    spec or one without points."""
    known = SPEC_ROWS.get(str(spec.get("id")))
    datasets = spec.get("datasets")
    if known is None or not isinstance(datasets, dict):
        return None
    period_key, wanted = known
    keys = [key for columns in wanted.values() for key in columns.values()]
    rows: dict[str, dict[str, Any]] = {}
    for name, columns in wanted.items():
        for period, values in _spec_points(datasets.get(name)):
            row = rows.setdefault(period, dict.fromkeys(keys))
            row[period_key] = period
            row.update({row_key: values.get(value_key) for value_key, row_key in columns.items()})
    return [rows[period] for period in sorted(rows)] or None


def _spec_points(dataset: object) -> Iterator[tuple[str, Mapping[str, Any]]]:
    """``(period, values)`` of each point of a chart spec's dataset with both."""
    points = dataset.get("points") if isinstance(dataset, dict) else None
    for point in points if isinstance(points, list) else ():
        values = point.get("values") if isinstance(point, dict) else None
        if isinstance(values, dict) and isinstance(point.get("period"), str):
            yield point["period"], values


# --- the rows as series of the models --------------------------------------------------------

WHOLE_COUNTRY_NAME = "Polska"
"""``polska`` is not on the page's list of locations (it is the root page) [P]."""

# Sections of each dataset in the page's table of contents (the link's anchor): [P
# 2026-10-11]. `polska` shows its demography as `eurostat-demografia`, cities as
# `gus-demografia`; `polska` has `nbp-grid` (prices of every city), not `nbp`.
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
# [W] docs/discovery/pages-rsc.md: the monthly demography of `polska` sits in the section
# `eurostat-demografia`; the page's own text about it is rendered in the browser.
EUROSTAT = "Eurostat"

Value = Callable[[StatsRowDto], float | None]


@dataclass(frozen=True)
class _Mapping:
    """One kind of data prop -> one dataset: its period and series (id -> value)."""

    field: str
    dataset: Dataset
    frequency: Frequency
    source: str
    columns: Sequence[tuple[str, Value]]

    def table(self, raw_rows: Sequence[Any], section: str | None, path: str) -> StatisticsTable:
        """The rows as series, oldest period first; series without any value are left out
        (e.g. a ratio the page does not give, or a form the page does not list).

        Raises ``UnexpectedResponseError`` for rows off the contract or an inconsistent
        table: the caller decides whether that dataset was the one asked for.
        """
        rows = Dto.validated_rows(STATS_ROWS[self.field], raw_rows, f"{path} ({self.field})")
        series = self._series(sorted(rows, key=self._period))
        try:
            return StatisticsTable(
                dataset=self.dataset,
                frequency=self.frequency,
                source=self.source,
                series=series,
                section=section,
            )
        except ValueError as err:  # e.g. a period twice, or no values at all
            raise UnexpectedResponseError(
                f"Dane statystyk na stronie serwisu są niespójne. {SERVICE_CHANGED}",
                detail=f"{path} ({self.field}): {err}",
            ) from err

    def _series(self, ordered: Sequence[StatsRowDto]) -> tuple[TimeSeries, ...]:
        periods = [self._period(row) for row in ordered]
        definitions = {d.series_id: d for d in self.dataset.series}
        series = []
        for series_id, value in self.columns:
            points = tuple(
                SeriesPoint(period, value(row))
                for period, row in zip(periods, ordered, strict=True)
            )
            if any(point.value is not None for point in points):
                definition = definitions[series_id]
                series.append(TimeSeries(series_id, definition.label, definition.unit, points))
        return tuple(series)

    @staticmethod
    def _period(row: Any) -> str:
        for name in ("quarter", "month"):
            label = getattr(row, name, None)
            if isinstance(label, str):
                return label
        return str(row.year)


def _attr(name: str) -> Value:
    return lambda row: row.number(name)


def _sum(*names: str) -> Value:
    """The sum of ``names``; ``None`` when any of them is missing."""

    def total(row: StatsRowDto) -> float | None:
        values = [row.number(name) for name in names]
        present = [value for value in values if value is not None]
        return sum(present) if len(present) == len(values) else None

    return total


_FORMS = (
    ("developer", "Deweloperskie"),
    ("individual", "Indywidualne"),
    ("cooperative", "Spoldzielcze"),
    ("municipal", "Komunalne"),
    ("social", "Spoleczne"),
    ("company", "Zakladowe"),
)
_DWELLINGS: Sequence[tuple[str, Value]] = (
    ("completed_total", _attr("oddane")),
    *((f"completed_{key}", _attr(f"oddane{name}")) for key, name in _FORMS),
    ("started_total", _attr("rozpoczete")),
    *((f"started_{key}", _attr(f"rozpoczete{name}")) for key, name in _FORMS),
    ("started_for_rent", _attr("rozpoczeteNaWynajem")),
)
_DEMOGRAPHY_REST: Sequence[tuple[str, Value]] = (
    ("deaths", _attr("zgony")),
    ("natural_increase", _attr("przyrostNaturalny")),
)

MAPPINGS = (
    _Mapping(
        "dwellings_quarterly", Dataset.DWELLINGS_QUARTERLY, Frequency.QUARTER, GUS, _DWELLINGS
    ),
    _Mapping("dwellings_monthly", Dataset.DWELLINGS_MONTHLY, Frequency.MONTH, GUS, _DWELLINGS),
    _Mapping(
        "average_area_yearly",
        Dataset.AVERAGE_AREA,
        Frequency.YEAR,
        GUS,
        (("average_area", _attr("averageSizeM2")),),
    ),
    _Mapping(
        "demography_yearly",
        Dataset.DEMOGRAPHY,
        Frequency.YEAR,
        GUS,
        (("births", _attr("urodzenia")), *_DEMOGRAPHY_REST),
    ),
    _Mapping(
        "demography_monthly",
        Dataset.DEMOGRAPHY,
        Frequency.MONTH,
        EUROSTAT,
        (("births", _attr("urodzeniaZywe")), *_DEMOGRAPHY_REST),
    ),
    _Mapping(
        "population_yearly",
        Dataset.POPULATION,
        Frequency.YEAR,
        GUS,
        (
            # [P 2026-10-11] the page states the population as this sum (2025: 37 332 510
            # for polska, 1 866 729 for warszawa).
            ("total", _sum("totalKobiety", "totalMezczyzni")),
            ("women", _attr("totalKobiety")),
            ("men", _attr("totalMezczyzni")),
        ),
    ),
    _Mapping(
        "unemployment_monthly",
        Dataset.UNEMPLOYMENT,
        Frequency.MONTH,
        GUS,
        (("rate", _attr("rate")),),
    ),
    _Mapping("wages_monthly", Dataset.WAGES, Frequency.MONTH, GUS, (("gross", _attr("brutto")),)),
    _Mapping(
        "wages_yearly",
        Dataset.WAGES,
        Frequency.YEAR,
        GUS,
        (("gross", _attr("brutto")), ("relative_to_poland", _attr("relacjaPolska"))),
    ),
    _Mapping(
        "nbp_quarterly",
        Dataset.NBP_PRICES,
        Frequency.QUARTER,
        NBP,
        (
            ("primary_asking", _attr("pierwotnyOfertowa")),
            ("primary_transaction", _attr("pierwotnyTransakcyjna")),
            ("secondary_asking", _attr("wtornyOfertowa")),
            ("secondary_transaction", _attr("wtornyTransakcyjna")),
        ),
    ),
)

# --- the page --------------------------------------------------------------------------------

STATS_WHOLE_COUNTRY = "polska"
"""The location of the root page of these statistics; its ``currentSlug`` is ``null`` [P]."""


class GovernmentStatsPageDto(Dto):
    """The data of ``/statystyki/statystyki-rzadowe/{location}`` (RSC).

    ``tocItems`` and ``sortedLocations`` are the page's props, checked here; every other
    field holds the rows of a data prop recognized by its rows (``None``: the page has no
    such prop), checked one dataset at a time (``validate_rows`` with ``STATS_ROWS``), so
    rows that do not match the contract make only their own dataset unreadable.
    """

    tocItems: list[TocItemDto]
    sortedLocations: list[StatsLocationDto] = Field(default_factory=list)
    dwellings_quarterly: RawRows | None = None
    dwellings_monthly: RawRows | None = None
    average_area_yearly: RawRows | None = None
    demography_yearly: RawRows | None = None
    demography_monthly: RawRows | None = None
    population_yearly: RawRows | None = None
    unemployment_monthly: RawRows | None = None
    wages_monthly: RawRows | None = None
    wages_yearly: RawRows | None = None
    nbp_quarterly: RawRows | None = None

    @classmethod
    def from_payload(cls, payload: str | bytes, *, path: str, location: str) -> Self:
        """The table of contents, the list of locations and every data prop of the page at
        ``path``, the page of ``location``.

        Raises ``NotFoundError`` for a page Next.js answers with ``notFound()`` and
        ``UnexpectedResponseError`` for a page without the table of contents, one that is
        about another location (``currentSlug``), or one whose data props are ambiguous.
        """
        props = _PageProps(path)
        for name, value in component_props(payload):
            props.add(name, value)
        return Dto.validated(cls, props.data(payload, location), f"{path} (statystyki rządowe)")

    def to_model(
        self, location: LocationSlug, dataset: Dataset, *, path: str
    ) -> LocationStatistics:
        """Every dataset the page shows, as a table, with the page's list of locations.

        A table that cannot be read fails only when it is ``dataset``'s (the port's
        contract: the other datasets do not matter for it), and so does a section of
        ``dataset`` the page lists without its data: ``UnexpectedResponseError``, with the
        page's ``path`` in its detail.
        """
        sections = [item.id for item in self.tocItems]
        tables = self._tables(dataset, sections, path)
        if dataset not in tables and self._shown_without_data(dataset, sections, tables):
            raise UnexpectedResponseError(
                f"Serwis pokazuje zestaw {dataset.value!r}, ale jego dane są nieczytelne. "
                f"{SERVICE_CHANGED}",
                detail=f"{path}: sekcja {SECTIONS[dataset]} w tocItems, brak propsa z danymi",
            )
        return LocationStatistics(
            location=location,
            name=self._name(location),
            tables=tables,
            locations=tuple(item.to_model() for item in self.sortedLocations),
        )

    def _tables(
        self, dataset: Dataset, sections: Sequence[str], path: str
    ) -> dict[Dataset, StatisticsTable]:
        tables: dict[Dataset, StatisticsTable] = {}
        for mapping in MAPPINGS:
            rows = getattr(self, mapping.field)
            if rows is None:
                continue
            section = next((s for s in SECTIONS[mapping.dataset] if s in sections), None)
            try:
                tables[mapping.dataset] = mapping.table(rows, section, path)
            except UnexpectedResponseError:
                if mapping.dataset is dataset:
                    raise
                # Another dataset of the page: the one asked for does not depend on it (the
                # port's contract; "isolation" in
                # tests/contract/api/adapters/test_government_statistics_api.py).
        return tables

    @staticmethod
    def _shown_without_data(
        dataset: Dataset, sections: Sequence[str], tables: Mapping[Dataset, StatisticsTable]
    ) -> bool:
        """The page lists a section of ``dataset``, and no dataset it read explains it.

        ``gus-mieszkania`` is the section of both quarterly and monthly dwellings: a page
        with only one of them lists it for that one, so the other is not published there
        (the domain's ``NotFoundError``), not unreadable. [W] every page seen has both.
        """
        shown = {section for section in SECTIONS[dataset] if section in sections}
        explained = any(other is not dataset and shown & set(SECTIONS[other]) for other in tables)
        return bool(shown) and not explained

    def _name(self, location: LocationSlug) -> str:
        if location.whole_country:
            return WHOLE_COUNTRY_NAME
        listed = (item.displayName for item in self.sortedLocations if item.slug == location.value)
        return next(listed, location.value)


class _PageProps:
    """The props of one page, collected in the order of its stream (``add``): the table of
    contents, the list of locations, each ``currentSlug``, and the data props recognized by
    their rows (``STATS_SHAPES``); ``data`` checks them and gives the DTO's data."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._toc: list[Any] | None = None
        self._locations: list[Any] | None = None
        self._current: list[object] = []
        self._sections: list[Any] | None = None
        self._city_slugs: list[str] = []
        self._city_name: str | None = None
        self._spec_tables: dict[str, list[Any]] = {}
        self._tables: dict[str, list[Any]] = {}
        self._groups: dict[str, str] = {}
        self._found: list[str] = []

    def add(self, name: str, value: Any) -> None:
        if isinstance(value, dict | list) and name not in self._found:
            self._found.append(name)
        if name == "tocItems" and isinstance(value, list) and self._toc is None:
            self._toc = value
        elif name == "sortedLocations" and isinstance(value, list) and self._locations is None:
            self._locations = value
        elif name == "currentSlug" and (value is None or isinstance(value, str)):
            self._current.append(value)
        elif self._add_2_0(name, value):
            return
        elif shape := self._shape(name, value):
            self._add_rows(shape, name, value)

    def _add_2_0(self, name: str, value: Any) -> bool:
        """A prop of the 2.0 page (sections, location, name, chart spec): ``True`` when
        ``name`` and ``value`` are one."""
        if name == "blocks" and isinstance(value, dict):
            sections = value.get("govSections")
            if self._sections is None and isinstance(sections, list):
                self._sections = sections
        elif name == "spec" and isinstance(value, dict):
            self._add_spec(value)
        elif name in ("citySlug", "cityName") and isinstance(value, str):
            self._add_location(name, value)
        else:
            return False
        return True

    def _add_location(self, name: str, value: str) -> None:
        if name == "citySlug":
            self._city_slugs.append(value)
        else:
            self._city_name = self._city_name or value

    def data(self, payload: str | bytes, location: str) -> dict[str, Any]:
        """The props under the DTO's field names, once the page proves to be the one of
        ``location`` (its ``payload`` tells a page Next.js does not know)."""
        if self._toc is None and self._sections is not None:
            return self._data_2_0(location)
        if self._toc is None:
            raise self._without_toc(payload)
        self._check_location(location)
        data: dict[str, Any] = {"tocItems": self._toc, **self._tables}
        if self._locations is not None:
            data["sortedLocations"] = self._locations
        return data

    def _data_2_0(self, location: str) -> dict[str, Any]:
        """The data of the 2.0 page: the sections of ``blocks.govSections``, the ``data``
        props and, for a dataset without one, its chart spec (``SPEC_ROWS``)."""
        # [P 2026-10-30] `citySlug` is the requested city (wroclaw); `polska` has none.
        self._current = list(self._city_slugs) or [None]
        self._check_location(location)
        tables = {**self._spec_tables_without_data(), **self._tables}
        toc = [{"id": section} for section in self._sections or () if isinstance(section, str)]
        data: dict[str, Any] = {"tocItems": toc, **tables}
        if self._city_name is not None and location != STATS_WHOLE_COUNTRY:
            data["sortedLocations"] = [self._own_location(location, "nbp_quarterly" in tables)]
        return data

    def _spec_tables_without_data(self) -> dict[str, list[Any]]:
        """The tables of the chart specs whose dataset has no ``data`` prop on the page."""
        groups = {shape.field: shape.group for shape in STATS_SHAPES}
        return {
            field: rows
            for field, rows in self._spec_tables.items()
            if groups[field] not in self._groups
        }

    def _own_location(self, location: str, with_nbp: bool) -> dict[str, Any]:
        """The page's location as the one entry of ``sortedLocations``: the 2.0 page lists
        no other locations."""
        nbp: dict[str, Any] | None = {} if with_nbp else None
        return {"slug": location, "displayName": self._city_name, "nbp": nbp}

    def _add_spec(self, spec: Mapping[str, Any]) -> None:
        rows = _spec_rows(spec)
        shape = self._shape("spec", rows) if rows else None
        if rows and shape is not None and shape.field not in self._spec_tables:
            self._spec_tables[shape.field] = rows

    def _add_rows(self, shape: StatsShape, name: str, rows: list[Any]) -> None:
        if shape.group in self._groups:
            raise self._ambiguous(f"dwa propsy z danymi {shape.group}: {name}, {self._groups}")
        self._groups[shape.group] = name
        self._tables[shape.field] = rows

    def _shape(self, name: str, value: Any) -> StatsShape | None:
        """The one shape whose keys every row of ``value`` has; ``None`` for anything else."""
        if not isinstance(value, list) or not value or not all(isinstance(r, dict) for r in value):
            return None
        shapes = [s for s in STATS_SHAPES if all(s.keys <= row.keys() for row in value)]
        if len(shapes) > 1:
            raise self._ambiguous(f"prop {name} pasuje do {[s.field for s in shapes]}")
        return shapes[0] if shapes else None

    def _without_toc(self, payload: str | bytes) -> NotFoundError | UnexpectedResponseError:
        """A page Next.js does not know (its 404 marker), or one that changed."""
        if NOT_FOUND_DIGEST in error_digests(payload):
            return NotFoundError(
                "Serwis nie zna żądanych danych (strona nie istnieje).",
                detail=f"{self._path}: brak propsa 'tocItems', strona zgłasza {NOT_FOUND_DIGEST}",
            )
        names = ", ".join(self._found[:10]) or "brak"
        return UnexpectedResponseError(
            f"Na stronie serwisu brakuje oczekiwanych danych. {SERVICE_CHANGED}",
            detail=f"{self._path} nie zawiera spisu treści 'tocItems' (propsy z danymi: {names})",
        )

    def _check_location(self, location: str) -> None:
        # [P 2026-10-11] `currentSlug` is the requested city (warszawa) or null (polska). A
        # page about another location (e.g. a fallback for an unknown one, [H]) is not this
        # one's.
        expected = None if location == STATS_WHOLE_COUNTRY else location
        if not self._current or any(slug != expected for slug in self._current):
            raise UnexpectedResponseError(
                f"Serwis zwrócił statystyki innej lokalizacji niż żądana. {SERVICE_CHANGED}",
                detail=f"{self._path}: currentSlug {self._current!r}, oczekiwano {expected!r}",
            )

    def _ambiguous(self, what: str) -> UnexpectedResponseError:
        return UnexpectedResponseError(
            f"Dane na stronie serwisu są niejednoznaczne. {SERVICE_CHANGED}",
            detail=f"{self._path}: {what}",
        )
