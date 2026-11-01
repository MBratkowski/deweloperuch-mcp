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
        # [P 2026-10-30] docs/discovery/endpoints.md, avg-price-trend/city: despite its name,
        # `avgPriceSqm` is the median price of one m² of the quarter. In the 36 quarters
        # 2017-Q1..2025-Q4 of Warsaw it lies within 2.41 PLN/m² of the median of the
        # service's statistics page (`medSqm`), whose quarters have the same counts, and
        # 165 PLN/m² or more from its mean (`avgSqm`); the same on the page of 2026-10-31
        # (tests/contract/api/dto/test_city_trend_dto.py). `count`: the number of
        # transactions of the quarter (its name, [W]). The trend gives no mean, no area and
        # no price of a flat. Which market it covers is open (T45): it counts 2–4 % more
        # transactions than the page's months of the secondary market (the closed quarters of
        # Warsaw 2017-Q1..2026-Q1 against the sums of their months, the fixtures of
        # 2026-10-16 and 2026-10-31).
        return TransactionPeriod(
            period=self.period,
            transactions=self.count,
            median_price_per_m2=self._measure(self.count, self.avgPriceSqm),
        )


class CityTrendDto(Dto):
    """``scope`` is the echo of what the trend covers: a city [P]; anything else is not
    the city's data. ``scopeName`` (``null`` in the sample) is not needed."""

    scope: Literal["city"]
    data: list[CityTrendQuarterDto]

    def to_model(self) -> tuple[TransactionPeriod, ...]:
        """The quarters in the service's order."""
        return tuple(row.to_model() for row in self.data)
