"""Tests of ``deweloperuch_mcp.api.dto.building_trend_dto``."""

from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.building_trend_dto import BuildingTrendDto
from deweloperuch_mcp.models.building import TrendQuarter
from support.providers.samples import body


def test_the_trend_of_the_sample_oldest_first() -> None:
    data = body("api.avg_trend_building")
    data["data"].reverse()

    trend = BuildingTrendDto.model_validate(data).to_model()

    assert trend.radius_km == 1.0
    assert trend.quarters == (
        TrendQuarter(period="2006-Q2", avg_price_per_m2=5706.0, transactions=25),
        TrendQuarter(period="2006-Q3", avg_price_per_m2=6188.0, transactions=38),
        TrendQuarter(period="2006-Q4", avg_price_per_m2=6668.0, transactions=38),
    )
    assert (trend.total, trend.omitted) == (3, 0)


@pytest.mark.parametrize(
    "rows",
    [
        [dict(period="2006-Q5", avgPriceSqm=1, count=1)],
        [dict(period="2006", avgPriceSqm=1, count=1)],
        [dict(period="2006-Q1", avgPriceSqm="dużo", count=1)],
    ],
)
def test_a_trend_of_another_shape_is_refused(rows: list[dict[str, Any]]) -> None:
    with pytest.raises(ValidationError):
        BuildingTrendDto.model_validate(dict(data=rows, radiusKm=1))


@pytest.mark.parametrize("zero", [0, "0", -1], ids=["0", "text 0", "-1"])
def test_a_quarter_price_of_0_or_less_is_no_price(zero: object) -> None:
    """A rule test on a hand-edited payload: the trend sample with the price of its
    first quarter replaced by 0 or less. [W] no real quarter with such a price is known;
    the service writes 0 for no value in its monthly statistics and
    ``city-transaction-stats`` [P], and no flat costs 0. The quarter itself stays."""
    data = body("api.avg_trend_building")
    data["data"][0]["avgPriceSqm"] = zero

    trend = BuildingTrendDto.model_validate(data).to_model()

    assert trend.quarters[0] == TrendQuarter(
        period="2006-Q2", avg_price_per_m2=None, transactions=25
    )
    assert trend.quarters[1].avg_price_per_m2 == 6188.0


@pytest.mark.parametrize(
    "radius", [0, "0", -1, "", None], ids=["0", "text 0", "-1", "empty", "null"]
)
def test_a_radius_of_0_or_less_is_no_radius(radius: object) -> None:
    """0 is the service's own for a trend without quarters [P 2026-10-15]
    (tests/contract); less than 0 is no radius either (a rule test on a hand-edited
    payload: the trend sample with its radius replaced)."""
    data = body("api.avg_trend_building")
    data["radiusKm"] = radius

    trend = BuildingTrendDto.model_validate(data).to_model()

    assert (trend.radius_km, trend.total) == (None, 3)


@pytest.mark.parametrize(("count", "transactions"), [(25, 25), ("25", 25), (1.5, None)])
def test_the_count_of_a_quarter_is_a_whole_number_or_none(
    count: float | str, transactions: int | None
) -> None:
    rows = [dict(period="2006-Q2", avgPriceSqm=5706, count=count)]

    trend = BuildingTrendDto.model_validate(dict(data=rows, radiusKm=1)).to_model()

    assert trend.quarters[0].transactions == transactions
