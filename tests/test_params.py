"""Offer search criteria -> the service's parameters (infrastructure ``params``), pinned.

The exact query of each kind of criteria, the exact URL the catalog adapter requests
(with its ``_rsc`` token), and the link to the same list: one mapping for both, in the
UI's order. Open ranges reach the UI's sentinels ([P z kodu], pages-rsc.md).
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import respx

from deweloperuch_mcp import identity
from deweloperuch_mcp.application import arguments
from deweloperuch_mcp.domain.values import AmountPln, AreaM2
from deweloperuch_mcp.flight import rsc_token
from deweloperuch_mcp.infrastructure.deweloperuch import params
from deweloperuch_mcp.infrastructure.deweloperuch.links import ServicePageLinks
from deweloperuch_mcp.infrastructure.deweloperuch.offers import ServiceOfferCatalog
from deweloperuch_mcp.infrastructure.deweloperuch.params import SORT_PARAMS, offers_list_query
from deweloperuch_mcp.infrastructure.deweloperuch.transport import HttpClient
from deweloperuch_mcp.throttle import RequestLimiter
from rsc_fixtures import offers_payload

BASE = identity.BASE_URL

CASES: list[tuple[dict[str, Any], str]] = [
    ({}, "page=1&perPage=10"),
    ({"price_max": 500_000}, "filterPrice=0-500000&page=1&perPage=10"),
    ({"price_min": 500_000}, "filterPrice=500000-99999999&page=1&perPage=10"),
    ({"price_min": 0, "price_max": 0}, "filterPrice=0-0&page=1&perPage=10"),
    ({"area_min": 40}, "filterSize=40-9999&page=1&perPage=10"),
    ({"area_max": 60}, "filterSize=0-60&page=1&perPage=10"),
    (
        {"price_max": 900_000, "area_min": 35},
        "filterPrice=0-900000&filterSize=35-9999&page=1&perPage=10",
    ),
    ({"sort": "price_asc"}, "sortBy=amount&sortOrder=asc&page=1&perPage=10"),
    ({"sort": "price_desc"}, "sortBy=amount&sortOrder=desc&page=1&perPage=10"),
    ({"page": 20, "per_page": 100}, "page=20&perPage=100"),
    (
        {
            "price_min": 500_000,
            "price_max": 700_000,
            "area_min": 40,
            "area_max": 60,
            "sort": "price_asc",
            "page": 2,
            "per_page": 50,
        },
        "filterPrice=500000-700000&filterSize=40-60&sortBy=amount&sortOrder=asc&page=2&perPage=50",
    ),
]


def query_of(params: list[tuple[str, str | int]]) -> str:
    return "&".join(f"{name}={value}" for name, value in params)


@pytest.mark.parametrize(("given", "query"), CASES)
def test_the_query_of_the_criteria(given: dict[str, Any], query: str) -> None:
    assert query_of(offers_list_query(arguments.offer_search("krakow", **given))) == query


def test_open_ends_are_the_ui_sentinels() -> None:
    """[P z kodu] pages-rsc.md: the UI's own ends of an open range; this mapping owns them
    (the domain's open end is ``None``). They equal the largest values the domain accepts,
    so every closed range the domain lets through is also within them."""
    assert (params.OPEN_LOW, params.PRICE_SENTINEL, params.AREA_SENTINEL) == (0, 99_999_999, 9_999)
    assert (params.PRICE_SENTINEL, params.AREA_SENTINEL) == (AmountPln.MAX, AreaM2.MAX)


def test_only_amount_is_sorted_by() -> None:
    """[P] only ``sortBy=amount``; the other ``sortBy`` values are [W z kodu]."""
    assert {sort_by for sort_by, _ in SORT_PARAMS.values()} == {"amount"}


@pytest.fixture
def http(tmp_path: Path) -> Iterator[HttpClient]:
    limiter = RequestLimiter(tmp_path, min_interval=0, testing_only_allow_fast_interval=True)
    with HttpClient(limiter=limiter) as client:
        yield client


@pytest.mark.parametrize(("given", "query"), CASES)
def test_the_catalog_requests_exactly_that_and_the_link_is_the_same_list(
    http: HttpClient, given: dict[str, Any], query: str
) -> None:
    criteria = arguments.offer_search("krakow", **given)
    with respx.mock(assert_all_mocked=True) as router:
        route = router.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
            200, content=offers_payload(), headers={"Content-Type": "text/x-component"}
        )

        ServiceOfferCatalog(http).search(criteria)

    target = f"/ceny-ofertowe/krakow/mieszkania?{query}"
    assert str(route.calls.last.request.url) == f"{BASE}{target}&_rsc={rsc_token(target)}"
    assert route.calls.last.request.headers["rsc"] == "1"
    assert ServicePageLinks().offers_list(criteria) == BASE + target


def test_the_whole_country_is_its_own_page() -> None:
    criteria = arguments.offer_search("polska", page=3, per_page=50)

    assert ServicePageLinks().offers_list(criteria) == (
        BASE + "/ceny-ofertowe/polska/mieszkania?page=3&perPage=50"
    )
