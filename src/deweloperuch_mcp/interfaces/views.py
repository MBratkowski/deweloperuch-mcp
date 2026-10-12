"""What the CLI (``--json``) and the MCP presenter show of a result.

The representation that used to be the domain model, kept field for field: the CLI's
``--json`` prints these models as they are, and ``mcp.presenters`` cuts them down for a
model's context. The domain (``deweloperuch_mcp.domain``) is plain Python now; the
builders at the end (``location_search``, ``offer_search``, ``offer_detail``,
``investment``, ``government_statistics``) turn what the use cases return into these
views. Shared by both interfaces: the CLI prints them, the MCP presenter cuts them down.

Names are the domain's (D3): no backend names and no backend enum values; numbers are
``float`` (PLN, m², percent points), dates ``datetime.date``, missing values ``None``.
Identifiers are named as the "get" operations take them: ``offer_id``,
``investment_slug``, ``developer_slug``, ``city_slug`` (docs/capability-matrix.md).

Fields ending in ``_url`` hold addresses of the service's public pages for people, named
after what they point to (D12; the use cases get them from the ``PageLinks`` port);
``None`` when a slug they need is missing.

Value sets that the backend may extend (``kind``, ``status``) are plain strings; the
known values are listed in the field docs. Unknown values pass through: backend enums
(price event and price change kinds, e.g. ``PRICE_SOMETHING``) lowercased, values that
are already lowercase words (``Location.kind``, ``status``) unchanged.
"""

import datetime as dt
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from deweloperuch_mcp.application.investments import FoundInvestment
from deweloperuch_mcp.application.offers import FoundOffer, FoundOffers
from deweloperuch_mcp.application.statistics import FoundStatistics
from deweloperuch_mcp.domain import locations, offers
from deweloperuch_mcp.domain.statistics import Dataset, Frequency, TimeSeries


class View(BaseModel):
    model_config = ConfigDict(frozen=True)


# --- locations -------------------------------------------------------------------------


class Location(View):
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


class LocationSearchResult(View):
    total: int | None
    """All matches; ``None`` when ``truncated`` (the service does not say how many)."""
    returned: int
    truncated: bool
    """More matches exist than shown: make the query more specific."""
    hint: str | None = None
    items: list[Location]


# --- developers and offers ------------------------------------------------------------


class Developer(View):
    developer_slug: str
    name: str
    website: str | None = None
    description: str | None = None


class PriceEvent(View):
    """One entry of an offer's price history."""

    date: dt.date | None
    """``None`` only if the service sent no date."""
    kind: str
    """The service's event type: ``offer``, ``archived`` or ``restored``."""
    price: float | None


class OfferBase(View):
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
    investment_url: str | None = None
    """The investment's page on the service."""
    city: str | None = None
    city_slug: str | None = None
    developer_slug: str
    developer_name: str


class OfferDetail(OfferBase):
    """One offer with its investment, developer and full price history (``get_offer``)."""

    investment_slug: str
    investment_name: str
    investment_url: str | None = None
    """The investment's page on the service."""
    city: str
    city_slug: str
    developer: Developer
    developer_url: str | None = None
    """The developer's profile on the service."""
    price_history: list[PriceEvent]


class OfferSearchResult(View):
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
    list_url: str | None = None
    """This list on the service: the same filters, order and page."""
    items: list[OfferSummary]


# --- investments ---------------------------------------------------------------------------


class Investment(View):
    """A development project with its developer and offers (``get_investment``)."""

    investment_slug: str
    name: str
    status: str
    """``active`` or ``archived``."""
    investment_url: str | None = None
    """The investment's page on the service (its offers have no pages of their own)."""
    city: str
    city_slug: str
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    currency: str | None = None
    developer: Developer
    developer_url: str | None = None
    """The developer's profile on the service."""
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


# --- government statistics -------------------------------------------------------------------


@dataclass(frozen=True)
class GovernmentStatistics:
    """The latest periods of one dataset for one location (D4: the cut is explicit).

    The CLI's ``--json`` prints it with ``dataclasses.asdict``, in this field order.
    """

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
    hint: str | None
    note: str | None
    """A caveat about the data, e.g. a last quarter that holds only some of its months."""
    stats_url: str | None
    """The section of the service's page with this data (D12), for people."""
    series: tuple[TimeSeries, ...]

    @property
    def periods(self) -> tuple[str, ...]:
        return self.series[0].periods


# --- from the use cases ----------------------------------------------------------------------


