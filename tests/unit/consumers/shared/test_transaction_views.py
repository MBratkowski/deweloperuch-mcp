"""Tests of ``deweloperuch_mcp.consumers.shared.transaction_views``."""

from deweloperuch_mcp.consumers.shared.transaction_views import TransactionStatisticsView
from deweloperuch_mcp.models.government_statistics import PeriodCount
from deweloperuch_mcp.usecases.get_transaction_statistics import GetTransactionStatisticsResult
from support.builders.transactions import WARSZAWA_LAST_16_MONTHS, counted


def view_of(*counts: int, periods: int) -> TransactionStatisticsView:
    statistics = counted("2025-04", *counts).latest(PeriodCount(periods))
    return TransactionStatisticsView.from_result(
        GetTransactionStatisticsResult(statistics=statistics, stats_url=None)
    )


def test_the_view_carries_the_incomplete_periods_and_the_last_complete_one() -> None:
    """2025-04..2026-07 of tests/fixtures/api/monthly_tx_warszawa_20261015.json."""
    shown = view_of(*WARSZAWA_LAST_16_MONTHS, periods=4)

    assert [(item.period, item.incomplete) for item in shown.periods] == [
        ("2026-04", False),
        ("2026-05", True),
        ("2026-06", True),
        ("2026-07", True),
    ]
    assert shown.last_complete_period == "2026-04"
    assert shown.hint is not None and "Okresy 2026-05, 2026-06 i 2026-07" in shown.hint


def test_without_enough_history_the_view_has_no_last_complete_period() -> None:
    shown = view_of(*WARSZAWA_LAST_16_MONTHS[:3], periods=3)

    assert shown.last_complete_period is None
    assert not any(item.incomplete for item in shown.periods)
