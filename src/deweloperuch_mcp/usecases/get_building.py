"""Use case ``GetBuilding``: a building of the price register with its units and their
transactions, and on request the price trend around it."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.building import (
    BuildingSlug,
    NeighbourhoodTrend,
    UnitListing,
    UnitsLimit,
)
from deweloperuch_mcp.models.errors import TrueOrFalse, ValueName
from deweloperuch_mcp.usecases.ports import BuildingCatalog, BuildingPageLinks
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs

SLUG_SOURCE = (
    "Slug budynku to ostatni człon adresu jego strony z cenami transakcyjnymi na "
    "deweloperuch.pl, np. 23-marca-79c-sopot albo aleja-krakowska-279-warszawa."
)
"""Where a building's slug comes from. No lookup by address gives it [P]: the streets of
the transaction search have no slugs (docs/discovery/endpoints.md, investment-streets)."""


@dataclass(frozen=True, kw_only=True)
class GetBuildingRequest:
    """The building and how much of it to show, checked (``parse``) before anything is
    sent."""

    building_slug: BuildingSlug
    limit: UnitsLimit | None = None
    """At most this many units (``None``: all)."""
    include_trend: bool = False
    trend_quarters: int | None = None
    """The newest quarters of the trend a result keeps (``None``: all): the consumer's
    choice, not the caller's, so it is not checked."""

    @classmethod
    def parse(
        cls,
        *,
        building_slug: object,
        limit: object = None,
        include_trend: object = False,
        trend_quarters: int | None = None,
    ) -> Self:
        """Checked in this order: building, limit, trend. A refusal names the parameter
        (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(
                building_slug=BuildingSlug.parse(building_slug),
                limit=UnitsLimit.parse(limit),
                include_trend=TrueOrFalse().check(ValueName.TREND, include_trend),
                trend_quarters=trend_quarters,
            )


@dataclass(frozen=True, kw_only=True)
class GetBuildingResult:
    """The building as a result shows it, with its page (D12) and, when asked for, the
    trend around it."""

    listing: UnitListing
    trend: NeighbourhoodTrend | None
    building_url: str | None


class GetBuilding:
    """The units whose last transaction is the newest first, at most ``limit``
    (``Building.listing``); with the trend around the building when asked (one more
    request), its newest ``trend_quarters`` quarters (``None``: all)."""

    def __init__(self, catalog: BuildingCatalog, links: BuildingPageLinks) -> None:
        self._catalog = catalog
        self._links = links

    def execute(self, request: GetBuildingRequest) -> GetBuildingResult:
        slug = request.building_slug
        with ReportedAs(f"Budynek {slug.value!r}", not_found=self._unknown_building(slug)):
            building = self._catalog.building(slug)
        trend = None
        if request.include_trend:
            with ReportedAs(
                f"Trend cen w okolicy budynku {slug.value!r}", not_found=self._no_trend(slug)
            ):
                trend = self._catalog.neighbourhood_trend(building).latest(request.trend_quarters)
        return GetBuildingResult(
            listing=building.listing(request.limit),
            trend=trend,
            building_url=self._links.building(building.ref),
        )

    @staticmethod
    def _unknown_building(slug: BuildingSlug) -> str:
        return f"Nie znaleziono budynku {slug.value!r}. {SLUG_SOURCE}"

    @staticmethod
    def _no_trend(slug: BuildingSlug) -> str:
        return (
            f"Serwis nie ma trendu cen w okolicy budynku {slug.value!r}. Pobierz budynek bez "
            "include_trend."
        )