def location_search(result: locations.LocationSearchResult) -> LocationSearchResult:
    return LocationSearchResult(
        total=result.total,
        returned=result.returned,
        truncated=result.truncated,
        hint=result.hint,
        items=[_location(item) for item in result.items],
    )


def offer_search(found: FoundOffers) -> OfferSearchResult:
    page = found.page
    return OfferSearchResult(
        total=page.total,
        returned=page.returned,
        truncated=page.truncated,
        page=page.page,
        per_page=page.per_page,
        pages_available=page.pages_available,
        hint=found.hint,
        list_url=found.list_url,
        items=[
            _offer_summary(item, url)
            for item, url in zip(page.items, found.investment_urls, strict=True)
        ],
    )


def offer_detail(found: FoundOffer) -> OfferDetail:
    offer, investment = found.detail.offer, found.detail.investment
    return OfferDetail(
        **_offer_fields(offer),
        investment_slug=investment.investment_slug,
        investment_name=investment.name,
        investment_url=found.investment_url,
        city=investment.city,
        city_slug=investment.city_slug,
        developer=_developer(investment.developer),
        developer_url=found.developer_url,
        price_history=_events(offer) or [],
    )


def investment(found: FoundInvestment) -> Investment:
    listing = found.listing
    shown = listing.investment
    return Investment(
        investment_slug=shown.investment_slug,
        name=shown.name,
        status=shown.status,
        investment_url=found.investment_url,
        city=shown.city,
        city_slug=shown.city_slug,
        street=shown.street,
        lat=shown.lat,
        lng=shown.lng,
        currency=shown.currency,
        developer=_developer(shown.developer),
        developer_url=found.developer_url,
        avg_price=shown.avg_price,
        avg_area_m2=shown.avg_area_m2,
        avg_price_per_m2=shown.avg_price_per_m2,
        offers_active=shown.offers_active,
        offers_total=shown.offers_total,
        offers=[
            Offer(**_offer_fields(offer), price_history=_events(offer)) for offer in listing.offers
        ],
        offers_omitted=listing.omitted,
    )


def government_statistics(found: FoundStatistics) -> GovernmentStatistics:
    result = found.statistics
    return GovernmentStatistics(
        location_slug=result.location_slug,
        location_name=result.location_name,
        dataset=result.dataset,
        title=result.title,
        source=result.source,
        frequency=result.frequency,
        total=result.total,
        returned=result.returned,
        truncated=result.truncated,
        available_from=result.available_from,
        hint=found.hint,
        note=result.note,
        stats_url=found.stats_url,
        series=result.series,
    )


def _location(item: locations.Location) -> Location:
    return Location(
        kind=item.kind,
        name=item.name,
        city=item.city,
        city_slug=item.city_slug,
        district=item.district,
        street=item.street,
        lat=item.lat,
        lng=item.lng,
        offer_count=item.offer_count,
    )


def _developer(developer: offers.Developer) -> Developer:
    return Developer(
        developer_slug=developer.developer_slug,
        name=developer.name,
        website=developer.website,
        description=developer.description,
    )


def _offer_fields(offer: offers.Offer) -> dict[str, Any]:
    history = offer.history
    return {
        "offer_id": offer.offer_id,
        "name": offer.name,
        "status": offer.status,
        "price": offer.price,
        "currency": offer.currency,
        "area_m2": offer.area_m2,
        "price_per_m2": offer.price_per_m2,
        "price_change_since_start": history.since_start.pln,
        "price_change_since_start_pct": history.since_start.percent,
        "creation_date": history.created_on,
        "last_event_date": history.last_event_on,
        "last_change_date": history.last_changed_on,
    }


def _events(offer: offers.Offer) -> list[PriceEvent] | None:
    events = offer.history.events
    if events is None:
        return None
    return [PriceEvent(date=event.date, kind=event.kind, price=event.price) for event in events]


def _offer_summary(item: offers.ListedOffer, investment_url: str | None) -> OfferSummary:
    offer, ref = item.offer, item.investment
    history = offer.history
    return OfferSummary(
        **_offer_fields(offer),
        last_price_change=history.last_change.pln,
        last_price_change_pct=history.last_change.percent,
        last_price_change_kind=history.last_change.direction,
        events_count=history.events_count,
        investment_slug=ref.investment_slug,
        investment_name=ref.name,
        investment_url=investment_url,
        city=ref.city,
        city_slug=ref.city_slug,
        developer_slug=ref.developer.developer_slug,
        developer_name=ref.developer.name,
    )
