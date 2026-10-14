"""Tests of ``deweloperuch_mcp.models.investment``."""

import dataclasses
import datetime as dt

import pytest

from deweloperuch_mcp.models.investment import OfferDetail
from deweloperuch_mcp.models.price_history import PriceEvent
from deweloperuch_mcp.models.values import (
    OffersLimit,
)
from support.builders.investments import offer, smolna


@pytest.mark.parametrize(("limit", "returned", "omitted"), [(None, 3, 0), (2, 2, 1), (0, 0, 3)])
def test_a_limit_says_what_was_omitted(limit: int | None, returned: int, omitted: int) -> None:
    listing = smolna().listing(OffersLimit.parse(limit))

    assert (len(listing.offers), listing.omitted) == (returned, omitted)


def test_histories_are_attached_to_the_offers_kept() -> None:
    events = {206087: (PriceEvent(date=dt.date(2026, 10, 3), kind="offer", price=1679796.0),)}

    listing = smolna().listing(OffersLimit(2)).with_price_events(events)

    first, second = listing.offers
    assert first.history.events == events[206087]
    assert second.history.events == ()  # no entry: no events, not "unknown"


def test_averages_are_those_of_the_active_offers() -> None:
    """In the sample avg_* equal the mean of the active offers (3 of 16, all in the sample)."""
    investment = smolna()
    active = [o for o in investment.offers if o.active]

    assert len(active) == investment.offers_active == 3
    assert investment.avg_price == pytest.approx(sum(o.price or 0 for o in active) / 3)
    assert investment.avg_area_m2 == pytest.approx(
        sum(o.area_m2 or 0 for o in active) / 3, abs=0.01
    )
    assert investment.avg_price_per_m2 == 24487.63


def test_an_offer_detail_belongs_to_its_investment() -> None:
    investment = smolna()

    OfferDetail(offer=offer(2377), investment=investment)
    with pytest.raises(ValueError, match="nie należy"):
        OfferDetail(offer=offer(999), investment=investment)


def test_domain_objects_are_immutable() -> None:
    investment = smolna()

    with pytest.raises(dataclasses.FrozenInstanceError):
        investment.name = "x"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        investment.offers[0].history.events = ()  # type: ignore[misc]
