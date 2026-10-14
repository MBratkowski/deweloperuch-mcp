"""Tests of ``deweloperuch_mcp.api.queries.valuation_query``."""

import pytest

from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.queries.valuation_query import ValuationQuery
from deweloperuch_mcp.models.valuation import ValuationSubject
from support.builders.valuation import SUBJECT
from support.providers.samples import request_target


def test_the_request_is_the_one_of_the_sample() -> None:
    query = ValuationQuery(SUBJECT)
    target = HttpClient.target(query.path(), query.params())

    assert target == request_target("api.standalone_val")


@pytest.mark.parametrize(
    ("lat", "lng", "area", "expected"),
    [
        (52.2297, 21.0122, 50, [("area", "50"), ("lat", "52.2297"), ("lng", "21.0122")]),
        (52, 21, 48.5, [("area", "48.5"), ("lat", "52"), ("lng", "21")]),
        (
            52.123456789,
            21.000000049,
            48.787,
            [("area", "48.79"), ("lat", "52.123457"), ("lng", "21")],
        ),
    ],
)
def test_numbers_without_trailing_zeros_and_without_an_address(
    lat: float, lng: float, area: float, expected: list[tuple[str, str]]
) -> None:
    assert ValuationQuery(ValuationSubject.parse(lat, lng, area)).params() == expected
