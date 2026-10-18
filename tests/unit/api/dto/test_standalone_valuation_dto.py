"""Tests of ``deweloperuch_mcp.api.dto.standalone_valuation_dto``."""

import copy

import pytest

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


@pytest.mark.parametrize(("count", "expected"), [(-1, None), ("-3", None), (0, 0), ("26", 26)])
def test_a_negative_count_is_no_count(count: object, expected: int | None) -> None:
    """No count is below 0; 0 stays 0 (Valuation.counted_comparables then counts the
    transactions given)."""
    data = api_sample()
    data["stats"]["count"] = count

    stats = mapped(data).stats

    assert stats is not None and stats.count == expected
