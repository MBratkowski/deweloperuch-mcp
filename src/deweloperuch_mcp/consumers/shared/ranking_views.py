"""The views of a ranking of cities or powiats: what ``rank_locations`` shows, for the CLI
(``--json``) and for the MCP presenter, and the choices of its parameters.

The views keep the models' names (D3): ``city_slug`` for a city, ``powiat_id`` for a
powiat, and the price per m², area and price as the service gives them (averages or
medians: the service does not say, T10 [H]). Each builds itself from a use case's result
(``from_result``) or a model (``from_model``).
"""

from typing import Literal, Self

from deweloperuch_mcp.consumers.shared.view import View
from deweloperuch_mcp.models.location_ranking import LocationTransactions
from deweloperuch_mcp.usecases.rank_locations import RankLocationsResult

RankingLevelChoice = Literal["city", "powiat"]
"""``models.location_ranking.RankingLevel``."""

RankingSortChoice = Literal["transactions_desc", "price_per_m2_desc", "price_per_m2_asc"]
"""``models.location_ranking.RankingOrder``."""


class RankedLocationView(View):
    """A city (``city_slug``) or a powiat (``powiat_id``) with its transactions."""

    name: str
    city_slug: str | None = None
    powiat_id: int | None = None
    transaction_count: int
    price_per_m2: float | None = None
    area_m2: float | None = None
    price: float | None = None

    @classmethod
    def from_model(cls, place: LocationTransactions) -> Self:
        return cls(
            name=place.name,
            city_slug=place.city_slug,
            powiat_id=place.powiat_id,
            transaction_count=place.transaction_count,
            price_per_m2=place.price_per_m2,
            area_m2=place.area_m2,
            price=place.price,
        )


class LocationRankingView(View):
    """The first places of a ranking (D4: the cut is explicit)."""

    level: str
    """``city`` or ``powiat``."""
    sort: str
    min_transactions: int
    total: int
    """Places with at least ``min_transactions`` transactions."""
    returned: int
    truncated: bool
    """More places meet the criteria than shown."""
    hint: str | None = None
    ranking_url: str | None = None
    """The service's page of the ranking of cities (D12); ``None`` for powiats."""
    items: list[RankedLocationView]

    @classmethod
    def from_result(cls, found: RankLocationsResult) -> Self:
        ranking = found.ranking
        criteria = ranking.criteria
        return cls(
            level=criteria.level.value,
            sort=criteria.order.value,
            min_transactions=criteria.min_transactions.value,
            total=ranking.total,
            returned=ranking.returned,
            truncated=ranking.truncated,
            hint=found.hint,
            ranking_url=found.ranking_url,
            items=[RankedLocationView.from_model(place) for place in ranking.items],
        )
