"""Contract of ``deweloperuch_mcp.api.dto.monthly_transaction_stats_dto`` with the
service's real answers (the samples in docs/discovery/samples/, the raw payloads in
tests/fixtures/).
"""

from deweloperuch_mcp.api.dto.monthly_transaction_stats_dto import MonthlyTransactionStatsDto
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
