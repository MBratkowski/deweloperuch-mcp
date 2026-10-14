"""Tests of ``deweloperuch_mcp.usecases.search_offers``."""

import re
from typing import Any

import pytest

from deweloperuch_mcp.models.errors import (
    InvalidInputError,
    NotFoundError,
    ServiceBlockedError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.models.offer import InvestmentRef, ListedOffer, OfferSearchPage
from deweloperuch_mcp.models.values import (
    DistrictName,
    OfferSort,
    OfferStatus,
    PricePerM2Pln,
)
from deweloperuch_mcp.usecases.search_offers import (
    SearchOffers,
    SearchOffersRequest,
    SearchOffersResult,
)
from support.fakes.catalogs import DEVELOPER, EchoPageLinks, FakeCatalogs, offer


def listed(offer_id: int) -> ListedOffer:
    ref = InvestmentRef(
        investment_slug=f"inv-{offer_id}", name="I", city=None, city_slug=None, developer=DEVELOPER
    )
    return ListedOffer(offer=offer(offer_id), investment=ref)


def search_page(total: int, page: int = 1, per_page: int = 10, items: int = 3) -> OfferSearchPage:
    listed_offers = tuple(listed(index) for index in range(items))
    return OfferSearchPage(items=listed_offers, total=total, page=page, per_page=per_page)


def test_a_search_gets_its_links() -> None:
    page = OfferSearchPage(items=(listed(1), listed(2)), total=2, page=1, per_page=10)
    fake = FakeCatalogs(page=page)

    found = SearchOffers(fake, EchoPageLinks()).execute(
        SearchOffersRequest.parse(city="krakow", page=3)
    )

    assert fake.calls == ["search"]
    assert found.page is page
    assert found.list_url == "list:krakow:3"
    assert found.investment_urls == ("investment:inv-1", "investment:inv-2")


@pytest.mark.parametrize(
    ("page", "hint"),
    [
        (
            search_page(13324),
            "Pasujących ofert jest 13324, a serwis pozwala przejrzeć najwyżej 20 stron po 10 "
            "(200). Zawęź filtry (cena, metraż) albo zwiększ per_page do 100.",
        ),
        (
            search_page(13324, per_page=100),
            "Pasujących ofert jest 13324, a serwis pozwala przejrzeć najwyżej 20 stron po 100 "
            "(2000). Zawęź filtry (cena, metraż).",
        ),
        (
            search_page(0, items=0),
            "Brak ofert spełniających kryteria. Sprawdź slug miasta (search_locations) i "
            "poluzuj filtry.",
        ),
        (search_page(30, page=9, items=0), "Strona 9 jest pusta; dostępne strony: 1–3."),
        (search_page(2000, per_page=100), None),
        (search_page(3), None),
    ],
)
def test_a_search_says_what_to_do_next(page: OfferSearchPage, hint: str | None) -> None:
    """The domain knows the cut (D4); the use case says it with the operations' names."""
    assert (
        SearchOffersResult(
            criteria=SearchOffersRequest.parse(city="x").criteria,
            page=page,
            list_url=None,
            investment_urls=(),
        ).hint
        == hint
    )
    assert (
        SearchOffers(FakeCatalogs(page=page), EchoPageLinks())
        .execute(SearchOffersRequest.parse(city="x"))
        .hint
        == hint
    )


def test_an_unknown_city_points_to_search_locations() -> None:
    fake = FakeCatalogs(
        errors={"search": NotFoundError("Serwis nie zna żądanych danych.", detail="d")}
    )

    with pytest.raises(NotFoundError) as caught:
        SearchOffers(fake, EchoPageLinks()).execute(SearchOffersRequest.parse(city="atlantyda"))

    assert str(caught.value) == (
        "Serwis nie zna miasta 'atlantyda'. Podaj city_slug z search_locations albo polska "
        "(cały kraj)."
    )
    assert caught.value.detail == "d"


def test_unexpected_data_keeps_its_type_and_names_the_search() -> None:
    fake = FakeCatalogs(errors={"search": UnexpectedResponseError("Inny format.", detail="x")})

    with pytest.raises(UnexpectedResponseError, match="^Wyszukiwanie ofert w 'warszawa': Inny"):
        SearchOffers(fake, EchoPageLinks()).execute(SearchOffersRequest.parse(city="warszawa"))


@pytest.mark.parametrize(
    "error", [ServiceBlockedError("STOP: 403."), InvalidInputError("Błąd programu.")]
)
def test_stop_and_input_errors_pass_unchanged(error: Exception) -> None:
    fake = FakeCatalogs(errors={"search": error})

    with pytest.raises(type(error)) as caught:
        SearchOffers(fake, EchoPageLinks()).execute(SearchOffersRequest.parse(city="warszawa"))

    assert caught.value is error


def test_the_search_with_its_defaults() -> None:
    criteria = SearchOffersRequest.parse(city=" warszawa ").criteria

    assert (criteria.city.value, criteria.page.value, criteria.per_page.value) == (
        "warszawa",
        1,
        10,
    )
    assert (criteria.price, criteria.area, criteria.sort) == (None, None, None)
    assert (criteria.price_per_m2, criteria.district, criteria.price_dropped) == (
        None,
        None,
        False,
    )
    assert criteria.status is OfferStatus.ACTIVE


def test_the_new_filters_of_the_search() -> None:
    criteria = SearchOffersRequest.parse(
        city="warszawa",
        price_per_m2_min=10_000,
        district="  Mokotów ",
        price_dropped=True,
        status="all",
        sort="biggest_drop",
    ).criteria

    assert criteria.price_per_m2 is not None and criteria.price_per_m2.low == PricePerM2Pln(10_000)
    assert criteria.district == DistrictName("Mokotów")
    assert (criteria.price_dropped, criteria.status, criteria.sort) == (
        True,
        OfferStatus.ALL,
        OfferSort.BIGGEST_DROP,
    )


@pytest.mark.parametrize(
    ("given", "first"),
    [
        ({"city": "X", "price_min": -1, "sort": "x", "page": 0, "per_page": 7}, "city"),
        ({"price_min": -1, "area_min": -1, "sort": "x", "page": 0, "per_page": 7}, "price_min"),
        ({"price_max": 1, "price_min": 2, "area_min": -1}, "price_min (2)"),
        ({"area_max": -1, "sort": "x", "page": 0, "per_page": 7}, "area_max"),
        ({"price_per_m2_min": -1, "district": "", "status": "x"}, "price_per_m2_min"),
        ({"district": "", "price_dropped": "x", "status": "x"}, "district"),
        ({"price_dropped": "x", "status": "x", "sort": "x"}, "price_dropped"),
        ({"status": "x", "sort": "x"}, "status"),
        ({"sort": "x", "page": 0, "per_page": 7}, "sort"),
        ({"page": 0, "per_page": 7}, "page"),
        ({"per_page": 7}, "per_page"),
    ],
)
def test_the_search_is_checked_in_the_order_of_its_parameters(
    given: dict[str, Any], first: str
) -> None:
    """With several mistakes, the first one by the parameters' order is reported."""
    given = {"city": "warszawa", **given}
    city = given.pop("city")

    with pytest.raises(InvalidInputError, match=f"^{re.escape(first)}"):
        SearchOffersRequest.parse(city=city, **given)
