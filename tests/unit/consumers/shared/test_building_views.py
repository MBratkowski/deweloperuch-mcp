"""Tests of ``deweloperuch_mcp.consumers.shared.building_views``."""

from deweloperuch_mcp.consumers.shared.building_views import BuildingView
from deweloperuch_mcp.models.building import ENFORCEMENT, REGULAR, SHARE, UnitsLimit
from deweloperuch_mcp.usecases.get_building import NO_TREND_QUARTERS, GetBuildingResult
from support.fakes.buildings import building_of, trend_of, unit_sold_as


def test_the_view_counts_the_other_transactions_of_the_whole_building() -> None:
    building = building_of(unit_sold_as(1, REGULAR, SHARE), unit_sold_as(2, ENFORCEMENT))

    view = BuildingView.from_result(
        GetBuildingResult(listing=building.listing(UnitsLimit(0)), trend=None, building_url=None)
    )

    assert view.non_regular_transactions == {ENFORCEMENT: 1, SHARE: 1}
    assert (view.units, view.units_omitted, view.transactions_total) == ([], 2, 3)
    assert view.hint is None


def test_the_view_of_regular_sales_and_a_trend_without_quarters() -> None:
    view = BuildingView.from_result(
        GetBuildingResult(
            listing=building_of(unit_sold_as(1, REGULAR)).listing(),
            trend=trend_of(),
            building_url=None,
        )
    )

    assert view.non_regular_transactions == {}
    assert view.hint == NO_TREND_QUARTERS
    trend = view.neighbourhood_trend
    assert trend is not None
    assert (trend.quarters_total, trend.quarters_omitted, trend.quarters) == (0, 0, [])
