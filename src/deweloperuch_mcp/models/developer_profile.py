"""A developer's profile: its investments and cities, in one city or the whole country.

The port ``usecases.ports.DeveloperDirectory`` gives the profile as the service shows it
(``DeveloperProfile``); ``DeveloperProfile.listing`` is the rule of what a result shows:
the investments with the most active offers first, at most ``limit`` of them, with the
number left out (D4). Single offers are not part of a profile.
"""

from dataclasses import dataclass

from deweloperuch_mcp.models.offer import DeveloperRef, InvestmentRef
from deweloperuch_mcp.models.values import CitySlug, InvestmentsLimit

DEFAULT_INVESTMENTS_LIMIT = 20
"""Investments a result shows unless asked otherwise."""


@dataclass(frozen=True, kw_only=True)
class DeveloperInvestment:
    """An investment on a developer's profile, with the service's own figures."""

    investment_slug: str
    name: str
    city: str | None
    city_slug: str | None
    status: str
    active_offers: int | None
    total_offers: int | None
    """Active and archived offers."""
    avg_price: float | None
    """Mean price of the active offers."""
    avg_area_m2: float | None
    """Mean area of the active offers."""
    avg_price_per_m2: float | None
    """Price per m² of the active offers, as the service counts it."""
    developer: DeveloperRef

    @property
    def ref(self) -> InvestmentRef:
        return InvestmentRef(
            investment_slug=self.investment_slug,
            name=self.name,
            city=self.city,
            city_slug=self.city_slug,
            developer=self.developer,
        )


@dataclass(frozen=True, kw_only=True)
class DeveloperCity:
    """A city where a developer has active offers, with the service's own figures."""

    city: str
    city_slug: str
    investments: int | None
    active_offers: int | None
    avg_price: float | None
    avg_price_per_m2: float | None


@dataclass(frozen=True, kw_only=True)
class DeveloperSummary:
    """The developer's active offers in the profile's city (or the whole country)."""

    investments: int | None
    active_offers: int | None
    cities: int | None
    avg_price: float | None
    avg_area_m2: float | None
    avg_price_per_m2: float | None


@dataclass(frozen=True, kw_only=True)
class DeveloperProfile:
    """A developer in a city (or the whole country, ``polska``)."""

    developer: DeveloperRef
    city: CitySlug
    """The scope of ``investments`` and ``summary``."""
    summary: DeveloperSummary
    investments: tuple[DeveloperInvestment, ...]
    """In the service's order."""
    cities: tuple[DeveloperCity, ...]
    """Every city of the developer, whatever the scope."""

    def listing(self, limit: InvestmentsLimit) -> "DeveloperListing":
        """The investments with the most active offers first (unknown counts last, ties
        in the service's order), at most ``limit``."""
        ordered = sorted(  # stable: ties keep the service's order
            self.investments,
            key=lambda item: (item.active_offers is None, -(item.active_offers or 0)),
        )
        kept = tuple(ordered[: limit.value])
        return DeveloperListing(profile=self, investments=kept, omitted=len(ordered) - len(kept))


@dataclass(frozen=True, kw_only=True)
class DeveloperListing:
    """What a result shows of a profile: the investments kept and how many were left out."""

    profile: DeveloperProfile
    investments: tuple[DeveloperInvestment, ...]
    omitted: int
