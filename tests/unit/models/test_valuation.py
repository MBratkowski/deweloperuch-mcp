"""Tests of ``deweloperuch_mcp.models.valuation``."""

import math

import pytest

from deweloperuch_mcp.models.errors import InvalidValueError, ValueName
from deweloperuch_mcp.models.valuation import (
    ADDRESS_MAX,
    AddressText,
    ComparablesLimit,
    Coordinates,
    Valuation,
    ValuedArea,
)
from support.builders.valuation import SUBJECT, comparable

VALUATION = Valuation(
    subject=SUBJECT,
    estimated_value=1.0,
    comparables=(
        comparable(300, "c"),
        comparable(None, "unknown"),
        comparable(100, "a"),
        comparable(200, "b1"),
        comparable(200, "b2"),
    ),
)


@pytest.mark.parametrize(
    ("lat", "lng", "refused"),
    [
        (48.99, 21.0, ValueName.LATITUDE),
        (54.91, 21.0, ValueName.LATITUDE),
        (52.0, 14.09, ValueName.LONGITUDE),
        (52.0, 24.21, ValueName.LONGITUDE),
        (math.nan, 21.0, ValueName.LATITUDE),
        (52.0, math.inf, ValueName.LONGITUDE),
        (True, 21.0, ValueName.LATITUDE),
        ("52.2", 21.0, ValueName.LATITUDE),
        (None, None, ValueName.LATITUDE),  # the latitude is checked first
    ],
)
def test_a_point_outside_poland_is_refused(lat: object, lng: object, refused: ValueName) -> None:
    with pytest.raises(InvalidValueError) as caught:
        Coordinates.parse(lat, lng)

    assert caught.value.value is refused


def test_the_corners_of_poland_are_points() -> None:
    assert Coordinates.parse(49.0, 14.1) == Coordinates(49.0, 14.1)
    assert Coordinates.parse(54.9, 24.2) == Coordinates(54.9, 24.2)


@pytest.mark.parametrize("area", [9.99, 500.01, 0, -50, math.nan, False, "50"])
def test_an_area_out_of_range_is_refused(area: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        ValuedArea.parse(area)

    assert caught.value.value is ValueName.VALUED_AREA


def test_an_area_is_kept_to_hundredths_of_a_m2() -> None:
    assert ValuedArea.parse(10).value == 10.0
    assert ValuedArea.parse(48.787).value == 48.79
    assert ValuedArea.parse(500).value == 500.0


@pytest.mark.parametrize(
    ("given", "expected"),
    [(None, None), ("", None), ("   ", None), (" Marszałkowska 100 ", "Marszałkowska 100")],
)
def test_an_address_is_optional(given: object, expected: str | None) -> None:
    found = AddressText.parse(given)

    assert (None if found is None else found.text) == expected


def test_an_address_is_measured_without_the_spaces_around_it() -> None:
    found = AddressText.parse("  " + "x" * ADDRESS_MAX + "  ")

    assert found is not None and found.text == "x" * ADDRESS_MAX


@pytest.mark.parametrize("given", ["ab", " ab ", "x" * (ADDRESS_MAX + 1), 42])
def test_an_address_too_short_too_long_or_not_text_is_refused(given: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        AddressText.parse(given)

    assert caught.value.value is ValueName.ADDRESS


def test_the_nearest_comparables_first_unknown_distances_last() -> None:
    listing = VALUATION.nearest()

    assert [c.address for c in listing.comparables] == ["a", "b1", "b2", "c", "unknown"]
    assert (listing.total, listing.returned, listing.omitted, listing.truncated) == (
        5,
        5,
        0,
        False,
    )


@pytest.mark.parametrize(("limit", "shown"), [(0, []), (2, ["a", "b1"]), (5, None), (9, None)])
def test_a_limit_keeps_the_nearest_and_counts_the_rest(limit: int, shown: list[str] | None) -> None:
    listing = VALUATION.nearest(ComparablesLimit(limit))
    expected = ["a", "b1", "b2", "c", "unknown"] if shown is None else shown

    assert [c.address for c in listing.comparables] == expected
    assert listing.omitted == 5 - len(expected)
    assert listing.truncated is (len(expected) < 5)


@pytest.mark.parametrize("limit", [-1, True, 1.5, "3"])
def test_a_wrong_limit_is_refused(limit: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        ComparablesLimit.parse(limit)

    assert caught.value.value is ValueName.COMPARABLES_LIMIT
