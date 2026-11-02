"""The views of a ranking of cities, powiats or cities by an indicator: what
``rank_locations`` shows, for the CLI (``--json``) and for the MCP presenter, and the
choices of its parameters.

The views keep the models' names (D3): ``city_slug`` for a city, ``powiat_id`` for a
powiat, and the price per m², area and price as the service gives them (averages or
medians: the service does not say, T10, T85 [H]); an indicator's ``value`` in its
``unit``. Each builds itself from a use case's result (``from_result``) or a model
(``from_model``, ``from_indicator``).
"""

from typing import Literal, Self

from deweloperuch_mcp.consumers.shared.view import View
from deweloperuch_mcp.models.indicator_ranking import CityIndicator, IndicatorRanking
from deweloperuch_mcp.models.location_ranking import (
    LocationRanking,
    LocationTransactions,
    RankingLevel,
)
from deweloperuch_mcp.usecases.rank_locations import RankLocationsResult

RankingLevelChoice = Literal["city", "powiat"]
"""``models.location_ranking.RankingLevel``."""

RankingSortChoice = Literal[
    "transactions_desc", "price_per_m2_desc", "price_per_m2_asc", "value_desc", "value_asc"
]
"""``models.location_ranking.RankingOrder``."""

RankingMarketChoice = Literal["secondary", "primary", "all"]
"""``models.location_ranking.RankingMarket``."""

IndicatorChoice = Literal[
    "unemployment_rate",
    "average_wage",
    "dwellings_completed",
    "dwellings_started",
    "average_dwelling_area",
    "natural_increase",
    "nbp_price_per_m2",
]
"""``models.indicator_ranking.Indicator``."""


class RankedLocationView(View):
    """A city (``city_slug``) or a powiat (``powiat_id``) with its transactions, or a city
    with its value of an indicator (``value``, ``stats_url``)."""

    name: str
    city_slug: str | None = None
    powiat_id: int | None = None
    transaction_count: int | None = None
    price_per_m2: float | None = None
    area_m2: float | None = None
    price: float | None = None
    value: float | None = None
    stats_url: str | None = None
    """The city's page of government statistics (D12); indicator rankings only."""

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

    @classmethod
    def from_indicator(cls, city: CityIndicator, stats_url: str | None) -> Self:
        return cls(name=city.name, city_slug=city.city_slug, value=city.value, stats_url=stats_url)


class LocationRankingView(View):
    """The first places of a ranking (D4: the cut is explicit)."""

    level: str
    """``city`` or ``powiat``; an indicator ranks cities."""
    sort: str
    min_transactions: int | None = None
    """The threshold applied: ``min_transactions`` as given, else the order's default;
    ``None`` for an indicator ranking."""
    market: str | None = None
    """The market of a powiat ranking."""
    period_start: str | None = None
    """The first day of a powiat ranking's months (``2025-11-01``)."""
    period_end: str | None = None
    """The last month of a powiat ranking (``2026-10``)."""
    indicator: str | None = None
    unit: str | None = None
    """The unit of an indicator's values."""
    period: str | None = None
    """The period of an indicator's values (``2026-08``, ``2026-Q2``, ``2025``)."""
    total: int
    """Places that meet the criteria (with a value, for an indicator)."""
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
        if isinstance(ranking, IndicatorRanking):
            return cls._of_indicator(found, ranking)
        return cls._of_transactions(found, ranking)

    @classmethod
    def _of_transactions(cls, found: RankLocationsResult, ranking: LocationRanking) -> Self:
        criteria = ranking.criteria
        period = found.period
        powiats = criteria.level is RankingLevel.POWIAT
        return cls(
            level=criteria.level.value,
            sort=criteria.order.value,
            min_transactions=criteria.threshold.value,
            market=criteria.powiat_market.value if powiats else None,
            period_start=period.start if period is not None else None,
            period_end=period.end if period is not None else None,
            total=ranking.total,
            returned=ranking.returned,
            truncated=ranking.truncated,
            hint=found.hint,
            ranking_url=found.ranking_url,
            items=[RankedLocationView.from_model(place) for place in ranking.items],
        )

    @classmethod
    def _of_indicator(cls, found: RankLocationsResult, ranking: IndicatorRanking) -> Self:
        criteria = ranking.criteria
        return cls(
            level="city",
            sort=criteria.order.value,
            indicator=criteria.indicator.value,
            unit=criteria.indicator.unit,
            period=ranking.period,
            total=ranking.total,
            returned=ranking.returned,
            truncated=ranking.truncated,
            hint=found.hint,
            items=[
                RankedLocationView.from_indicator(city, url)
                for city, url in zip(ranking.items, found.stats_urls, strict=True)
            ],
        )
