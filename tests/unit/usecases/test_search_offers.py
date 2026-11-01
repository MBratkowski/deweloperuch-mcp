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
            "(200). Zawęź filtry (dzielnica, cena, metraż) albo zwiększ per_page do 100.",
        ),
        (
            search_page(13324, per_page=100),
            "Pasujących ofert jest 13324, a serwis pozwala przejrzeć najwyżej 20 stron po 100 "
            "(2000). Zawęź filtry (dzielnica, cena, metraż).",
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


def test_a_cut_list_of_a_district_is_narrowed_by_price_and_area() -> None:
    """A search already in a district has no district left to narrow by."""
    result = SearchOffersResult(
        criteria=SearchOffersRequest.parse(city="warszawa", district="Mokotów").criteria,
        page=search_page(959),
        list_url=None,
        investment_urls=(),
    )

    assert result.hint == (
        "Pasujących ofert jest 959, a serwis pozwala przejrzeć najwyżej 20 stron po 10 (200). "
        "Zawęź filtry (cena, metraż) albo zwiększ per_page do 100."
    )
    assert result.narrowing == "cena, metraż"


def test_an_unknown_city_points_to_search_locations() -> None:
    fake = FakeCatalogs(
        errors={"search": NotFoundError("Serwis nie zna żądanych danych.", detail="d")}
    )

    with pytest.raises(NotFoundError) as caught:
        SearchOffers(fake, EchoPageLinks()).execute(SearchOffersRequest.parse(city="atlantyda"))

    assert str(caught.value) == (
        "Serwis nie zna miasta 'atlantyda'. Podaj city_slug miasta z search_locations."
    )
    assert caught.value.detail == "d"


def test_an_unknown_district_points_to_the_districts_of_search_locations() -> None:
    """The district's list of an unknown district (or city) answers like an unknown city
    [P 2026-10-31]; the search names the district in its city."""
    fake = FakeCatalogs(
        errors={"search": NotFoundError("Serwis nie zna żądanych danych.", detail="d")}
    )
    request = SearchOffersRequest.parse(city="warszawa", district=" Mokotow Gorny ")

    with pytest.raises(NotFoundError) as caught:
        SearchOffers(fake, EchoPageLinks()).execute(request)

    assert str(caught.value) == (
        "Serwis nie zna dzielnicy 'Mokotow Gorny' w mieście 'warszawa'. Podaj nazwę dzielnicy "
        "tak, jak zwraca ją search_locations (kind=district, pole name), razem z city_slug "
        "jej miasta."
    )
    assert caught.value.detail == "d"


def test_a_page_above_1_that_is_not_found_may_be_past_the_last_one() -> None:
    """[P 2026-10-31, live e2e] the 2.0 list answers a page past its last one with the 404
    marker of an unknown city, so a page above 1 names both readings and points to page=1."""
    fake = FakeCatalogs(
        errors={"search": NotFoundError("Serwis nie zna żądanych danych.", detail="d")}
    )

    with pytest.raises(NotFoundError) as caught:
        SearchOffers(fake, EchoPageLinks()).execute(SearchOffersRequest.parse(city="sopot", page=2))

    assert str(caught.value) == (
        "Serwis nie ma strony 2 tej listy albo nie zna miasta 'sopot': lista może mieć mniej "
        "stron (pages_available podaje page=1); jeśli page=1 też zawiedzie, podaj city_slug "
        "miasta z search_locations."
    )


@pytest.mark.parametrize(
    ("given", "subject"),
    [
        ({"city": "warszawa"}, "Wyszukiwanie ofert w 'warszawa'"),
        (
            {"city": "warszawa", "district": "Mokotów"},
            "Wyszukiwanie ofert w 'warszawa' (dzielnica 'Mokotów')",
        ),
    ],
)
def test_unexpected_data_keeps_its_type_and_names_the_search(
    given: dict[str, Any], subject: str
) -> None:
    fake = FakeCatalogs(errors={"search": UnexpectedResponseError("Inny format.", detail="x")})

    with pytest.raises(UnexpectedResponseError) as caught:
        SearchOffers(fake, EchoPageLinks()).execute(SearchOffersRequest.parse(**given))

    assert str(caught.value) == f"{subject}: Inny format."


@pytest.mark.parametrize(
    "given",
    [
        {"city": "polska"},
        {"city": " polska ", "district": "Mokotów", "page": 2},
        {"city": "polska", "price_min": -1, "per_page": 7},
    ],
)
def test_the_whole_country_is_refused_before_anything_is_sent(given: dict[str, Any]) -> None:
    """[P 2026-10-29] pages-rsc.md: the service's list of Poland is a list of cities (308 to
    ``/ceny-ofertowe/polska/miasta``), so a search is of one city; the refusal comes with
    the city, before the other parameters are checked."""
    with pytest.raises(InvalidInputError) as caught:
        SearchOffersRequest.parse(**given)

    assert str(caught.value) == (
        "city=polska nie działa przy wyszukiwaniu ofert: serwis nie ma jednej listy ofert "
        "całej Polski. Podaj city_slug jednego miasta z search_locations (np. warszawa); "
        "oferty kilku miast wyszukaj osobno dla każdego."
    )


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
