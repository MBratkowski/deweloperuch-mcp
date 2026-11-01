"""Tests of ``deweloperuch_mcp.api.dto.offer_snapshot_dto``: how it reads the shape of a
snapshot, on the real body of Sopot (tests/fixtures/api/) with one thing changed."""

import datetime as dt
from typing import Any

import pytest

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.offer_snapshot_dto import OfferSnapshotDto
from deweloperuch_mcp.errors import UnexpectedResponseError
from deweloperuch_mcp.models.market_statistics import CityOffers, MarketCriteria
from deweloperuch_mcp.models.values import CitySlug
from support.providers.routes.offer_snapshot import snapshot

SOPOT = CitySlug("sopot")


def offers(data: Any) -> CityOffers:
    return Dto.validated(OfferSnapshotDto, data, "offer-snapshot").to_model(SOPOT)


@pytest.mark.parametrize("value", [1, -7, "x", None, [0]])
def test_the_third_item_of_a_sale_is_never_read(value: object) -> None:
    """T76: position 2 is 0 in every row seen and its meaning is unknown."""
    data = snapshot("sopot")
    for row in data["sales"]:
        row[2] = value

    assert offers(data) == offers(snapshot("sopot"))


@pytest.mark.parametrize(
    "change",
    [
        lambda row: row.pop(2),  # 6 items: every later position moves
        lambda row: row.append(0),  # 8 items
        lambda row: row.clear(),
    ],
)
def test_a_sale_of_another_length_is_a_changed_service(change: Any) -> None:
    """Positions cannot be read from a row of another length (D21: the service changed)."""
    data = snapshot("sopot")
    change(data["sales"][1])

    with pytest.raises(UnexpectedResponseError) as caught:
        offers(data)

    assert caught.value.detail is not None and "sales.1" in caught.value.detail


def test_a_sale_with_keys_is_a_changed_service_even_with_seven_of_them() -> None:
    """Only an array is read by position: an object of 7 keys is a changed shape too."""
    data = snapshot("sopot")
    keys = ("id", "investId", "flag", "amount", "pricePerM2", "size", "startDifference")
    data["sales"][0] = dict(zip(keys, data["sales"][0], strict=True))

    with pytest.raises(UnexpectedResponseError) as caught:
        offers(data)

    assert caught.value.detail is not None and "sales.0" in caught.value.detail


def test_a_sale_without_an_investment_counts_for_no_developer() -> None:
    """A null ``invest_id``: one such offer is no reason to refuse a city; it counts, but
    no investment or developer is credited with it."""
    data = snapshot("sopot")
    data["sales"][0][1] = None

    found = offers(data)
    summary = found.statistics(MarketCriteria(city=SOPOT))

    first = found.offers[0]
    assert (first.investment_slug, first.developer_slug, first.developer_name) == (None,) * 3
    assert (summary.offers, summary.investments) == (8, 2)
    assert [share.offers for share in summary.top_developers] == [7]


@pytest.mark.parametrize(
    ("position", "largest_price", "largest_area"), [(3, 1679796.0, 95.49), (5, 3735107.0, 66.36)]
)
def test_a_sale_without_a_price_or_an_area_counts_outside_that_spread(
    position: int, largest_price: float, largest_area: float
) -> None:
    """A null price (area), like ``""`` and 0: the offer counts and stays out of the spread
    of prices (areas) and of prices per m²; the first offer has the largest of both."""
    data = snapshot("sopot")
    data["sales"][0][position] = None

    found = offers(data)
    summary = found.statistics(MarketCriteria(city=SOPOT))

    assert found.offers[0].price_per_m2 is None
    assert summary.offers == 8
    assert summary.price_spread is not None and summary.price_spread.max == largest_price
    assert summary.area_spread is not None and summary.area_spread.max == largest_area
    assert summary.price_per_m2_spread is not None
    assert summary.price_per_m2_spread.max < 39115.16  # the first offer's, left out


@pytest.mark.parametrize("value", ["31.10.2026", "2026-13-01", 20261031, None, ["2026-10-31"]])
def test_a_day_that_cannot_be_read_is_no_day(value: object) -> None:
    """``asOf`` is shown, not counted: one that cannot be read leaves the day out."""
    data = snapshot("sopot")
    data["asOf"] = value

    found = offers(data)

    assert found.as_of is None and len(found.offers) == 8


def test_without_a_day_the_offers_are_of_no_day() -> None:
    data = snapshot("sopot")
    del data["asOf"]

    found = offers(data)

    assert found.as_of is None and len(found.offers) == 8


def test_a_day_with_a_time_is_its_day() -> None:
    data = snapshot("sopot")
    data["asOf"] = "2026-10-31T00:00:00.000Z"

    assert offers(data).as_of == dt.date(2026, 10, 31)


def test_the_slugs_and_the_name_of_an_investment_are_trimmed_and_blank_is_none() -> None:
    data = snapshot("sopot")
    smolna, kolibki = data["investments"]
    smolna.update(slug=" smolna ", developerSlug=" invest-komfort-spolka-akcyjna ")
    smolna["developer"] = " Invest Komfort Spółka Akcyjna Sp.K. "
    kolibki.update(slug="", developerSlug="  ", developer="")

    found = {offer.offer_id: offer for offer in offers(data).offers}

    assert (found[206523].investment_slug, found[206523].developer_slug) == (
        "smolna",
        "invest-komfort-spolka-akcyjna",
    )
    assert found[206523].developer_name == "Invest Komfort Spółka Akcyjna Sp.K."
    assert (found[69910].investment_slug, found[69910].developer_slug) == (None, None)
    assert found[69910].developer_name is None


def test_an_offer_of_an_investment_off_the_list_has_no_slugs() -> None:
    """[P 2026-10-31] every sale's investment is listed; one that is not still counts."""
    data = snapshot("sopot")
    data["investments"] = [item for item in data["investments"] if item["id"] != 1276]

    found = offers(data).offers

    assert len(found) == 8
    assert {(o.investment_slug, o.developer_slug) for o in found if o.offer_id == 69910} == {
        (None, None)
    }


def test_a_price_or_an_area_of_zero_is_no_value() -> None:
    """``Dto._positive``: no flat costs 0 or measures 0 m²; never seen in a snapshot."""
    data = snapshot("sopot")
    data["sales"][0][3] = 0
    data["sales"][1][5] = 0

    first, second = offers(data).offers[:2]

    assert (first.price, first.area_m2) == (None, 95.49)
    assert (second.price, second.area_m2) == (1399534.0, None)


def test_a_snapshot_without_its_city_is_a_changed_service() -> None:
    """[P 2026-10-31] ``citySlug`` echoes the city asked for; the adapter compares them."""
    data = snapshot("sopot")
    del data["citySlug"]

    with pytest.raises(UnexpectedResponseError):
        offers(data)
