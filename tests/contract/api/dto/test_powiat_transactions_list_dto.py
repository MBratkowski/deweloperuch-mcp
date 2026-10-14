"""Contract of ``deweloperuch_mcp.api.dto.powiat_transactions_list_dto`` with the service's
real answers (the samples in docs/discovery/samples/, the raw payloads in
tests/fixtures/).
"""

from support.providers.samples import body


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
