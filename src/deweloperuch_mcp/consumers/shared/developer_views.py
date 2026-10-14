"""The views of the developers: what ``search_developers`` and ``get_developer`` show, for the
CLI (``--json``) and for the MCP presenters. Each builds itself from a use case's result
(``from_result``) or a model (``from_model``); names end in ``View`` so they never shadow
a model.
"""

import dataclasses
from typing import Self

from deweloperuch_mcp.consumers.shared.offer_views import Developer
from deweloperuch_mcp.consumers.shared.view import View
from deweloperuch_mcp.models.developer_match import DeveloperMatch
from deweloperuch_mcp.models.developer_profile import DeveloperCity, DeveloperInvestment
from deweloperuch_mcp.usecases.get_developer import GetDeveloperResult
from deweloperuch_mcp.usecases.search_developers import SearchDevelopersResult

# --- search_developers -------------------------------------------------------------------------


class DeveloperMatchView(View):
    """A developer whose name matches; ``developer_slug`` goes to its profile."""

    developer_slug: str
    name: str
    offer_count: int | None = None
    """Offers of the developer, as the service counts them."""
    developer_url: str | None = None
    """The developer's profile on the service, for the whole country."""

    @classmethod
    def from_model(cls, match: DeveloperMatch, developer_url: str | None) -> Self:
        return cls(
            developer_slug=match.developer_slug,
            name=match.name,
            offer_count=match.offer_count,
            developer_url=developer_url,
        )


class DeveloperSearchView(View):
    total: int | None
    """Every match; ``None`` when the result is truncated and the service's count does
    not fit what it gave."""
    returned: int
    truncated: bool
    """More developers match than shown: a more specific name or a larger limit."""
    hint: str | None = None
    items: list[DeveloperMatchView]

    @classmethod
    def from_result(cls, found: SearchDevelopersResult) -> Self:
        search = found.search
        return cls(
            total=search.total,
            returned=search.returned,
            truncated=search.truncated,
            hint=found.hint,
            items=[
                DeveloperMatchView.from_model(item, url)
                for item, url in zip(search.items, found.developer_urls, strict=True)
            ],
        )


# --- get_developer -----------------------------------------------------------------------------


class DeveloperInvestmentView(View):
    """An investment on a developer's profile (``get_developer``)."""

    investment_slug: str
    name: str
    city: str | None = None
    city_slug: str | None = None
    status: str
    active_offers: int | None = None
    total_offers: int | None = None
    """Active and archived offers."""
    avg_price: float | None = None
    """Of the active offers, as are the other averages."""
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None
    investment_url: str | None = None

    @classmethod
    def from_model(cls, item: DeveloperInvestment, investment_url: str | None) -> Self:
        return cls(
            investment_slug=item.investment_slug,
            name=item.name,
            city=item.city,
            city_slug=item.city_slug,
            status=item.status,
            active_offers=item.active_offers,
            total_offers=item.total_offers,
            avg_price=item.avg_price,
            avg_area_m2=item.avg_area_m2,
            avg_price_per_m2=item.avg_price_per_m2,
            investment_url=investment_url,
        )


class DeveloperCityView(View):
    city: str
    city_slug: str
    investments: int | None = None
    active_offers: int | None = None
    avg_price: float | None = None
    avg_price_per_m2: float | None = None

    @classmethod
    def from_model(cls, item: DeveloperCity) -> Self:
        return cls(
            city=item.city,
            city_slug=item.city_slug,
            investments=item.investments,
            active_offers=item.active_offers,
            avg_price=item.avg_price,
            avg_price_per_m2=item.avg_price_per_m2,
        )


class DeveloperSummaryView(View):
    """The developer's active offers in the profile's city (or the whole country)."""

    investments: int | None = None
    active_offers: int | None = None
    cities: int | None = None
    avg_price: float | None = None
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None


class DeveloperProfileView(View):
    """A developer in a city or the whole country (``get_developer``)."""

    developer: Developer
    developer_url: str | None = None
    """The developer's profile in ``city_slug`` on the service."""
    city_slug: str
    """The scope of ``summary`` and ``investments``: a city or ``polska``."""
    summary: DeveloperSummaryView
    investments_total: int
    investments_omitted: int
    """Investments left out because of ``limit``."""
    hint: str | None = None
    investments: list[DeveloperInvestmentView]
    """The most active offers first, at most ``limit``."""
    cities: list[DeveloperCityView]
    """Every city of the developer, whatever ``city_slug``."""

    @classmethod
    def from_result(cls, found: GetDeveloperResult) -> Self:
        listing = found.listing
        profile = listing.profile
        return cls(
            developer=Developer.from_model(profile.developer),
            developer_url=found.developer_url,
            city_slug=profile.city.value,
            summary=DeveloperSummaryView(**dataclasses.asdict(profile.summary)),
            investments_total=len(profile.investments),
            investments_omitted=listing.omitted,
            hint=found.hint,
            investments=[
                DeveloperInvestmentView.from_model(item, url)
                for item, url in zip(listing.investments, found.investment_urls, strict=True)
            ],
            cities=[DeveloperCityView.from_model(item) for item in profile.cities],
        )
