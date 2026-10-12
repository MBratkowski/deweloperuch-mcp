"""DTOs of the service's responses: the backend's JSON 1:1, tolerant to how values are typed.

Field names and nesting are the backend's (``invest``, ``sale``, ``cityMappings``...);
the domain renames them (D3). Values are kept as sent: amounts and coordinates come as
numbers or numeric strings depending on the endpoint, dates as ``YYYY-MM-DD`` or ISO
datetimes, missing text as ``""`` (docs/discovery/entities.md, "Normalizacja"). The DTO
only checks that such a value can be normalized (``Number``, ``DateText``), so the
domain's conversion never fails; ``infrastructure.deweloperuch.mappers`` converts them.

Unknown fields are ignored (the backend may add some). Fields the domain relies on are
required, so a renamed or removed field fails the contract tests instead of turning
into silent ``None``. Every model is immutable: the client caches response bodies, not
DTOs, but nothing should mutate a parsed response anyway.
"""

import math
import re
from collections.abc import Mapping
from datetime import date, datetime
from functools import cache
from typing import Annotated, Any, TypeVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    RootModel,
    TypeAdapter,
    ValidationError,
)

from deweloperuch_mcp.domain.errors import SERVICE_CHANGED, UnexpectedResponseError

M = TypeVar("M", bound=BaseModel)

_NUMERIC_TEXT = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_DATE_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}")
_DATETIME_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}T.+")


def _check_number(value: object) -> object:
    """A finite number, a numeric string or ``""``, returned unchanged."""
    if isinstance(value, bool):
        raise ValueError("oczekiwano liczby, a nie wartości logicznej")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("oczekiwano skończonej liczby")
        return value
    if isinstance(value, str):
        text = value.strip()
        # isfinite: "1e999" is numeric text, but float() makes it inf.
        if text and not (_NUMERIC_TEXT.fullmatch(text) and math.isfinite(float(text))):
            raise ValueError(f"oczekiwano skończonej liczby albo pustego tekstu, podano {value!r}")
        return value
    raise ValueError(f"oczekiwano liczby albo tekstu z liczbą, podano {type(value).__name__}")


def _check_date(value: object) -> object:
    """``YYYY-MM-DD``, an ISO datetime (``2025-02-25T00:00:00.000Z``) or ``""``, unchanged."""
    if not isinstance(value, str):
        raise ValueError(f"oczekiwano daty jako tekstu, podano {type(value).__name__}")
    text = value.strip()
    if not text:
        return value
    if _DATE_TEXT.fullmatch(text):
        date.fromisoformat(text)  # ValueError for 2026-13-01
    elif _DATETIME_TEXT.fullmatch(text):
        datetime.fromisoformat(text)
    else:
        raise ValueError(f"oczekiwano daty YYYY-MM-DD albo ISO 8601, podano {value!r}")
    return value


Number = Annotated[int | float | str, BeforeValidator(_check_number)]
"""A number as the backend sends it: ``994012``, ``"994012"``, ``"55.25"`` or ``""``."""

DateText = Annotated[str, BeforeValidator(_check_date)]
"""A date as the backend sends it: ``"2026-10-03"``, ``"2025-02-25T00:00:00.000Z"``, ``""``."""


