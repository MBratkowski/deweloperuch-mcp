"""Contract of ``deweloperuch_mcp.api.adapters.transaction_statistics_api`` with the
service's real answers (the samples in docs/discovery/samples/, the raw payloads in
tests/fixtures/).
"""

from deweloperuch_mcp.allowlist import match_api, match_dump
from support.providers.samples import request_target


def test_the_samples_were_captured_with_the_requests_the_client_sends() -> None:
    assert request_target("api.monthly_tx") == (
        "/api/monthly-transaction-stats?propertyType=mieszkania&citySlug=warszawa"
    )
    assert request_target("api.avg_trend_city") == "/api/avg-price-trend/city/warszawa"
    for target in (request_target("api.monthly_tx"), request_target("api.avg_trend_city")):
        path = target.split("?", 1)[0]
        assert match_api(path) is not None
        assert match_dump(path) is None
