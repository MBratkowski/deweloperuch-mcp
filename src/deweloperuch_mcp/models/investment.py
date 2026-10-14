"""Investments: development projects with their developer and offers (D3, D13).

``Investment.listing`` is the rule of what a result shows: active offers first, then the
rest in the service's order, at most ``limit`` of them, with the number left out (D4).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Self

from deweloperuch_mcp.models.offer import DeveloperRef, InvestmentRef, Offer
from deweloperuch_mcp.models.price_history import PriceEvent
from deweloperuch_mcp.models.values import OfferId, OffersLimit


@dataclass(frozen=True, kw_only=True)
class Investment:
    """A development project with its developer and all its offers, in the service's
    order."""

    investment_id: int
    """The catalog's own number of the investment (its price histories are kept under
    it); never shown."""
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
    developer: DeveloperRef
    avg_price: float | None = None
    """Mean price of the active offers, as the service counts it."""
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None
    offers_active: int | None = None
    offers_total: int | None = None
    """Active and archived offers, as counted by the service."""
    offers: tuple[Offer, ...] = ()

    @property
    def ref(self) -> InvestmentRef:
        return InvestmentRef(
            investment_slug=self.investment_slug,
            name=self.name,
            city=self.city,
            city_slug=self.city_slug,
            developer=self.developer,
        )

    def find_offer(self, offer_id: OfferId) -> Offer | None:
        return next((offer for offer in self.offers if offer.offer_id == offer_id.value), None)

    def listing(self, limit: OffersLimit | None = None) -> "OfferListing":
        """Active offers first, then the rest (each in the service's order), at most
        ``limit``."""
        ordered = sorted(self.offers, key=lambda offer: not offer.active)  # stable
        kept = ordered if limit is None else ordered[: limit.value]
        return OfferListing(investment=self, offers=tuple(kept), omitted=len(ordered) - len(kept))


@dataclass(frozen=True, kw_only=True)
class OfferListing:
    """What a result shows of an investment: the offers kept and how many were left out."""

    investment: Investment
    offers: tuple[Offer, ...]
    omitted: int

    def with_price_events(self, events: Mapping[int, Sequence[PriceEvent]]) -> Self:
        """Every offer kept with its events (offer id -> events, oldest first); an offer
        the map does not name has none."""
        return replace(
            self,
            offers=tuple(
                offer.with_price_events(events.get(offer.offer_id, ())) for offer in self.offers
            ),
        )


@dataclass(frozen=True, kw_only=True)
class OfferDetail:
    """One offer with its full price history and the investment it belongs to."""

    offer: Offer
    investment: Investment

    def __post_init__(self) -> None:
        if all(offer.offer_id != self.offer.offer_id for offer in self.investment.offers):
            raise ValueError(f"oferta {self.offer.offer_id} nie należy do inwestycji")
