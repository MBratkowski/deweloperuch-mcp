"""``CityTrendDto``: ``GET /api/avg-price-trend/city/{citySlug}`` [P] (sample
``api.avg_trend_city``: Warsaw, 2017-Q1..2026-Q3), every quarter of the price trend of a
city."""

from typing import Literal

from deweloperuch_mcp.api.dto.dto import Dto, Number, QuarterText
from deweloperuch_mcp.api.dto.transaction_period_dto import TransactionPeriodDto
from deweloperuch_mcp.models.transaction_series import TransactionPeriod


class CityTrendQuarterDto(TransactionPeriodDto):
    """A quarter of ``CityTrendDto`` [P]."""

    period: QuarterText
    avgPriceSqm: Number | None
    count: int

    def to_model(self) -> TransactionPeriod:
        # [W] docs/discovery/endpoints.md, avg-price-trend: `avgPriceSqm` is read as the mean
        # price of one m² and `count` as the number of transactions of the quarter (their
        # names); the endpoint gives no median, area or price of a flat.
        return TransactionPeriod(
            period=self.period,
            transactions=self.count,
            average_price_per_m2=self._measure(self.count, self.avgPriceSqm),
        )


class CityTrendDto(Dto):
    """``scope`` is the echo of what the trend covers: a city [P]; anything else is not
    the city's data. ``scopeName`` (``null`` in the sample) is not needed."""

    scope: Literal["city"]
    data: list[CityTrendQuarterDto]

    def to_model(self) -> tuple[TransactionPeriod, ...]:
        """The quarters in the service's order."""
        return tuple(row.to_model() for row in self.data)
