"""Tests of ``deweloperuch_mcp.api.queries.offers_query``."""

from typing import Any

import pytest

from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.queries import offers_query
from deweloperuch_mcp.api.queries.offers_query import SORT_PARAMS, OffersQuery
from deweloperuch_mcp.models.values import AmountPln, AreaM2, OfferSort, PricePerM2Pln
from deweloperuch_mcp.usecases.search_offers import SearchOffersRequest
from support.builders.offers import OFFERS_QUERY_CASES


def query_of(params: list[tuple[str, str | int]]) -> str:
    return HttpClient.target("", params).removeprefix("?")


@pytest.mark.parametrize(("given", "query"), OFFERS_QUERY_CASES)
def test_the_query_of_the_criteria(given: dict[str, Any], query: str) -> None:
    assert (
        query_of(OffersQuery(SearchOffersRequest.parse(city="krakow", **given).criteria).params())
        == query
    )


def test_open_ends_are_the_ui_sentinels() -> None:
    """[P z kodu] pages-rsc.md: the UI's own ends of an open range; this mapping owns them
    (the domain's open end is ``None``). They equal the largest values the domain accepts,
    so every closed range the domain lets through is also within them."""
    assert (offers_query.OPEN_LOW, offers_query.PRICE_SENTINEL, offers_query.AREA_SENTINEL) == (
        0,
        99_999_999,
        9_999,
    )
    assert (offers_query.PRICE_SENTINEL, offers_query.AREA_SENTINEL) == (AmountPln.MAX, AreaM2.MAX)
    # [P z kodu] the price-per-m² one; what the server does with it is [W] (live suite).
    assert offers_query.PRICE_PER_M2_SENTINEL == PricePerM2Pln.MAX == 999_999


def test_every_order_has_its_sort_parameters() -> None:
    """[P 2026-10-10] pages-rsc.md: ``amount`` both ways; ``price_per_sqm``, ``size`` and
    ``start_amount_difference_percent`` ascending. Descending by price per m² and area is
    [W] (commented in ``params``; the live suite checks the order)."""
    assert dict(SORT_PARAMS) == {
        OfferSort.PRICE_ASC: ("amount", "asc"),
        OfferSort.PRICE_DESC: ("amount", "desc"),
        OfferSort.PRICE_PER_M2_ASC: ("price_per_sqm", "asc"),
        OfferSort.PRICE_PER_M2_DESC: ("price_per_sqm", "desc"),
        OfferSort.AREA_ASC: ("size", "asc"),
        OfferSort.AREA_DESC: ("size", "desc"),
        OfferSort.BIGGEST_DROP: ("start_amount_difference_percent", "asc"),
    }
