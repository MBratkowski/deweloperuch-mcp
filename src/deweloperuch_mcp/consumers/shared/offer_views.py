"""The views of the offers (D17 reference): what ``search_offers`` and ``get_offer`` show,
for the CLI (``--json``) and for the MCP presenters, and the offer and developer views
``get_investment`` reuses. Each builds itself from a use case's result (``from_result``)
or a model (``from_model``). Names end in ``View`` so they never shadow a model; only
``Developer`` keeps its name, a ``$defs`` key of the MCP output schemas.
"""

import dataclasses
import datetime as dt
from typing import Any, Self

from deweloperuch_mcp.consumers.shared.view import View
from deweloperuch_mcp.models.offer import DeveloperRef, ListedOffer, Offer
from deweloperuch_mcp.usecases.get_offer import GetOfferResult
from deweloperuch_mcp.usecases.search_offers import SearchOffersResult


# No class docstring: ``Developer`` is a ``$defs`` key of the MCP output schemas, and a
# docstring would become its description (tests/snapshots/mcp_tools.json).
class Developer(View):
    developer_slug: str
    name: str
    website: str | None = None
    description: str | None = None

    @classmethod
    def from_model(cls, developer: DeveloperRef) -> Self:
        return cls(
            developer_slug=developer.developer_slug,
            name=developer.name,
            website=developer.website,
            description=developer.description,
        )


class PriceEventView(View):
    """One entry of an offer's price history."""

    date: dt.date | None
    """``None`` only if the service sent no date."""
    kind: str
    """The service's event type: ``offer``, ``archived`` or ``restored``."""
    price: float | None

    @classmethod
    def history_of(cls, offer: Offer) -> list[Self] | None:
        """The offer's events, oldest first; ``None`` until they are fetched."""
        events = offer.history.events
        if events is None:
            return None
        return [cls(date=event.date, kind=event.kind, price=event.price) for event in events]


class OfferBaseView(View):
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

    @staticmethod
    def fields_of(offer: Offer) -> dict[str, Any]:
        """These fields of ``offer``, for the subclasses' constructors."""
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


class OfferView(OfferBaseView):
    """An offer within its investment (``get_investment``)."""

    price_history: list[PriceEventView] | None = None
    """``None`` unless the history was requested."""

    @classmethod
    def from_model(cls, offer: Offer) -> Self:
        return cls(**cls.fields_of(offer), price_history=PriceEventView.history_of(offer))


class OfferSummaryView(OfferBaseView):
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

    @classmethod
    def from_model(cls, item: ListedOffer, investment_url: str | None) -> Self:
        offer, ref = item.offer, item.investment
        history = offer.history
        return cls(
            **cls.fields_of(offer),
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


class PriceFlagsView(View):
    """What an offer's price history says as of today (``models.price_history.PriceFlags``)."""

    lowest_price_30d: float | None = None
    """The lowest price in effect in the last 30 days (for an archived offer: before its
    withdrawal), the price in effect 30 days ago included."""
    lowest_price_90d: float | None = None
    price_changes: int
    """Prices that differ from the one before them."""
    largest_drop_pct: float | None = None
    """The largest single drop, in % of the earlier price (positive)."""
    largest_rise_pct: float | None = None
    suspicious_reduction: bool
    """The latest drop came at most 30 days after a rise and its price is not below the
    lowest one of the 30 days before it."""


class OfferDetailView(OfferBaseView):
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
    price_history: list[PriceEventView]
    price_flags: PriceFlagsView | None = None
    """``None`` only without a price history."""

    @classmethod
    def from_result(cls, found: GetOfferResult) -> Self:
        offer, investment = found.detail.offer, found.detail.investment
        flags = found.price_flags
        return cls(
            **cls.fields_of(offer),
            investment_slug=investment.investment_slug,
            investment_name=investment.name,
            investment_url=found.investment_url,
            city=investment.city,
            city_slug=investment.city_slug,
            developer=Developer.from_model(investment.developer),
            developer_url=found.developer_url,
            price_history=PriceEventView.history_of(offer) or [],
            price_flags=None if flags is None else PriceFlagsView(**dataclasses.asdict(flags)),
        )


class OfferSearchView(View):
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
    items: list[OfferSummaryView]

    @classmethod
    def from_result(cls, found: SearchOffersResult) -> Self:
        page = found.page
        return cls(
            total=page.total,
            returned=page.returned,
            truncated=page.truncated,
            page=page.page,
            per_page=page.per_page,
            pages_available=page.pages_available,
            hint=found.hint,
            list_url=found.list_url,
            items=[
                OfferSummaryView.from_model(item, url)
                for item, url in zip(page.items, found.investment_urls, strict=True)
            ],
        )
