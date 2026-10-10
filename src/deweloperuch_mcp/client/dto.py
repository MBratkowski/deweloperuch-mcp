"""DTOs of the service's responses: the backend's JSON 1:1, tolerant to how values are typed.

Field names and nesting are the backend's (``invest``, ``sale``, ``cityMappings``...);
the domain renames them (D3). Values are kept as sent: amounts and coordinates come as
numbers or numeric strings depending on the endpoint, dates as ``YYYY-MM-DD`` or ISO
datetimes, missing text as ``""`` (docs/discovery/entities.md, "Normalizacja"). The DTO
only checks that such a value can be normalized (``Number``, ``DateText``), so the
domain's conversion never fails; ``deweloperuch_mcp.domain.normalize`` converts them.

Unknown fields are ignored (the backend may add some). Fields the domain relies on are
required, so a renamed or removed field fails the contract tests instead of turning
into silent ``None``. Every model is immutable: the client caches response bodies, not
DTOs, but nothing should mutate a parsed response anyway.
"""

import math
import re
from datetime import date, datetime
from typing import Annotated, Any, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, RootModel, ValidationError

from deweloperuch_mcp.errors import SERVICE_CHANGED, UnexpectedResponseError

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
        problems = "; ".join(
            f"{'.'.join(str(part) for part in e['loc']) or '(całość)'}: {e['msg']}"
            for e in err.errors()[:3]
        )
        more = f" (i {err.error_count() - 3} innych)" if err.error_count() > 3 else ""
        raise UnexpectedResponseError(
            f"Dane z serwisu nie pasują do kontraktu klienta (inny format). {SERVICE_CHANGED}",
            detail=f"{source}: {problems}{more}",
        ) from err


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
