"""Contract of ``deweloperuch_mcp.api.adapters.transaction_statistics_api`` with the
service's real answers (the samples in docs/discovery/samples/, the raw payloads in
tests/fixtures/).
"""

from pathlib import Path

import pytest
import respx

from deweloperuch_mcp.allowlist import match_api, match_dump, match_page
from deweloperuch_mcp.api.adapters.transaction_statistics_api import TransactionStatisticsApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.transaction_series import Granularity, TransactionCity
from support.providers.routes.offers import RSC_HEADERS
from support.providers.rsc import STATS_TX_KARPACZ_20261031, STATS_TX_WARSZAWA_20261031, raw
from support.providers.samples import request_target


def test_the_samples_were_captured_with_the_requests_the_client_sends() -> None:
    """The months: the page of the samples of 2.0, an allowed page and no dump (the 1.0
    page with every transaction, ``page.stats_transactions``, is one); the quarters: the
    trend's sample, an allowed path."""
    page = request_target("page.stats_transactions.v2_view")
    assert page == "/statystyki/warszawa/transakcje"
    assert TransactionStatisticsApi.stats_path("warszawa") == page
    assert request_target("page.stats_transactions.v2_latest_summary") == page
    assert match_page(page) == "/statystyki/{location}/transakcje"
    assert match_dump(page) is None
    assert match_dump(request_target("page.stats_transactions")) is not None
    trend = request_target("api.avg_trend_city")
    assert trend == "/api/avg-price-trend/city/warszawa"
    assert match_api(trend) is not None
    assert match_dump(trend) is None


@pytest.mark.parametrize(
    ("city", "page", "with_transactions", "newest"),
    [
        ("warszawa", STATS_TX_WARSZAWA_20261031, 114, "2026-07"),
        ("karpacz", STATS_TX_KARPACZ_20261031, 67, "2025-12"),
    ],
)
def test_every_month_of_the_real_pages(
    http: HttpClient,
    service: respx.MockRouter,
    city: str,
    page: Path,
    with_transactions: int,
    newest: str,
) -> None:
    """tests/fixtures/rsc/stats_tx_*_20261031.rsc, requested as the client requests them
    (``/statystyki/{city}/transakcje?_rsc=``, tests/fixtures/rsc/README.md): every month
    with transactions, up to the newest of them."""
    route = service.get(path=f"/statystyki/{city}/transakcje").respond(
        200, content=raw(page), headers=RSC_HEADERS
    )

    found = TransactionStatisticsApi(http).transaction_series(
        TransactionCity(city), Granularity.MONTH
    )

    assert route.calls.last.request.url.raw_path.decode() == f"/statystyki/{city}/transakcje?_rsc="
    assert (found.periods[0].period, found.periods[-1].period) == ("2017-01", newest)
    assert sum(item.transactions > 0 for item in found.periods) == with_transactions
