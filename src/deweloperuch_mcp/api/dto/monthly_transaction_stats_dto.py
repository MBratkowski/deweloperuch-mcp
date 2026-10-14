"""``MonthlyTransactionStatsDto``: ``GET /api/monthly-transaction-stats?propertyType=&citySlug=``
[P] (sample ``api.monthly_tx``: Warsaw, 2021-01..2026-07), every month of the transactions of
flats in a city."""

from typing import Literal

from deweloperuch_mcp.api.dto.dto import Dto, MonthText, Number
from deweloperuch_mcp.api.dto.transaction_period_dto import TransactionPeriodDto
from deweloperuch_mcp.models.transaction_series import TransactionPeriod


class MonthlyTransactionsDto(TransactionPeriodDto):
    """A month of ``MonthlyTransactionStatsDto`` [P]: every field is in the sample."""

    month: MonthText
    transaction_count: int
    med_price_sqm: Number | None
    avg_price_sqm: Number | None
    med_size: Number | None
    avg_size: Number | None
    med_amount: Number | None
    avg_amount: Number | None

    def to_model(self) -> TransactionPeriod:
        # [W] docs/discovery/endpoints.md: `med_*` is read as the median and `avg_*` as the
        # mean (their names; no page text says so). They differ in every month of the sample
        # (10651 vs 10876 PLN/m²...), so here `avg_*` is not a median in disguise (cf. T10,
        # which is about another endpoint).
        count = self.transaction_count
        return TransactionPeriod(
            period=self.month,
            transactions=count,
            median_price_per_m2=self._measure(count, self.med_price_sqm),
            average_price_per_m2=self._measure(count, self.avg_price_sqm),
            median_area_m2=self._measure(count, self.med_size),
            average_area_m2=self._measure(count, self.avg_size),
            median_price=self._measure(count, self.med_amount),
            average_price=self._measure(count, self.avg_amount),
        )


class MonthlyScopeDto(Dto):
    """What the series covers, as the service echoes it: a city [P] (``label: "city"``
    for ``citySlug``). Another label means the data is not the city's."""

    label: Literal["city"]


class MonthlyTransactionStatsDto(Dto):
    scope: MonthlyScopeDto
    data: list[MonthlyTransactionsDto]

    def to_model(self) -> tuple[TransactionPeriod, ...]:
        """The months in the service's order."""
        return tuple(row.to_model() for row in self.data)
