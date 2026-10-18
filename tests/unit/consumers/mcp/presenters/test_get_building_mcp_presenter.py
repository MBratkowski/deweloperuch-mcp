"""Tests of ``deweloperuch_mcp.consumers.mcp.presenters.get_building_mcp_presenter``."""

from deweloperuch_mcp.consumers.mcp.presenters.get_building_mcp_presenter import (
    GetBuildingMcpPresenter,
)
from deweloperuch_mcp.consumers.mcp.support.mcp_model import dump
from deweloperuch_mcp.models.building import (
    ENFORCEMENT,
    REGULAR,
    SHARE,
    NeighbourhoodTrend,
    UnitsLimit,
)
from deweloperuch_mcp.usecases.get_building import NO_TREND_QUARTERS, GetBuildingResult
from support.fakes.buildings import building_of, trend_of, unit_sold_as


def test_regular_sales_only_and_no_hint_add_no_field() -> None:
    result = GetBuildingResult(
        listing=building_of(unit_sold_as(1, REGULAR, None)).listing(),
        trend=trend_of("2025-Q1"),
        building_url=None,
    )

    shown = dump(GetBuildingMcpPresenter().present(result))

    assert "non_regular_transactions" not in shown
    assert "hint" not in shown
    assert shown["neighbourhood_trend"]["radius_km"] == 1.0


def test_the_other_transactions_of_the_building_and_a_trend_without_quarters() -> None:
    """The counts are the whole building's, also when no unit is listed; an empty trend
    keeps its counters (D4), has no radius and the hint says why."""
    result = GetBuildingResult(
        listing=building_of(
            unit_sold_as(1, SHARE, REGULAR), unit_sold_as(2, ENFORCEMENT, "nowa_klasa")
        ).listing(UnitsLimit(0)),
        trend=NeighbourhoodTrend(radius_km=None, quarters=()),
        building_url=None,
    )

    shown = dump(GetBuildingMcpPresenter().present(result))

    assert list(shown["non_regular_transactions"].items()) == [
        (ENFORCEMENT, 1),
        ("nowa_klasa", 1),
        (SHARE, 1),
    ]
    assert shown["units"] == []
    assert shown["neighbourhood_trend"] == dict(total=0, returned=0, truncated=False, quarters=[])
    assert shown["hint"] == NO_TREND_QUARTERS
