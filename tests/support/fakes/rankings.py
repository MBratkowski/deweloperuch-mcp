"""``TransactionRankingSource`` and ``RankingLinks`` in memory, and the places they rank."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from deweloperuch_mcp.models.location_ranking import (
    LocationTransactions,
    RankingLevel,
)
from deweloperuch_mcp.usecases import ports


def city(
    name: str, count: int, price_per_m2: float | None = 10_000.0, slug: str | None = None
) -> LocationTransactions:
    return LocationTransactions(
        name=name,
        city_slug=slug or name.lower(),
        transaction_count=count,
        price_per_m2=price_per_m2,
        area_m2=50.0,
        price=500_000.0,
    )


# Figures of the sample api.city_tx_stats [P 2026-10-09] and made-up small places.
WARSZAWA = city("Warszawa", 3606, 16413.0)


KRAKOW = city("Kraków", 1492, 14606.0, "krakow")


WROCLAW = city("Wrocław", 1443, 12437.0, "wroclaw")


VILLAGE = city("Wieś", 1, 30_000.0)


NO_PRICE = city("Bez ceny", 2, None)


CITIES = (WROCLAW, VILLAGE, WARSZAWA, NO_PRICE, KRAKOW)


@dataclass
class FakeRankingSource:
    """``TransactionRankingSource`` that answers from ``locations_of`` or raises ``error``."""

    locations_of: dict[RankingLevel, tuple[LocationTransactions, ...]] = field(
        default_factory=lambda: {RankingLevel.CITY: CITIES, RankingLevel.POWIAT: ()}
    )
    error: Exception | None = None
    asked: list[RankingLevel] = field(default_factory=list)

    def locations(self, level: RankingLevel) -> tuple[LocationTransactions, ...]:
        self.asked.append(level)
        if self.error is not None:
            raise self.error
        return self.locations_of[level]


class FakeRankingLinks:
    def city_ranking(self) -> str | None:
        return "<ranking miast>"


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _transaction_ranking_source: ports.TransactionRankingSource = FakeRankingSource()
    _ranking_links: ports.RankingLinks = FakeRankingLinks()
