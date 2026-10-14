"""Tests of ``deweloperuch_mcp.models.offer``."""

import dataclasses
import datetime as dt

import pytest

from deweloperuch_mcp.models.offer import (
    DeveloperRef,
    InvestmentRef,
    ListedOffer,
    OfferSearchPage,
)
from deweloperuch_mcp.models.price_history import PriceEvent
from support.builders.investments import offer, smolna


def search_page(total: int, page: int = 1, per_page: int = 10, items: int = 3) -> OfferSearchPage:
    ref = InvestmentRef(
        investment_slug="x",
        name="X",
        city=None,
        city_slug=None,
        developer=DeveloperRef(developer_slug="d", name="D"),
    )
    listed = tuple(ListedOffer(offer=offer(index), investment=ref) for index in range(items))
    return OfferSearchPage(items=listed, total=total, page=page, per_page=per_page)


def test_price_per_m2_is_derived_and_rounded() -> None:
    assert dataclasses.replace(offer(1), price=994012.0, area_m2=55.25).price_per_m2 == 17991.17
    assert dataclasses.replace(offer(1), area_m2=0.0).price_per_m2 is None
    assert dataclasses.replace(offer(1), price=None).price_per_m2 is None


def test_events_are_attached_to_the_history_oldest_first() -> None:
    events = [
        PriceEvent(date=dt.date(2025, 2, 25), kind="offer", price=1.0),
        PriceEvent(date=dt.date(2026, 10, 3), kind="restored", price=2.0),
    ]

    with_events = offer(1).with_price_events(events)

    assert offer(1).history.events is None
    assert with_events.history.events == tuple(events)
    with pytest.raises(ValueError, match="kolejności dat"):
        offer(1).with_price_events(reversed(events))


def test_active_offers_come_first_then_the_rest_in_service_order() -> None:
    investment = smolna()
    mixed = dataclasses.replace(
        investment,
        offers=(offer(2377, "archived"), offer(206087), offer(2386, "archived"), offer(1)),
    )

    listing = mixed.listing()

    assert [(o.offer_id, o.status) for o in listing.offers] == [
        (206087, "active"),
        (1, "active"),
        (2377, "archived"),
        (2386, "archived"),
    ]
    assert listing.omitted == 0


@pytest.mark.parametrize(
    ("total", "per_page", "pages", "truncated"),
    [
        (13324, 100, 20, True),
        (1192, 50, 20, True),
        (2000, 100, 20, False),
        (2001, 100, 20, True),
        (120, 10, 12, False),
        (3, 10, 1, False),
    ],
)
def test_a_search_says_how_much_can_be_browsed(
    total: int, per_page: int, pages: int, truncated: bool
) -> None:
    result = search_page(total, per_page=per_page)

    assert (result.total, result.returned, result.per_page) == (total, 3, per_page)
    assert (result.pages_available, result.truncated) == (pages, truncated)
    assert result.browsable == 20 * per_page


def test_a_search_without_offers_has_no_pages() -> None:
    result = search_page(0, items=0)

    assert (result.total, result.returned, result.pages_available) == (0, 0, 0)
    assert not result.truncated


def test_an_empty_page_past_the_last_one_knows_the_pages_that_exist() -> None:
    result = search_page(30, page=9, items=0)

    assert (result.returned, result.pages_available, result.browsable) == (0, 3, 200)


def test_no_pages_without_a_page_size() -> None:
    assert search_page(30, per_page=0).pages_available == 0
