"""Domain model (D3): names independent of the backend, normalized values.

What the services return and what the CLI and the MCP server (S1b) show. No backend
names (``invest``, ``sale``, ``amount``) and no backend enum values: numbers are
``float`` (PLN, m², percent points), dates are ``datetime.date``, missing values are
``None`` (never ``""``). Identifiers are named as the "get" operations take them:
``offer_id``, ``investment_slug``, ``developer_slug``, ``city_slug``
(docs/capability-matrix.md).

Value sets that the backend may extend (``kind``, ``status``) are plain strings; the
known values are listed in the field docs. Unknown values pass through: backend enums
(price event and price change kinds, e.g. ``PRICE_SOMETHING``) lowercased, values that
are already lowercase words (``Location.kind``, ``status``) unchanged.
"""

import datetime as dt

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True)


# --- locations -------------------------------------------------------------------------


class Location(DomainModel):
    """A city, district or street to search in; ``city_slug`` goes to ``search_offers``."""

    kind: str
    """``city``, ``district`` or ``street``."""
    name: str
    city: str
    city_slug: str
    district: str | None = None
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    offer_count: int | None = None
    """Developer offers in the location (for districts and streets [W])."""


class LocationSearchResult(DomainModel):
    total: int | None
    """All matches; ``None`` when ``truncated`` (the service does not say how many)."""
    returned: int
    truncated: bool
    """More matches exist than shown: make the query more specific."""
    hint: str | None = None
    items: list[Location]


# --- developers and offers ------------------------------------------------------------


class Developer(DomainModel):
    developer_slug: str
    name: str
    website: str | None = None
    description: str | None = None


class PriceEvent(DomainModel):
    """One entry of an offer's price history."""

    date: dt.date | None
    """``None`` only if the service sent no date."""
    kind: str
    """The service's event type: ``offer``, ``archived`` or ``restored``."""
    price: float | None


class OfferBase(DomainModel):
    """Fields every view of an offer (an apartment in a developer's price list) has."""

    offer_id: int
    name: str
    """The developer's label of the apartment, e.g. ``D1.1.1.4``."""
    status: str
    """``active`` or ``archived``."""
    price: float | None
    currency: str | None = None
    area_m2: float | None
    price_per_m2: float | None
    """Derived: ``price / area_m2``, rounded to 0.01."""
    price_change_since_start: float | None = None
    """Current price minus the first one seen, in ``currency``."""
    price_change_since_start_pct: float | None = None
    """The same in percent of the first price."""
    creation_date: dt.date | None = None
    last_event_date: dt.date | None = None
    last_change_date: dt.date | None = None


class Offer(OfferBase):
    """An offer within its investment (``get_investment``)."""

    price_history: list[PriceEvent] | None = None
    """``None`` unless the history was requested."""


class OfferSummary(OfferBase):
    """An offer in search results, with the investment and developer it belongs to."""

    last_price_change: float | None = None
    last_price_change_pct: float | None = None
    last_price_change_kind: str | None = None
    """``increase``, ``decrease`` or ``no_change``."""
    events_count: int | None = None
    investment_slug: str
    investment_name: str
    city: str | None = None
    city_slug: str | None = None
    developer_slug: str
    developer_name: str


class OfferDetail(OfferBase):
    """One offer with its investment, developer and full price history (``get_offer``)."""

    investment_slug: str
    investment_name: str
    city: str
    city_slug: str
    developer: Developer
    price_history: list[PriceEvent]


class OfferSearchResult(DomainModel):
    """One page of ``search_offers`` (D4: the limit is part of the contract)."""

    total: int
    """All offers matching the filters."""
    returned: int
    truncated: bool
    """``total`` exceeds what the service lets browse (20 pages x ``per_page``)."""
    page: int
    per_page: int
    pages_available: int
    """Pages that can be requested: at most 20."""
    hint: str | None = None
    items: list[OfferSummary]


# --- investments ---------------------------------------------------------------------------


class Investment(DomainModel):
    """A development project with its developer and offers (``get_investment``)."""

    investment_slug: str
    name: str
    status: str
    """``active`` or ``archived``."""
    city: str
    city_slug: str
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    currency: str | None = None
    developer: Developer
    avg_price: float | None = None
    """Mean price of the active offers."""
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None
    offers_active: int | None = None
    offers_total: int | None = None
    """Active and archived offers, as counted by the service."""
    offers: list[Offer]
    """Active offers first, then the rest; at most ``limit`` of them."""
    offers_omitted: int
    """Offers left out because of ``limit``."""
