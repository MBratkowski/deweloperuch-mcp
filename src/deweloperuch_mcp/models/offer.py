"""Offers of apartments in developers' price lists (D3), and how they are searched.

No backend names (``invest``, ``sale``, ``amount``) and no backend enum values: numbers
are ``float`` (PLN, m², percent points), dates ``datetime.date``, missing values ``None``.
Value sets the service may extend (``status``) stay plain strings.

- ``Offer``: one apartment of a price list, with its ``PriceHistory``
  (``models.price_history``); its price per m² is derived.
- ``OfferSearchCriteria`` -> ``OfferSearchPage``: one page of a search, with the limit of
  what the service lets browse as part of the result (D4).
"""

import datetime as dt
import math
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Self

from deweloperuch_mcp.models.errors import InvalidValueError, OneCity, ValueName
from deweloperuch_mcp.models.price_history import PriceEvent, PriceFlags, PriceHistory
from deweloperuch_mcp.models.values import (
    BROWSABLE_PAGES,
    AreaRange,
    CitySlug,
    DistrictName,
    OfferSort,
    OfferStatus,
    PageNumber,
    PageSize,
    PricePerM2Range,
    PriceRange,
)

ACTIVE, ARCHIVED = "active", "archived"
"""Statuses of an offer and of an investment the service names [P]."""


@dataclass(frozen=True, kw_only=True)
class DeveloperRef:
    developer_slug: str
    name: str
    website: str | None = None
    description: str | None = None


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

    def price_flags(self, as_of: dt.date) -> PriceFlags | None:
        """``PriceHistory.price_flags`` of this offer (archived: as of its withdrawal)."""
        return self.history.price_flags(as_of, archived=self.status == ARCHIVED)


@dataclass(frozen=True, kw_only=True)
class InvestmentRef:
    """The investment an offer belongs to, as far as a list of offers names it."""

    investment_slug: str
    name: str
    city: str | None
    city_slug: str | None
    developer: DeveloperRef


@dataclass(frozen=True, kw_only=True)
class ListedOffer:
    """An offer in search results, with the investment and developer it belongs to."""

    offer: Offer
    investment: InvestmentRef


@dataclass(frozen=True, kw_only=True)
class OfferSearchCriteria:
    """What an offers search asks for: a city (or the whole country), optional ranges of
    price, area and price per m², a district of the city, only offers cheaper than their
    first price, their status, an order, and the page.

    A district belongs to one city, so it needs one: never the whole country.
    """

    city: CitySlug
    price: PriceRange | None = None
    area: AreaRange | None = None
    price_per_m2: PricePerM2Range | None = None
    district: DistrictName | None = None
    price_dropped: bool = False
    """Only offers whose price is below their first one."""
    status: OfferStatus = OfferStatus.ACTIVE
    sort: OfferSort | None = None
    page: PageNumber = field(default_factory=PageNumber)
    per_page: PageSize = field(default_factory=PageSize)

    def __post_init__(self) -> None:
        if self.district is not None and self.city.whole_country:
            raise InvalidValueError(ValueName.DISTRICT, OneCity(), self.district.text)


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