class Dto(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


def validate(model: type[M], data: Any, source: str) -> M:
    """``data`` as ``model``; a mismatch is an ``UnexpectedResponseError``.

    ``source`` (where the data came from) and the problems go to its ``detail``.
    """
    try:
        return model.model_validate(data)
    except ValidationError as err:
        raise _mismatch(err, source) from err


def _mismatch(err: ValidationError, source: str) -> UnexpectedResponseError:
    problems = "; ".join(
        f"{'.'.join(str(part) for part in e['loc']) or '(całość)'}: {e['msg']}"
        for e in err.errors()[:3]
    )
    more = f" (i {err.error_count() - 3} innych)" if err.error_count() > 3 else ""
    return UnexpectedResponseError(
        f"Dane z serwisu nie pasują do kontraktu klienta (inny format). {SERVICE_CHANGED}",
        detail=f"{source}: {problems}{more}",
    )


# --- locations: GET /api/cities, /api/location-search, /api/city-lookup, /api/city-districts


class CityMappingDto(Dto):
    city: str
    city_slug: str
    offerCount: int


class CitiesDto(Dto):
    """``GET /api/cities?q=&limit=`` [P] (sample ``api.cities_q``)."""

    cities: list[str] = Field(default_factory=list)
    cityMappings: list[CityMappingDto]
    hasMore: bool = False
    total: int | None = None
    page: int | None = None


class LocationSuggestionDto(Dto):
    kind: str
    city: str
    citySlug: str
    district: str | None = None
    street: str | None = None
    count: int | None = None
    lat: Number | None = None
    lng: Number | None = None


class LocationSearchDto(Dto):
    """``GET /api/location-search?q=&limit=`` [P] (sample ``api.location_search``)."""

    suggestions: list[LocationSuggestionDto]


class CityLookupDto(Dto):
    """``GET /api/city-lookup?city=`` [P] (sample ``api.city_lookup``)."""

    city: str
    city_slug: str


class DistrictDto(Dto):
    name: str
    count: int


class CityDistrictsDto(Dto):
    """``GET /api/city-districts?citySlug=`` [P] (sample ``api.city_districts``)."""

    districts: list[DistrictDto]


# --- investments and offers: GET /api/map/investments/visible/{slug} and sale events -----


class DeveloperDto(Dto):
    developer_id: int | None = None
    name: str
    slug: str
    description: str | None = None
    website: str | None = None


class InvestmentSaleDto(Dto):
    """One offer (``sale``) of ``InvestmentDto``; amounts and size as strings [P]."""

    sale_id: int
    invest_id: int | None = None
    name: str
    type: str | None = None
    status: str
    amount: Number | None
    currency: str | None = None
    size: Number | None
    start_amount_difference: Number | None = None
    start_amount_difference_percent: Number | None = None
    last_event_date: DateText | None = None
    last_change_event_date: DateText | None = None
    creation_date: DateText | None = None


class InvestmentDto(Dto):
    """``GET /api/map/investments/visible/{slug}`` [P] (sample ``api.map_inv_visible``)."""

    invest_id: int
    developer_id: int | None = None
    city: str
    city_slug: str
    street: str | None = None
    latitude: Number | None = None
    longitude: Number | None = None
    name: str
    slug: str
    status: str
    currency: str | None = None
    avg_amount: Number | None = None
    avg_size: Number | None = None
    avg_price_sqm: Number | None = None
    avg_amount_archived: Number | None = None
    avg_size_archived: Number | None = None
    avg_price_sqm_archived: Number | None = None
    avg_amount_total: Number | None = None
    avg_size_total: Number | None = None
    avg_price_sqm_total: Number | None = None
    active_offers: int | None = None
    total_offers: int | None = None
    developer: DeveloperDto
    sale: list[InvestmentSaleDto]


class SaleEventDto(Dto):
    sale_event_id: int
    event_type: str
    event_data: str | None = None
    amount: Number | None
    event_date: DateText
    source: str | None = None


class InvestmentSaleEventsDto(RootModel[dict[int, list[SaleEventDto]]]):
    """``GET /api/investments/{investId}/sale-events`` [P]: offer id -> its events
    (sample ``api.inv_sale_events``)."""

    model_config = ConfigDict(frozen=True)


class SaleDataDto(Dto):
    name: str | None = None
    amount: Number | None = None
    size: Number | None = None
    currency: str | None = None


class SaleEventsDto(Dto):
    """``GET /api/sale-events?saleId=`` [P] (sample ``api.sale_events``)."""

    success: bool | None = None
    saleData: SaleDataDto | None = None
    events: list[SaleEventDto]


# --- the offers list page: /ceny-ofertowe/{city}/mieszkania, prop initialData (RSC) ------


class SaleListInvestDto(Dto):
    invest_id: int | None = None
    name: str
    city: str | None = None
    city_slug: str | None = None
    slug: str
    developer: DeveloperDto


class SaleListItemDto(Dto):
    sale_id: int
    name: str
    amount: Number | None
    start_amount_difference: Number | None = None
    start_amount_difference_percent: Number | None = None
    last_amount_difference: Number | None = None
    last_amount_difference_percent: Number | None = None
    last_event_type: str | None = None
    total_events: int | None = None
    currency: str | None = None
    size: Number | None
    status: str
    last_event_date: DateText | None = None
    last_change_event_date: DateText | None = None
    creation_date: DateText | None = None
    invest: SaleListInvestDto


class PaginationDto(Dto):
    page: int
    perPage: int
    total: int
    totalPages: int | None = None


class OffersPageDto(Dto):
    """Prop ``initialData`` of ``/ceny-ofertowe/{city}/mieszkania`` [P]
    (samples ``page.offers_list``, ``page.offers_list.filtered``)."""

    data: list[SaleListItemDto]
    pagination: PaginationDto


# --- government statistics: /statystyki/statystyki-rzadowe/{location} (RSC) --------------
#
# Several props of the page are called `data`; the RSC adapter tells them apart by the
# keys of their rows (``rsc.STATS_SHAPES``) and hands them over under the field names
# below, which are this client's own. Every shape is [P 2026-10-11] in the real payloads
# (tests/fixtures/rsc/stats_gov_*.rsc); which locations have which shape is [W].

_QUARTER_TEXT = re.compile(r"\d{4}-Q[1-4]")
_MONTH_TEXT = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])")
YEAR_MIN, YEAR_MAX = 1900, 2200


