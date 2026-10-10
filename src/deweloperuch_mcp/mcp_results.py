"""What the MCP tools return: the domain results shaped for a model's context (D6).

The MCP server's representation layer over ``deweloperuch_mcp.domain.models``; the CLI
(``--json``) keeps the domain models whole. Differences:

- offers in search results are compact: no currency, dates, event counts, developer
  slug or price changes in PLN; ``city`` and ``city_slug`` only for the whole country;
- ``get_investment`` says how many offers it returned and whether the list is cut
  (``offers_returned``, ``truncated``: D4);
- fields that may be missing are optional, so a result leaves out ``null`` values
  (``dump``) and still matches its output schema; D4 fields (``total``) stay, ``null``
  included (``keep_null``);
- short Polish descriptions of the fields whose name is not enough (the output schema
  is read by the model).

Field names are the domain's (D3; tests/test_mcp_server.py pins it). Value sets the
backend may extend (``status``, ``kind``) stay plain strings: the domain passes unknown
values through, so a ``Literal`` would turn a new value into an error.
"""

import datetime as dt
import json
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from deweloperuch_mcp.domain.models import (
    Developer,
    Investment,
    LocationSearchResult,
    OfferDetail,
    OfferSearchResult,
)

PRICE = "Cena ofertowa w PLN (nie transakcyjna)."
AREA = "Metraż w m²."
PRICE_PER_M2 = "Cena za m² w PLN (price / area_m2)."
STATUS = "active (aktualna) albo archived (wycofana)."
CHANGE_SINCE_START = "Zmiana ceny od pierwszej zaobserwowanej, w PLN (ujemna = tańsza)."
CHANGE_SINCE_START_PCT = "Zmiana ceny od pierwszej zaobserwowanej, w procentach (ujemna = tańsza)."
LAST_CHANGE_KIND = "increase, decrease albo no_change."
LAST_CHANGE_PCT = "Ostatnia zmiana ceny w procentach."
# [W] docs/discovery/endpoints.md, location-search: `count` of districts and streets is
# the number of offers; hence "przybliżona".
OFFER_COUNT = "Liczba ofert wg serwisu (dla dzielnic i ulic przybliżona; 0 = brak ofert)."
# The values are [P] (docs/discovery/entities.md, SaleEvent.event_type); whether a price
# change is an `offer` event or a type of its own is [H], so no "first price" here.
EVENT_KIND = "offer (cena w ofercie), archived (wycofanie), restored (powrót)."


# Class docstrings would become schema descriptions for the model: comments instead.


class McpModel(BaseModel):
    # Fields of the domain model not declared here are dropped (extra="ignore").
    model_config = ConfigDict(frozen=True, extra="ignore")

    # Top-level fields `dump` keeps when they are None (required in the schema).
    keep_null: ClassVar[frozenset[str]] = frozenset()


# --- search_locations ----------------------------------------------------------------------


class LocationItem(McpModel):
    kind: str = Field(description="city, district albo street.")
    name: str
    city: str
    city_slug: str
    district: str | None = None
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    offer_count: int | None = Field(None, description=OFFER_COUNT)


class LocationsResult(McpModel):
    keep_null = frozenset({"total"})  # D4: always there, null when unknown

    total: int | None = Field(
        description="Wszystkie pasujące; null, gdy wyników jest więcej niż pokazano."
    )
    returned: int
    truncated: bool
    hint: str | None = None
    items: list[LocationItem]


# --- search_offers -------------------------------------------------------------------------


class OfferItem(McpModel):
    # A compact offer of the search results; get_offer has the rest.
    offer_id: int
    investment_slug: str
    name: str
    price: float | None = Field(None, description=PRICE)
    area_m2: float | None = Field(None, description=AREA)
    price_per_m2: float | None = Field(None, description=PRICE_PER_M2)
    status: str = Field(description=STATUS)
    investment_name: str
    developer_name: str
    last_price_change_kind: str | None = Field(None, description=LAST_CHANGE_KIND)
    last_price_change_pct: float | None = Field(None, description=LAST_CHANGE_PCT)
    price_change_since_start_pct: float | None = Field(None, description=CHANGE_SINCE_START_PCT)
    city: str | None = Field(None, description="Tylko przy city=polska.")
    city_slug: str | None = Field(None, description="Tylko przy city=polska.")


