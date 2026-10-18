"""``BuildingTrendDto``: ``GET /api/avg-price-trend/building/{investRcnId}`` [P] (sample
``api.avg_trend_building``), the price per m² around a building quarter by quarter
(``TrendQuarterDto``)."""

from deweloperuch_mcp.api.dto.dto import Dto, Number, QuarterText
from deweloperuch_mcp.models.building import NeighbourhoodTrend, TrendQuarter


class TrendQuarterDto(Dto):
    period: QuarterText
    avgPriceSqm: Number | None
    count: Number | None = None

    def to_model(self) -> TrendQuarter:
        return TrendQuarter(
            period=self.period,
            # [W] 0 or less is no price: no such quarter is known, but the service writes
            # 0 for no value in its monthly statistics and city-transaction-stats [P].
            avg_price_per_m2=self._positive(self.avgPriceSqm),
            transactions=self._exact_whole(self.count),
        )


class BuildingTrendDto(Dto):
    """``GET /api/avg-price-trend/building/{investRcnId}`` [P] (sample
    ``api.avg_trend_building``)."""

    data: list[TrendQuarterDto]
    radiusKm: Number | None = None

    def to_model(self) -> NeighbourhoodTrend:
        """Every quarter, oldest first.

        [W] docs/discovery/endpoints.md, avg-price-trend/building: the trend of the
        transactions within ``radiusKm`` of the building; that ``avgPriceSqm`` is their mean
        price per m² and ``count`` their number follows from the names.
        """
        return NeighbourhoodTrend(
            # A trend without quarters comes with `radiusKm` 0 [P 2026-10-15]
            # (tests/fixtures/api/avg_trend_building_152198_20261015.json): no radius.
            radius_km=self._positive(self.radiusKm),
            quarters=tuple(
                item.to_model() for item in sorted(self.data, key=lambda item: item.period)
            ),
        )