def _period_text(pattern: re.Pattern[str], example: str) -> Any:
    def check(value: object) -> str:
        text = value.strip() if isinstance(value, str) else None
        if text is None or not pattern.fullmatch(text):
            raise ValueError(f"oczekiwano okresu w postaci {example}, podano {value!r}")
        return text

    return BeforeValidator(check)


def _check_year(value: object) -> int:
    """``2025`` or ``"2025"`` -> 2025, within ``YEAR_MIN``..``YEAR_MAX``."""
    if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or not YEAR_MIN <= value <= YEAR_MAX:
        raise ValueError(f"oczekiwano roku {YEAR_MIN}–{YEAR_MAX}, podano {value!r}")
    return value


QuarterText = Annotated[str, _period_text(_QUARTER_TEXT, "2025-Q3")]
MonthText = Annotated[str, _period_text(_MONTH_TEXT, "2025-08")]
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


class DwellingsCountsDto(Dto):
    """Dwellings completed (``oddane``) and started (``rozpoczete``) by form [P].

    The totals are the keys the rows are recognized by (``rsc.STATS_SHAPES``), so they
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


class AverageAreaYearDto(Dto):
    """Average usable area (m²) of what developers completed in a year [P]."""

    year: Year
    averageSizeM2: Number | None


class DemographyYearDto(Dto):
    """Live births, deaths, natural increase in a year: cities (GUS) [P warszawa]."""

    year: Year
    urodzenia: Number | None
    zgony: Number | None
    przyrostNaturalny: Number | None


class DemographyMonthDto(Dto):
    """The same per month: the whole country (section ``eurostat-demografia``) [P polska]."""

    month: MonthText
    urodzeniaZywe: Number | None
    zgony: Number | None
    przyrostNaturalny: Number | None


class PopulationYearDto(Dto):
    """Women and men on 31 December (the age pyramid's totals; its ``cohorts`` are not
    read) [P]: their sum is the population the page states."""

    year: Year
    totalKobiety: Number | None
    totalMezczyzni: Number | None


class UnemploymentMonthDto(Dto):
    """Registered unemployment rate (%) [P]."""

    month: MonthText
    rate: Number | None


class WagesMonthDto(Dto):
    """Average gross monthly wage (PLN) per month: the whole country [P polska]."""

    month: MonthText
    brutto: Number | None


class WagesYearDto(Dto):
    """The same per year, with the ratio to the national average (Poland = 100) [P
    warszawa]; whether every city has the ratio is [W], so it may be missing."""

    year: Year
    brutto: Number | None
    relacjaPolska: Number | None = None


class NbpQuarterDto(Dto):
    """NBP's average prices per m² (PLN), asking and transaction, primary and secondary
    market [P warszawa]; the whole country has no such series, only a grid of cities."""

    quarter: QuarterText
    pierwotnyOfertowa: Number | None
    pierwotnyTransakcyjna: Number | None
    wtornyOfertowa: Number | None
    wtornyTransakcyjna: Number | None


RawRows = list[dict[str, Any]]
"""The rows of one data prop as the page has them; ``STATS_ROWS`` checks them."""


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


STATS_ROWS: Mapping[str, type[Dto]] = {
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


@cache
def _rows_of(model: type[M]) -> TypeAdapter[list[M]]:
    return TypeAdapter(list[model])  # type: ignore[valid-type]


def validate_rows(model: type[M], rows: Any, source: str) -> list[M]:
    """``rows`` as a list of ``model``; a mismatch is an ``UnexpectedResponseError``
    (``validate``'s message and detail)."""
    try:
        return _rows_of(model).validate_python(rows)
    except ValidationError as err:
        raise _mismatch(err, source) from err
