"""Contract of ``deweloperuch_mcp.api.dto.monthly_transaction_stats_dto`` with the
service's real answers (the samples in docs/discovery/samples/, the raw payloads in
tests/fixtures/).
"""

from deweloperuch_mcp.api.dto.monthly_transaction_stats_dto import MonthlyTransactionStatsDto
from deweloperuch_mcp.models.government_statistics import PeriodCount
from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionCity,
    TransactionSeries,
)
from support.builders.transactions import WARSZAWA, karpacz_months, warszawa_months
from support.providers.samples import body


def test_the_monthly_sample() -> None:
    parsed = MonthlyTransactionStatsDto.model_validate(body("api.monthly_tx"))

    first = parsed.data[0]
    assert [row.month for row in parsed.data] == ["2021-01", "2021-02", "2021-03"]
    assert (first.transaction_count, first.med_price_sqm, first.avg_price_sqm) == (
        963,
        10651,
        10876,
    )
    assert (first.med_size, first.avg_size) == (49.4, 54.6)
    assert (first.med_amount, first.avg_amount) == (502000, 596261)


def test_every_month_of_warsaw_ends_with_three_incomplete_ones() -> None:
    """tests/fixtures/api/monthly_tx_warszawa_20261015.json, whole: 67 months; 2026-05,
    2026-06 (every measure 0) and 2026-07 (a median price per m² about twice the usual)
    are incomplete, 2026-04 (987 transactions) is the last complete month."""
    months = MonthlyTransactionStatsDto.model_validate(warszawa_months()).to_model()

    found = TransactionSeries(WARSZAWA, Granularity.MONTH, months).latest(PeriodCount(67))

    assert (found.total, found.available_from) == (67, "2021-01")
    assert [item.period for item in found.periods if item.incomplete] == [
        "2026-05",
        "2026-06",
        "2026-07",
    ]
    assert found.last_complete_period == "2026-04"
    tail = {item.period: item for item in found.periods[-4:]}
    assert [item.transactions for item in tail.values()] == [987, 22, 0, 35]
    assert tail["2026-06"].measures == (None,) * 6
    assert tail["2026-07"].median_price_per_m2 == 33176


def test_every_month_of_a_small_town_is_too_few_to_judge() -> None:
    """tests/fixtures/api/monthly_tx_karpacz_20261016.json, whole: 60 months to 2025-12,
    a median of 1 transaction a month, 26 months without any. Nothing is flagged, and no
    month is known to be complete."""
    months = MonthlyTransactionStatsDto.model_validate(karpacz_months()).to_model()
    karpacz = TransactionCity("karpacz")

    found = TransactionSeries(karpacz, Granularity.MONTH, months).latest(PeriodCount(60))

    assert (found.total, found.available_from, found.periods[-1].period) == (
        60,
        "2021-01",
        "2025-12",
    )
    assert sum(item.transactions == 0 for item in found.periods) == 26
    assert not any(item.incomplete for item in found.periods)
    assert found.last_complete_period is None
    assert found.few_transactions is True
