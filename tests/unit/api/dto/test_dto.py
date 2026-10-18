"""Tests of ``deweloperuch_mcp.api.dto.dto``."""

import datetime as dt

import pytest

from deweloperuch_mcp.api.dto.dto import Dto


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("994012", 994012.0),
        (994012, 994012.0),
        ("55.25", 55.25),
        (" -0.6 ", -0.6),
        ("-10795", -10795.0),
        ("", None),
        ("  ", None),
        (None, None),
    ],
)
def test_number(value: int | float | str | None, expected: float | None) -> None:
    assert Dto._number(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, None), ("0", None), (-1, None), ("", None), (None, None), (5, 5.0), ("5.5", 5.5)],
)
def test_positive_treats_zero_and_less_as_no_value(
    value: int | float | str | None, expected: float | None
) -> None:
    assert Dto._positive(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-03", dt.date(2026, 10, 3)),
        ("2025-02-25T00:00:00.000Z", dt.date(2025, 2, 25)),
        # A zone other than UTC: the date of the same moment in UTC.
        ("2025-02-25T01:00:00+02:00", dt.date(2025, 2, 24)),
        ("2025-02-25T12:30:00", dt.date(2025, 2, 25)),
        ("", None),
        (None, None),
    ],
)
def test_day(value: str | None, expected: dt.date | None) -> None:
    assert Dto._day(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [("", None), ("   ", None), (None, None), (" Sopot ", "Sopot")]
)
def test_text(value: str | None, expected: str | None) -> None:
    assert Dto._text(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(9, 9), ("9", 9), (9.0, 9), (1.5, 2), ("0.4", 0), ("", None), (None, None)],
)
def test_rounded(value: int | float | str | None, expected: int | None) -> None:
    """A figure the service may give with a fraction (a count of transactions, months):
    the nearest whole number."""
    assert Dto._rounded(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, 1), ("1", 1), (1.0, 1), (-1, -1), (1.5, None), ("2.5", None), ("", None), (None, None)],
)
def test_exact_whole(value: int | float | str | None, expected: int | None) -> None:
    """A whole number as sent (a floor, rooms, a count); a fraction is no such number."""
    assert Dto._exact_whole(value) == expected
