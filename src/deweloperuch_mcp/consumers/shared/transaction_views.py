"""The views of the transaction statistics: what ``get_transaction_statistics`` shows, for the
CLI (``--json``: every measure, the averages of area and price included) and for the MCP
presenter, which cuts it down. Each builds itself from a use case's result (``from_result``)
or a model (``from_model``), field for field with the model (``models.transaction_series``).
"""

from typing import Self

from deweloperuch_mcp.consumers.shared.view import View
from deweloperuch_mcp.models.transaction_series import Granularity, TransactionPeriod
from deweloperuch_mcp.usecases.get_transaction_statistics import GetTransactionStatisticsResult


class TransactionPeriodView(View):
    """The transactions of one period; a measure the service does not give is ``None``."""

    period: str
    """``2025-08`` (month) or ``2025-Q3`` (quarter)."""
    transactions: int
    incomplete: bool = False
    """Fewer than half the usual number of transactions at the end of the series: the
    register's data for it is not complete yet."""
    median_price_per_m2: float | None = None
    average_price_per_m2: float | None = None
    median_area_m2: float | None = None
    average_area_m2: float | None = None
    median_price: float | None = None
    average_price: float | None = None

    @classmethod
    def from_model(cls, item: TransactionPeriod) -> Self:
        return cls(
            period=item.period,
            transactions=item.transactions,
            incomplete=item.incomplete,
            median_price_per_m2=item.median_price_per_m2,
            average_price_per_m2=item.average_price_per_m2,
            median_area_m2=item.median_area_m2,
            average_area_m2=item.average_area_m2,
            median_price=item.median_price,
            average_price=item.average_price,
        )


class TransactionStatisticsView(View):
    """The latest periods of the RCN transaction prices of flats in a city (D4)."""

    city_slug: str
    granularity: Granularity
    total: int
    """Periods the service has for the city at this granularity."""
    returned: int
    truncated: bool
    """Older periods exist than the ones shown."""
    available_from: str
    """The oldest period the service has."""
    last_complete_period: str | None
    """The newest period with a usual number of transactions (its data may still change);
    ``None`` when there is too little history, or too few transactions, to tell."""
    hint: str | None
    note: str
    """The latest periods are incomplete (the RCN publishes transactions late)."""
    stats_url: str | None
    """The service's page of these statistics (D12), for people."""
    periods: list[TransactionPeriodView]

    @classmethod
    def from_result(cls, found: GetTransactionStatisticsResult) -> Self:
        statistics = found.statistics
        return cls(
            city_slug=statistics.city_slug,
            granularity=statistics.granularity,
            total=statistics.total,
            returned=statistics.returned,
            truncated=statistics.truncated,
            available_from=statistics.available_from,
            last_complete_period=statistics.last_complete_period,
            hint=found.hint,
            note=statistics.note,
            stats_url=found.stats_url,
            periods=[TransactionPeriodView.from_model(item) for item in statistics.periods],
        )
