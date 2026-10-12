"""Offers of apartments in developers' price lists (D3, D13), and how they are searched.

No backend names (``invest``, ``sale``, ``amount``) and no backend enum values: numbers
are ``float`` (PLN, m², percent points), dates ``datetime.date``, missing values ``None``.
Value sets the service may extend (``status``, event kinds) stay plain strings: unknown
values pass through, so a new one is shown instead of failing.

- ``PriceHistory``: what is known about an offer's price over time: the service's summary
  (the change since the first price, the last change, when it was added and changed) and,
  when fetched, the events themselves, oldest first.
- ``Offer``: one apartment of a price list; its price per m² is derived.
- ``OfferSearchCriteria`` -> ``OfferSearchPage``: one page of a search, with the limit of
  what the service lets browse as part of the result (D4).
"""

import datetime as dt
import math
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Self

from deweloperuch_mcp.domain.values import (
    BROWSABLE_PAGES,
    AreaRange,
    CitySlug,
    OfferSort,
    PageNumber,
    PageSize,
    PriceRange,
)

ACTIVE, ARCHIVED = "active", "archived"
"""Statuses of an offer and of an investment the service names [P]."""

EVENT_OFFER, EVENT_ARCHIVED, EVENT_RESTORED = "offer", "archived", "restored"
"""Kinds of a price event [P]: a price in the list, withdrawn, back in the list."""

INCREASE, DECREASE, NO_CHANGE = "increase", "decrease", "no_change"
"""Directions of the last price change [P]."""


@dataclass(frozen=True, kw_only=True)
class Developer:
    developer_slug: str
    name: str
    website: str | None = None
    description: str | None = None


@dataclass(frozen=True, kw_only=True)
class PriceEvent:
    """One entry of an offer's price history."""

    date: dt.date | None
    """``None`` only if the service gave no date."""
    kind: str
    """``offer``, ``archived`` or ``restored``."""
    price: float | None


@dataclass(frozen=True, kw_only=True)
class PriceChange:
    """A change of price: in PLN, in percent of the earlier price, and its direction
    (negative: cheaper)."""

    pln: float | None = None
    percent: float | None = None
    direction: str | None = None
    """``increase``, ``decrease`` or ``no_change``; given for the last change only."""


def _chronological(event: PriceEvent) -> dt.date:
    return event.date or dt.date.min


@dataclass(frozen=True, kw_only=True)
class PriceHistory:
    """An offer's price over time: the service's summary and, when fetched, its events.

    ``events`` is ``None`` until they are fetched; then oldest first (events without a
    date, none seen so far, before the rest).
    """

    since_start: PriceChange = field(default_factory=PriceChange)
    """Current price minus the first one seen."""
    last_change: PriceChange = field(default_factory=PriceChange)
    """The latest change (known in search results only)."""
    events_count: int | None = None
    created_on: dt.date | None = None
    last_event_on: dt.date | None = None
    last_changed_on: dt.date | None = None
    events: tuple[PriceEvent, ...] | None = None

    def __post_init__(self) -> None:
        if self.events is not None:
            dates = [_chronological(event) for event in self.events]
            if dates != sorted(dates):
                raise ValueError("zdarzenia historii ceny nie są w kolejności dat")

    def with_events(self, events: Iterable[PriceEvent]) -> Self:
        """This history with its events (oldest first)."""
        return replace(self, events=tuple(events))


@dataclass(frozen=True, kw_only=True)
class Offer:
    """An apartment in a developer's price list."""

    offer_id: int
    name: str
    """The developer's label of the apartment, e.g. ``D1.1.1.4``."""
    status: str
    """``active`` or ``archived``."""
    price: float | None
    currency: str | None = None
    area_m2: float | None
    history: PriceHistory = field(default_factory=PriceHistory)

    @property
    def price_per_m2(self) -> float | None:
        """``price / area_m2``, rounded to 0.01; ``None`` without a price or an area."""
        if self.price is None or not self.area_m2:
            return None
        return round(self.price / self.area_m2, 2)

    @property
    def active(self) -> bool:
        return self.status == ACTIVE

    def with_price_events(self, events: Iterable[PriceEvent]) -> Self:
        return replace(self, history=self.history.with_events(events))


@dataclass(frozen=True, kw_only=True)
class InvestmentRef:
    """The investment an offer belongs to, as far as a list of offers names it."""

    investment_slug: str
    name: str
    city: str | None
    city_slug: str | None
    developer: Developer


@dataclass(frozen=True, kw_only=True)
class ListedOffer:
    """An offer in search results, with the investment and developer it belongs to."""

    offer: Offer
    investment: InvestmentRef


@dataclass(frozen=True, kw_only=True)
class OfferSearchCriteria:
    """What an offers search asks for: a city (or the whole country), optional ranges of
    price and area, an order, and the page."""

    city: CitySlug
    price: PriceRange | None = None
    area: AreaRange | None = None
    sort: OfferSort | None = None
    page: PageNumber = field(default_factory=PageNumber)
    per_page: PageSize = field(default_factory=PageSize)


@dataclass(frozen=True, kw_only=True)
class OfferSearchPage:
    """One page of an offers search, as the service paged it (D4: the limit is part of
    the result)."""

    items: tuple[ListedOffer, ...]
    total: int
    """All offers matching the criteria."""
    page: int
    per_page: int

    @property
    def returned(self) -> int:
        return len(self.items)

    @property
    def pages_available(self) -> int:
        """Pages that can be requested: at most ``BROWSABLE_PAGES``."""
        if self.per_page <= 0:
            return 0
        return min(BROWSABLE_PAGES, math.ceil(self.total / self.per_page))

    @property
    def browsable(self) -> int:
        """Offers the service lets browse at this page size: ``BROWSABLE_PAGES`` pages."""
        return BROWSABLE_PAGES * self.per_page

    @property
    def truncated(self) -> bool:
        """``total`` exceeds what the service lets browse."""
        return self.total > self.browsable
