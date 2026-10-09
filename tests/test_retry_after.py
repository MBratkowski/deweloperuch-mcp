"""Parsing of the HTTP ``Retry-After`` header (delay-seconds or an HTTP date)."""

import math
from email.utils import formatdate

import pytest

from deweloperuch_mcp.retry_after import parse_retry_after

NOW = 1_800_000_000.0  # fixed wall clock (2027-01-15)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("120", 120.0),
        ("0", 0.0),
        (" 7 ", 7.0),
        # Not delay-seconds per RFC 9110 (1*DIGIT), but honouring it errs on the polite side.
        ("1.5", 1.5),
    ],
)
def test_seconds(value: str, expected: float) -> None:
    assert parse_retry_after(value, NOW) == expected


def test_seconds_beyond_float_range_are_infinite() -> None:
    """A valid but absurd delay must not read as "no delay": the limiter caps it."""
    assert parse_retry_after("9" * 400, NOW) == math.inf


def test_http_date_in_the_future() -> None:
    value = formatdate(NOW + 90, usegmt=True)  # "Fri, 15 Jan 2027 08:01:30 GMT"

    assert parse_retry_after(value, NOW) == 90.0


@pytest.mark.parametrize(
    "value",
    [
        "Sunday, 06-Nov-94 08:49:37 GMT",  # obsolete RFC 850 form
        "Sun Nov  6 08:49:37 1994",  # asctime form, no zone: HTTP dates are UTC
        "Sun, 06 Nov 1994 08:49:37 -0000",  # naive after parsing, taken as UTC
    ],
)
def test_obsolete_date_forms_are_utc(value: str) -> None:
    now = 784_111_777.0  # Sun, 06 Nov 1994 08:49:37 GMT

    assert parse_retry_after(value, now - 30) == 30.0


def test_date_with_offset() -> None:
    now = 784_111_777.0  # 08:49:37 GMT == 10:49:37 +0200

    assert parse_retry_after("Sun, 06 Nov 1994 10:50:37 +0200", now) == 60.0


def test_date_in_the_past_means_retry_now() -> None:
    assert parse_retry_after(formatdate(NOW - 3600, usegmt=True), NOW) == 0.0


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "-5",
        "-0",
        "+5",
        "abc",
        "1e3",
        "inf",
        "nan",
        "0x10",
        "5 s",
        "١٢٠",  # Arabic-Indic digits: not ASCII DIGIT
        "Wed, 99 Foo 2015 07:28:00 GMT",
        "Sun, 06 Nov 99999 08:49:37 GMT",
    ],
)
def test_unusable_values_give_none(value: str | None) -> None:
    assert parse_retry_after(value, NOW) is None
