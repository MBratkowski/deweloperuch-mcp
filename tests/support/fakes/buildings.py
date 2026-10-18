"""``BuildingCatalog`` and ``BuildingPageLinks`` in memory, and the buildings and trends
they answer.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from deweloperuch_mcp.models.building import (
    Building,
    BuildingRef,
    BuildingSlug,
    NeighbourhoodTrend,
    Transaction,
    TrendQuarter,
    Unit,
)
from deweloperuch_mcp.usecases import ports

OLD, MID, NEW = dt.date(2018, 1, 5), dt.date(2021, 6, 1), dt.date(2025, 3, 3)
"""Deed dates of the canned transactions: an old one, one in the middle, a new one."""


def sold(*days: dt.date | None) -> tuple[Transaction, ...]:
    return tuple(Transaction(date=day, price=1.0, price_per_m2=1.0) for day in days)


def unit_sold(unit_id: int, *days: dt.date | None) -> Unit:
    return Unit(unit_id=unit_id, name=f"U{unit_id}", transactions=sold(*days))


def unit_sold_as(unit_id: int, *classifications: str | None) -> Unit:
    """A unit with a transaction of each class, all on one day."""
    transactions = tuple(
        Transaction(date=MID, price=1.0, price_per_m2=1.0, classification=classification)
        for classification in classifications
    )
    return Unit(unit_id=unit_id, name=f"U{unit_id}", transactions=transactions)


def building_of(*units: Unit) -> Building:
    return Building(
        building_id=1,
        building_slug="ulica-1-miasto",
        name="Ulica 1",
        city="Miasto",
        city_slug="miasto",
        units=units,
    )


def trend_of(*periods: str) -> NeighbourhoodTrend:
    quarters = tuple(TrendQuarter(period=p, avg_price_per_m2=1.0) for p in periods)
    return NeighbourhoodTrend(radius_km=1.0, quarters=quarters)


@dataclass
class FakeBuildingCatalog:
    """``BuildingCatalog`` that records what it was asked and fails when told to; the
    trend has the quarters of ``trend_periods``."""

    building_error: Exception | None = None
    trend_error: Exception | None = None
    trend_periods: tuple[str, ...] = ("2024-Q4", "2025-Q1", "2025-Q2")
    calls: list[str] = field(default_factory=list)

    def building(self, slug: BuildingSlug) -> Building:
        self.calls.append(f"building {slug.value}")
        if self.building_error is not None:
            raise self.building_error
        return building_of(unit_sold(1, OLD), unit_sold(2, NEW), unit_sold(3, MID))

    def neighbourhood_trend(self, building: Building) -> NeighbourhoodTrend:
        self.calls.append(f"trend {building.building_id}")
        if self.trend_error is not None:
            raise self.trend_error
        return trend_of(*self.trend_periods)


class FakeBuildingLinks:
    def building(self, building: BuildingRef) -> str | None:
        return f"building:{building.city_slug}:{building.building_slug}"


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _building_catalog: ports.BuildingCatalog = FakeBuildingCatalog()
    _building_page_links: ports.BuildingPageLinks = FakeBuildingLinks()
