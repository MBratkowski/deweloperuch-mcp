"""Contract of ``deweloperuch_mcp.api.dto.powiat_transactions_list_dto`` with the service's
real answers (the samples in docs/discovery/samples/, the raw payloads in
tests/fixtures/).
"""

from deweloperuch_mcp.api.adapters.transaction_ranking_api import POWIAT_RANKING
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.powiat_transactions_list_dto import PowiatTransactionsListDto
from support.providers.routes.rankings import POWIATS_2026_10_15, captured
from support.providers.samples import body


def test_no_powiat_has_zeros_and_each_has_at_least_17_transactions() -> None:
    """[P 2026-10-15]: every powiat has its price per m², area and price, and the fewest
    transactions is 17, so the price orders' default threshold (20) leaves out few."""
    rows = captured(POWIATS_2026_10_15)
    powiats = Dto.validated(PowiatTransactionsListDto, rows, POWIAT_RANKING).to_model()

    assert len(powiats) == 380
    assert all(None not in (p.price_per_m2, p.area_m2, p.price) for p in powiats)
    assert min(p.transaction_count for p in powiats) == 17


def test_powiat_counts_span_many_years_city_counts_about_a_quarter() -> None:
    """[W] behind "Liczby transakcji powiatów obejmują wiele lat: służą tylko do
    uporządkowania" in the MCP description. Warszawa is a city with powiat rights (its only
    powiat is 302, ``api.city_powiats_waw``), so both levels cover the same area; its
    months have about 1.0-1.3k transactions (``api.monthly_tx``) [P 2026-10-09]. The
    powiat count is over 100 such months, the city count about three. The period itself
    stays unknown (T10)."""
    assert body("api.city_powiats_waw") == {"powiatIds": [302], "primaryPowiatId": 302}
    months = [month["transaction_count"] for month in body("api.monthly_tx")["data"]]
    city = next(c for c in body("api.city_tx_stats") if c["city_slug"] == "warszawa")
    powiat = next(p for p in body("api.powiat_stats") if p["powiat_rcn_id"] == 302)

    assert powiat["transaction_count"] > 100 * max(months)
    assert 2 * min(months) < city["transaction_count"] < 4 * max(months)
