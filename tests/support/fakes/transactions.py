"""``TransactionStatisticsSource`` and ``TransactionStatisticsLinks`` in memory."""

from typing import TYPE_CHECKING

from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionCity,
    TransactionSeries,
)
from deweloperuch_mcp.usecases import ports


class FakeTransactionSource:
    def __init__(self, found: TransactionSeries | Exception) -> None:
        self.found = found
        self.asked: list[tuple[TransactionCity, Granularity]] = []

    def transaction_series(
        self, city: TransactionCity, granularity: Granularity
    ) -> TransactionSeries:
        self.asked.append((city, granularity))
        if isinstance(self.found, Exception):
            raise self.found
        return self.found


class FakeTransactionLinks:
    """``TransactionStatisticsLinks`` that says what it was asked for."""

    def transaction_statistics(self, city: TransactionCity) -> str | None:
        return f"link:{city.value}"


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _transaction_statistics_source: ports.TransactionStatisticsSource = FakeTransactionSource(
        Exception()
    )
    _transaction_statistics_links: ports.TransactionStatisticsLinks = FakeTransactionLinks()
