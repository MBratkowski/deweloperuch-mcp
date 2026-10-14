"""Tests of ``deweloperuch_mcp.models.building``."""

import re
from typing import Any

import pytest

from deweloperuch_mcp.models.building import (
    BuildingRef,
    BuildingSlug,
    UnitsLimit,
)
from deweloperuch_mcp.models.errors import InvalidValueError, SlugText, ValueName, WholeNumber
from support.checks import layering
from support.fakes.buildings import MID, NEW, OLD, building_of, trend_of, unit_sold
from support.providers.routes.buildings import SLUG

BUILDING_WORDS = re.compile(r"get_building|building_slug|include_trend|\blimit\b")


def test_the_listing_shows_the_newest_transactions_first() -> None:
    building = building_of(
        unit_sold(1, OLD),
        unit_sold(2),
        unit_sold(3, OLD, NEW),
        unit_sold(4, MID),
        unit_sold(5, NEW),
        unit_sold(6, None),
    )

    listing = building.listing()

    # Equal last days keep the service's order (3 before 5); units never dated go last.
    assert [unit.unit_id for unit in listing.units] == [3, 5, 4, 1, 2, 6]
    assert listing.omitted == 0
    assert listing.building is building


@pytest.mark.parametrize(
    ("limit", "kept", "omitted"), [(0, [], 3), (2, [3, 2], 1), (5, [3, 2, 1], 0)]
)
def test_the_listing_keeps_at_most_the_limit(limit: int, kept: list[int], omitted: int) -> None:
    building = building_of(unit_sold(1, OLD), unit_sold(2, MID), unit_sold(3, NEW))

    listing = building.listing(UnitsLimit(limit))

    assert ([unit.unit_id for unit in listing.units], listing.omitted) == (kept, omitted)


def test_the_counts_and_dates_of_the_whole_building() -> None:
    building = building_of(unit_sold(1, MID, NEW), unit_sold(2, None, OLD), unit_sold(3))

    assert building.transactions_count == 4
    assert (building.first_sold_on, building.last_sold_on) == (OLD, NEW)
    assert building.ref == BuildingRef(building_slug="ulica-1-miasto", city_slug="miasto")
    assert building_of().first_sold_on is None
    assert building_of(unit_sold(1)).last_sold_on is None


def test_a_unit_keeps_its_transactions_in_order() -> None:
    with pytest.raises(ValueError, match="kolejności dat"):
        unit_sold(1, NEW, OLD)


def test_the_newest_quarters_of_the_trend() -> None:
    trend = trend_of("2024-Q3", "2024-Q4", "2025-Q1", "2025-Q2")

    latest = trend.latest(2)

    assert [q.period for q in latest.quarters] == ["2025-Q1", "2025-Q2"]
    assert (latest.total, latest.omitted, latest.radius_km) == (4, 2, 1.0)
    assert latest.latest(1).total == 4
    assert trend.latest(None) is trend
    assert trend.latest(4) is trend
    assert (trend.latest(0).quarters, trend.latest(0).omitted) == ((), 4)
    with pytest.raises(ValueError):
        trend.latest(-1)


def test_the_quarters_of_a_trend_are_in_order() -> None:
    with pytest.raises(ValueError, match="kolejności"):
        trend_of("2025-Q2", "2025-Q1")


@pytest.mark.parametrize(
    ("make", "value", "rule", "given"),
    [
        (lambda: BuildingSlug.parse(" 23-Marca-79C-Sopot "), ValueName.BUILDING, SlugText(), None),
        (lambda: BuildingSlug.parse("a/../b"), ValueName.BUILDING, SlugText(), "a/../b"),
        (lambda: BuildingSlug(""), ValueName.BUILDING, SlugText(), ""),
        (lambda: UnitsLimit.parse(-1), ValueName.UNITS_LIMIT, WholeNumber(0, 100_000), -1),
        (lambda: UnitsLimit.parse(True), ValueName.UNITS_LIMIT, WholeNumber(0, 100_000), True),
    ],
)
def test_the_values_of_a_building_refuse_what_they_cannot_be(
    make: Any, value: ValueName, rule: object, given: object
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        make()

    assert (caught.value.value, caught.value.rule) == (value, rule)
    if given is not None:
        assert caught.value.given == given


def test_the_values_of_a_building_take_what_they_can_be() -> None:
    assert BuildingSlug.parse(" 23-marca-79c-sopot ") == BuildingSlug(SLUG)
    assert UnitsLimit.parse(None) is None
    assert UnitsLimit.parse(0) == UnitsLimit(0)


def test_the_domain_of_buildings_names_no_tool_nor_parameter() -> None:
    """D13: the domain says what is wrong in its own words; the application names the
    parameters (tests/architecture/test_layering.py checks the tools and parameters it knows)."""
    texts = layering.message_texts(layering.source_of("deweloperuch_mcp.models.building"))

    assert texts
    assert [
        t for t in texts if BUILDING_WORDS.search(t) or layering.INTERFACE_WORDS.search(t)
    ] == []
