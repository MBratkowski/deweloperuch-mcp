"""Tests of ``deweloperuch_mcp.api.dto.standalone_valuation_dto``."""

import copy

from deweloperuch_mcp.api.dto.standalone_valuation_dto import ValuationStatsDto
from support.builders.valuation import api_sample, mapped


def test_mapping_does_not_change_the_data() -> None:
    data = api_sample()
    before = copy.deepcopy(data)

    mapped(data)

    assert data == before


def test_the_count_and_the_months_are_rounded() -> None:
    """The service's own figures, kept as whole numbers: 1.5 -> 2 (not refused)."""
    stats = ValuationStatsDto(
        averagePricePerSqm=None,
        medianPricePerSqm=None,
        minPricePerSqm=None,
        maxPricePerSqm=None,
        count=1.5,
    )

    assert stats.to_model().count == 2
