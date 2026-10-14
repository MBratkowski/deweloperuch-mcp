"""Use case ``RankLocations``: cities or powiats ranked by their RCN transactions, with what
to do about the places left out and the service's page of the ranking."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.location_ranking import (
    DEFAULT_RANKING_LIMIT,
    RANKING_LIMIT_MAX,
    LocationRanking,
    MinTransactions,
    RankingCriteria,
    RankingLevel,
    RankingLimit,
    RankingOrder,
)
from deweloperuch_mcp.usecases.ports import RankingLinks, TransactionRankingSource
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs


def _places(level: RankingLevel) -> str:
    """The places of ``level`` in the genitive plural, as in "Ranking powiatów"."""
    return "powiatów" if level is RankingLevel.POWIAT else "miejscowości"


@dataclass(frozen=True, kw_only=True)
class RankLocationsRequest:
    """What to rank, in which order, how many places and from how many transactions,
    checked (``parse``) before anything is sent."""

    criteria: RankingCriteria

    @classmethod
    def parse(
        cls,
        *,
        level: object = RankingLevel.CITY.value,
        sort: object = RankingOrder.TRANSACTIONS_DESC.value,
        limit: object = DEFAULT_RANKING_LIMIT,
        min_transactions: object = 0,
    ) -> Self:
        """Checked in this order: level, sort, limit, min_transactions. A refusal names the
        parameter (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(
                criteria=RankingCriteria(
                    level=RankingLevel.parse(level),
                    order=RankingOrder.parse(sort),
                    limit=RankingLimit.parse(limit),
                    min_transactions=MinTransactions.parse(min_transactions),
                )
            )


@dataclass(frozen=True, kw_only=True)
class RankLocationsResult:
    """The ranking with the service's page of the same ranking (D12; only cities have one)."""

    ranking: LocationRanking
    ranking_url: str | None

    @property
    def hint(self) -> str | None:
        """What to do when no place is left or the ranking is cut (D4)."""
        ranking = self.ranking
        criteria = ranking.criteria
        least = criteria.min_transactions.value
        if not ranking.items and least:
            return (
                f"Żadne miejsce nie ma co najmniej {least} transakcji: zmniejsz min_transactions."
            )
        if not ranking.truncated:
            return None
        shown = f"Pokazano pierwsze {ranking.returned} z {ranking.total} {_places(criteria.level)}"
        if criteria.limit.value >= RANKING_LIMIT_MAX:
            return (
                f"{shown}; to najwięcej w jednym wywołaniu. Pomiń małe miejsca przez "
                "min_transactions albo zmień sort."
            )
        return f"{shown}; kolejne pokaże większy limit (najwyżej {RANKING_LIMIT_MAX})."


class RankLocations:
    """One question to the source per ranking; the domain filters, orders and cuts it."""

    def __init__(self, source: TransactionRankingSource, links: RankingLinks) -> None:
        self._source = source
        self._links = links

    def execute(self, request: RankLocationsRequest) -> RankLocationsResult:
        criteria = request.criteria
        with ReportedAs(f"Ranking {_places(criteria.level)}"):
            places = self._source.locations(criteria.level)
        ranking = LocationRanking.of(criteria, places)
        url = self._links.city_ranking() if criteria.level is RankingLevel.CITY else None
        return RankLocationsResult(ranking=ranking, ranking_url=url)