class OffersResult(McpModel):
    total: int
    returned: int
    truncated: bool = Field(
        description=(
            "true: pasujących ofert jest więcej, niż można przejrzeć (najwyżej 20 stron); "
            "zawęź filtry."
        )
    )
    page: int
    per_page: int
    pages_available: int
    hint: str | None = None
    items: list[OfferItem]


# --- get_offer and get_investment ----------------------------------------------------------


class PriceEventItem(McpModel):
    date: dt.date | None = None
    kind: str = Field(description=EVENT_KIND)
    price: float | None = Field(None, description=PRICE)


class OfferFields(McpModel):
    offer_id: int
    name: str
    status: str = Field(description=STATUS)
    price: float | None = Field(None, description=PRICE)
    currency: str | None = None
    area_m2: float | None = Field(None, description=AREA)
    price_per_m2: float | None = Field(None, description=PRICE_PER_M2)
    price_change_since_start: float | None = Field(None, description=CHANGE_SINCE_START)
    price_change_since_start_pct: float | None = Field(None, description=CHANGE_SINCE_START_PCT)
    creation_date: dt.date | None = None
    last_event_date: dt.date | None = None
    last_change_date: dt.date | None = None


class OfferResult(OfferFields):
    investment_slug: str
    investment_name: str
    city: str
    city_slug: str
    developer: Developer
    price_history: list[PriceEventItem]


class InvestmentOfferItem(OfferFields):
    price_history: list[PriceEventItem] | None = None


class InvestmentResult(McpModel):
    investment_slug: str
    name: str
    status: str = Field(description=STATUS)
    city: str
    city_slug: str
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    currency: str | None = None
    developer: Developer
    avg_price: float | None = Field(None, description="Średnia cena aktywnych ofert w PLN.")
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None
    offers_active: int | None = None
    offers_total: int | None = Field(
        None,
        description=(
            "Wszystkie oferty inwestycji wg serwisu, także archiwalne; lista offers jest "
            "ucięta przez limit."
        ),
    )
    offers: list[InvestmentOfferItem]
    offers_returned: int = Field(description="Ofert na liście offers.")
    offers_omitted: int = Field(description="Ofert pominiętych przez limit.")
    truncated: bool = Field(description="true: lista offers jest niepełna (offers_omitted > 0).")


# --- from the domain -----------------------------------------------------------------------


def locations(result: LocationSearchResult) -> LocationsResult:
    return LocationsResult.model_validate(result.model_dump())


def offers(result: OfferSearchResult, *, whole_country: bool) -> OffersResult:
    """Compact offers; their city only when ``whole_country`` (otherwise it is the query).

    A truncated result gets its own hint: narrow the filters. The domain's hint also
    suggests a bigger page, which would not narrow anything and is not offered here.
    """
    hidden: Any = None if whole_country else {"items": {"__all__": {"city", "city_slug"}}}
    data = result.model_dump(exclude=hidden)
    if result.truncated:
        shown = result.pages_available * result.per_page
        data["hint"] = (
            f"Pasujących ofert jest {result.total}, a można przejrzeć najwyżej "
            f"{result.pages_available} stron po {result.per_page} ({shown}). Zawęź filtry "
            "(cena, metraż)."
        )
    return OffersResult.model_validate(data)


def offer(result: OfferDetail) -> OfferResult:
    return OfferResult.model_validate(result.model_dump())


def investment(result: Investment) -> InvestmentResult:
    data = result.model_dump()
    data["offers_returned"] = len(result.offers)
    data["truncated"] = result.offers_omitted > 0
    return InvestmentResult.model_validate(data)


def dump(result: McpModel) -> dict[str, Any]:
    """The structured result: JSON values without ``null`` fields, except ``keep_null``."""
    present = result.model_dump(mode="json", exclude_none=True)
    return {
        name: present.get(name)
        for name in type(result).model_fields
        if name in present or name in result.keep_null
    }


def dump_json(result: McpModel) -> str:
    """The same as compact JSON text."""
    return json.dumps(dump(result), ensure_ascii=False, separators=(",", ":"))
