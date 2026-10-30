"""``DeveloperPageDto``: prop ``data`` of ``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}``
(RSC) [P] (sample ``page.developer``, tests/fixtures/rsc/developer_*), a developer's profile.

The meaning of the figures read here is [P 2026-10-13]: checked against the page's own
list of offers (prop ``sale``) and investments in
tests/contract/api/dto/test_developer_page_dto.py. Not read:
``priceIncrease*``/``priceDecrease*`` (the counts are 0 while the sums are not: unclear),
``allCities``, ``allCitiesWithSlugs``, ``allInvestmentNames``, the ``sale`` list and the
daily change axis (prop ``data`` as a list).

The averages of the page (``filteredStats``, its investments and its cities) are 0 where
the service has no value: a developer without active offers in that city gets
``averagePrice``, ``averageSize`` and ``avgAmountPerM2`` 0 [P 2026-10-20] (live: ``atal``
in ``bialystok``). 0 is no value, not a price (``Dto._positive``).
"""

from pydantic import Field

from deweloperuch_mcp.api.dto.developer_dto import DeveloperDto
from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.models.developer_profile import (
    DeveloperCity,
    DeveloperInvestment,
    DeveloperProfile,
    DeveloperSummary,
)
from deweloperuch_mcp.models.offer import DeveloperRef
from deweloperuch_mcp.models.values import CitySlug


class DeveloperInvestmentDto(Dto):
    """An investment of the profile; ``avg_*`` of its active offers."""

    invest_id: int | None = None
    name: str
    city: str | None = None
    city_slug: str | None = None
    slug: str
    status: str
    active_offers: int | None = None
    total_offers: int | None = None
    avg_amount: Number | None = None
    avg_size: Number | None = None
    avg_price_sqm: Number | None = None

    def to_model(self, developer: DeveloperRef) -> DeveloperInvestment:
        """The investment of ``developer`` (the profile's owner)."""
        return DeveloperInvestment(
            investment_slug=self.slug,
            name=self.name,
            city=self._text(self.city),
            city_slug=self._text(self.city_slug),
            status=self.status,
            active_offers=self.active_offers,
            total_offers=self.total_offers,
            avg_price=self._positive(self.avg_amount),
            avg_area_m2=self._positive(self.avg_size),
            avg_price_per_m2=self._positive(self.avg_price_sqm),
            developer=developer,
        )


class DeveloperFilteredStatsDto(Dto):
    """The developer's active offers in the page's city (or the whole country)."""

    totalProjects: int | None = None
    totalSales: int | None = None
    totalCities: int | None = None
    averagePrice: Number | None = None
    averageSize: Number | None = None
    avgAmountPerM2: Number | None = None

    def to_model(self) -> DeveloperSummary:
        return DeveloperSummary(
            investments=self.totalProjects,
            active_offers=self.totalSales,
            cities=self.totalCities,
            avg_price=self._positive(self.averagePrice),
            avg_area_m2=self._positive(self.averageSize),
            avg_price_per_m2=self._positive(self.avgAmountPerM2),
        )


class DeveloperCityStatsDto(Dto):
    """A city of the developer (every city, whatever the page's city)."""

    city: str
    citySlug: str
    investmentCount: int | None = None
    activeOffersCount: int | None = None
    avgPricePerM2: Number | None = None
    avgPrice: Number | None = None

    def to_model(self) -> DeveloperCity:
        return DeveloperCity(
            city=self.city,
            city_slug=self.citySlug,
            investments=self.investmentCount,
            active_offers=self.activeOffersCount,
            avg_price=self._positive(self.avgPrice),
            avg_price_per_m2=self._positive(self.avgPricePerM2),
        )


class DeveloperPageDto(Dto):
    """Prop ``data`` of ``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`` [P]."""

    developer: DeveloperDto
    investments: list[DeveloperInvestmentDto]
    filteredStats: DeveloperFilteredStatsDto
    citiesStats: list[DeveloperCityStatsDto] = Field(default_factory=list)

    def to_model(self, city: CitySlug) -> DeveloperProfile:
        """The profile in ``city`` (the page's): its investments in the service's order,
        every city."""
        owner = self.developer.to_model()
        return DeveloperProfile(
            developer=owner,
            city=city,
            summary=self.filteredStats.to_model(),
            investments=tuple(item.to_model(owner) for item in self.investments),
            cities=tuple(item.to_model() for item in self.citiesStats),
        )
