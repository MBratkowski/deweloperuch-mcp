"""Contract of ``deweloperuch_mcp.api.adapters.buildings_api`` with the service's real
answers (the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from deweloperuch_mcp import identity
from deweloperuch_mcp.allowlist import match_api
from support.providers.routes.buildings import BUILDING_ID, TREND
from support.providers.samples import body, request_target


def test_the_trend_mock_is_asked_for_by_the_number_of_the_sample_building() -> None:
    assert body("api.tx_visible")["invest_rcn_id"] == BUILDING_ID
    assert request_target("api.avg_trend_building") == "/api/avg-price-trend/building/583284"
    assert match_api(TREND.removeprefix(identity.BASE_URL)) == (
        "/api/avg-price-trend/building/" + "{investRcnId}"
    )
