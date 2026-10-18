"""Contract of ``deweloperuch_mcp.api.dto.building_trend_dto`` with the service's real
answers (the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from deweloperuch_mcp.api.dto.building_trend_dto import BuildingTrendDto
from support.providers.routes.buildings import CISNA_TREND_BODY, fixture_body
from support.providers.samples import body


def test_the_trend_sample_parses() -> None:
    parsed = BuildingTrendDto.model_validate(body("api.avg_trend_building"))

    assert parsed.radiusKm == 1
    assert [(q.period, q.avgPriceSqm, q.count) for q in parsed.data] == [
        ("2006-Q2", 5706, 25),
        ("2006-Q3", 6188, 38),
        ("2006-Q4", 6668, 38),
    ]


def test_a_trend_without_quarters_has_no_radius() -> None:
    """tests/fixtures/api/avg_trend_building_152198_20261015.json [P 2026-10-15]: for a
    building the service has no trend around, a 200 with no quarters and a radius of 0,
    which is no radius."""
    parsed = BuildingTrendDto.model_validate(fixture_body(CISNA_TREND_BODY))

    assert (parsed.data, parsed.radiusKm) == ([], 0)

    trend = parsed.to_model()

    assert (trend.quarters, trend.radius_km, trend.total, trend.empty) == ((), None, 0, True)
