"""Contract of ``deweloperuch_mcp.api.dto.building_trend_dto`` with the service's real
answers (the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from deweloperuch_mcp.api.dto.building_trend_dto import BuildingTrendDto
from support.providers.samples import body


def test_the_trend_sample_parses() -> None:
    parsed = BuildingTrendDto.model_validate(body("api.avg_trend_building"))

    assert parsed.radiusKm == 1
    assert [(q.period, q.avgPriceSqm, q.count) for q in parsed.data] == [
        ("2006-Q2", 5706, 25),
        ("2006-Q3", 6188, 38),
        ("2006-Q4", 6668, 38),
    ]
