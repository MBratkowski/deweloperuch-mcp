"""The government statistics port (``domain.ports.GovernmentStatisticsSource``) over the
page ``/statystyki/statystyki-rzadowe/{location}`` (RSC, D1; D13: infrastructure).

The page's props are read by ``rsc.government_stats``; this adapter maps them to the
domain (``domain.statistics``): backend field -> series, period labels, sources, the
section of the page that shows each table (the anchor of its link, ``links``). Names of
the backend (``oddane``, ``tocItems``...) stay in the infrastructure.

Sections of the page (ids of its table of contents, [P 2026-10-11] in both fixtures,
``polska`` and ``warszawa``) tell a dataset the page does not have (``NotFoundError``
from the domain) from one it shows but whose data cannot be read: the latter means the
service changed (``UnexpectedResponseError``), not that the location lacks the data.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from deweloperuch_mcp.domain.errors import SERVICE_CHANGED, UnexpectedResponseError
from deweloperuch_mcp.domain.statistics import (
    Dataset,
    Frequency,
    LocationStatistics,
    SeriesPoint,
    StatisticsLocation,
    StatisticsTable,
    TimeSeries,
)
from deweloperuch_mcp.domain.values import LocationSlug
from deweloperuch_mcp.infrastructure.deweloperuch import rsc
from deweloperuch_mcp.infrastructure.deweloperuch.dto import (
    STATS_ROWS,
    GovernmentStatsPageDto,
    validate_rows,
)
from deweloperuch_mcp.infrastructure.deweloperuch.transport import HttpClient

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

Value = Callable[[Any], int | float | str | None]


@dataclass(frozen=True)
class _Mapping:
    """One kind of data prop -> one dataset: its period and series (id -> value)."""

    field: str
    dataset: Dataset
    frequency: Frequency
    source: str
    columns: Sequence[tuple[str, Value]]


def _attr(name: str) -> Value:
    return lambda row: getattr(row, name)


def _sum(*names: str) -> Value:
    """The sum of ``names``; ``None`` when any of them is missing."""

    def total(row: Any) -> float | None:
        values = [_number(getattr(row, name)) for name in names]
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


class GovernmentStatisticsAdapter:
    """``GovernmentStatisticsSource`` of deweloperuch.pl: one page request per location
    (the transport's cache answers the next datasets of the same location)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def location_statistics(self, location: LocationSlug, dataset: Dataset) -> LocationStatistics:
        page = rsc.government_stats(self._http, location.value)
        path = rsc.government_stats_path(location.value)
        sections = [item.id for item in page.tocItems]
        tables: dict[Dataset, StatisticsTable] = {}
        for mapping in MAPPINGS:
            rows = getattr(page, mapping.field)
            if rows is None:
                continue
            section = next((s for s in SECTIONS[mapping.dataset] if s in sections), None)
            try:
                tables[mapping.dataset] = _table(path, mapping, rows, section)
            except UnexpectedResponseError:
                if mapping.dataset is dataset:
                    raise
                # Another dataset of the page: the one asked for does not depend on it
                # (the port's contract; tests/test_client_statistics.py, "isolation").
        if dataset not in tables and _shown_without_data(dataset, sections, tables):
            raise UnexpectedResponseError(
                f"Serwis pokazuje zestaw {dataset.value!r}, ale jego dane są nieczytelne. "
                f"{SERVICE_CHANGED}",
                detail=f"{path}: sekcja {SECTIONS[dataset]} w tocItems, brak propsa z danymi",
            )
        return LocationStatistics(
            location=location,
            name=_name(page, location),
            tables=tables,
            locations=tuple(
                StatisticsLocation(
                    slug=item.slug,
                    name=item.displayName,
                    is_aggregate=item.isAggregate,
                    has_nbp_prices=item.nbp is not None,
                )
                for item in page.sortedLocations
            ),
        )


def _shown_without_data(
    dataset: Dataset, sections: Sequence[str], tables: Mapping[Dataset, StatisticsTable]
) -> bool:
    """The page lists a section of ``dataset``, and no dataset it read explains it.

    ``gus-mieszkania`` is the section of both quarterly and monthly dwellings: a page with
    only one of them lists it for that one, so the other is not published there (the
    domain's ``NotFoundError``), not unreadable. [W] every page seen has both.
    """
    shown = {section for section in SECTIONS[dataset] if section in sections}
    explained = any(other is not dataset and shown & set(SECTIONS[other]) for other in tables)
    return bool(shown) and not explained


def _name(page: GovernmentStatsPageDto, location: LocationSlug) -> str:
    if location.whole_country:
        return WHOLE_COUNTRY_NAME
    listed = (item.displayName for item in page.sortedLocations if item.slug == location.value)
    return next(listed, location.value)


def _table(
    path: str, mapping: _Mapping, raw_rows: Sequence[Any], section: str | None
) -> StatisticsTable:
    """The rows as series, oldest period first; series without any value are left out
    (e.g. a ratio the page does not give, or a form the page does not list).

    Raises ``UnexpectedResponseError`` for rows off the contract or an inconsistent
    table: the caller decides whether that dataset was the one asked for.
    """
    rows = validate_rows(STATS_ROWS[mapping.field], raw_rows, f"{path} ({mapping.field})")
    ordered = sorted(rows, key=_period)
    periods = [_period(row) for row in ordered]
    series = []
    definitions = {d.series_id: d for d in mapping.dataset.series}
    for series_id, value in mapping.columns:
        points = tuple(
            SeriesPoint(period, _number(value(row)))
            for period, row in zip(periods, ordered, strict=True)
        )
        if any(point.value is not None for point in points):
            definition = definitions[series_id]
            series.append(TimeSeries(series_id, definition.label, definition.unit, points))
    try:
        return StatisticsTable(
            dataset=mapping.dataset,
            frequency=mapping.frequency,
            source=mapping.source,
            series=tuple(series),
            section=section,
        )
    except ValueError as err:  # e.g. a period twice, or no values at all
        raise UnexpectedResponseError(
            f"Dane statystyk na stronie serwisu są niespójne. {SERVICE_CHANGED}",
            detail=f"{path} ({mapping.field}): {err}",
        ) from err


def _period(row: Any) -> str:
    for name in ("quarter", "month"):
        label = getattr(row, name, None)
        if isinstance(label, str):
            return label
    return str(row.year)


def _number(value: int | float | str | None) -> float | None:
    """``3611``, ``"62.5"`` -> float; ``""`` and ``None`` -> ``None`` (DTOs checked them)."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    return float(value)
