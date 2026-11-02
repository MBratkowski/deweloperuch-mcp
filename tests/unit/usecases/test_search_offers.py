"""Tests of ``deweloperuch_mcp.usecases.search_offers``."""

import re
from typing import Any

import pytest

from deweloperuch_mcp.models.district import District
from deweloperuch_mcp.models.errors import (
    InvalidInputError,
    LimiterWaitError,
    NotFoundError,
    RateLimitedError,
    ServiceBlockedError,
    ServiceError,
    SessionClosedError,
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
from support.builders.districts import (
    districts_of,
    no_districts_message,
    unlisted_district_message,
    warszawa_districts,
    with_service_slug,
)
from support.builders.offers import unknown_district_message
from support.fakes.catalogs import DEVELOPER, EchoPageLinks, FakeCatalogs, offer
from support.fakes.districts import FakeDistrictDirectory, FakeDistrictLists
from support.fakes.places import VILLAGE, FakePlaces, unknown_place_message


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

    found = SearchOffers(fake, EchoPageLinks(), FakeDistrictDirectory(), FakePlaces()).execute(
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
        SearchOffers(
            FakeCatalogs(page=page), EchoPageLinks(), FakeDistrictDirectory(), FakePlaces()
        )
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


def not_found(places: FakePlaces, **given: Any) -> NotFoundError:
    """What a search ends with when the service does not know its list."""
    fake = FakeCatalogs(
        errors={"search": NotFoundError("Serwis nie zna żądanych danych.", detail="d")}
    )
    with pytest.raises(NotFoundError) as caught:
        SearchOffers(fake, EchoPageLinks(), FakeDistrictDirectory(), places).execute(
            SearchOffersRequest.parse(**given)
        )
    assert caught.value.detail == "d"
    return caught.value


def test_an_unknown_place_says_there_is_no_such_place() -> None:
    places = FakePlaces()

    found = not_found(places, city="atlantyda")

    assert str(found) == (unknown_place_message("atlantyda"))
    assert places.calls == ["atlantyda"]


def test_a_known_place_without_offers_says_so() -> None:
    found = not_found(FakePlaces.knowing(VILLAGE), city=VILLAGE.slug)

    assert str(found) == (
        "Miejscowość 'Ignatki-osiedle' istnieje, ale serwis nie ma dla niej ofert. "
        "Nie ponawiaj; powiedz to użytkownikowi."
    )


def test_an_unknown_city_points_to_search_locations_when_the_lookup_cannot_tell() -> None:
    found = not_found(FakePlaces(failure=UnexpectedResponseError("inny format")), city="atlantyda")

    assert str(found) == (
        "Serwis nie zna miasta 'atlantyda'. Podaj city_slug miasta z search_locations."
    )


@pytest.mark.parametrize(
    "given",
    [
        pytest.param({"district": "Mokotów"}, id="district"),
        pytest.param({"page": 2}, id="page-2"),
    ],
)
def test_only_the_first_page_of_a_city_looks_up_the_place(given: dict[str, Any]) -> None:
    """A district's list (an unknown district or city) and a page past the last one have
    "not found" answers of their own: the place says nothing about them."""
    places = FakePlaces.knowing(VILLAGE)

    not_found(places, city=VILLAGE.slug, **given)

    assert places.calls == []


def search_in(
    district: str,
    directory: FakeDistrictDirectory,
    lists: FakeDistrictLists,
    page: int = 1,
) -> SearchOffersResult:
    request = SearchOffersRequest.parse(city="warszawa", district=district, page=page)
    return SearchOffers(lists, EchoPageLinks(), directory, FakePlaces()).execute(request)


def test_unknown_district_lists_real_names() -> None:
    """A district the service does not list (Oliwa is Gdańsk's): the names of the city's
    real districts, all 18, in the service's order."""
    directory, lists = FakeDistrictDirectory(), FakeDistrictLists(search_page(3))

    with pytest.raises(NotFoundError) as caught:
        search_in("Oliwa", directory, lists)

    assert str(caught.value) == unlisted_district_message("Oliwa")
    assert caught.value.detail == "404"
    assert (directory.calls, lists.searched) == (["warszawa"], ["Oliwa"])


def test_more_than_25_districts_are_cut_and_counted() -> None:
    """26 districts: the real 18 and 8 copies of them under other names."""
    real = warszawa_districts()
    copies = tuple(District(name=f"{found.name} II", slug=f"{found.slug}-ii") for found in real)
    directory = FakeDistrictDirectory(real + copies[:8])

    with pytest.raises(NotFoundError) as caught:
        search_in("Oliwa", directory, FakeDistrictLists(search_page(3)))

    names = ", ".join(found.name for found in (real + copies)[:25])
    assert str(caught.value) == (
        "Serwis nie zna dzielnicy 'Oliwa' w mieście 'warszawa'. Znane dzielnice tego miasta "
        f"(25 z 26): {names}. Podaj w district jedną z nich albo szukaj bez district."
    )
    assert names.endswith("Praga-Południe II") and "Ursus II" not in str(caught.value)


def test_the_real_directory_finds_a_name_written_otherwise() -> None:
    """„Moko-tów” makes the slug ``moko-tow``, which the service does not know; the real
    answer has Mokotów, so its list is asked again by the service's slug."""
    page = search_page(959)
    directory, lists = FakeDistrictDirectory(), FakeDistrictLists(page, frozenset({"mokotow"}))

    found = search_in("Moko-tów", directory, lists)

    assert (found.page, found.list_url) == (page, "list:warszawa:1:mokotow")
    assert (directory.calls, lists.searched) == (["warszawa"], ["Moko-tów", "mokotow"])


def test_district_with_another_service_slug_is_retried_once() -> None:
    """The service addresses Praga-Północ by another slug than the client makes of the name:
    the list is asked again, once, with the service's slug, and its page is the result."""
    page = search_page(990)
    directory = FakeDistrictDirectory(districts_of(with_service_slug("Praga-Północ", "praga-pn")))
    lists = FakeDistrictLists(page, frozenset({"praga-pn"}))

    found = search_in("Praga Północ", directory, lists)

    assert (found.page, found.list_url) == (page, "list:warszawa:1:praga-pn")
    assert (directory.calls, lists.searched) == (["warszawa"], ["Praga Północ", "praga-pn"])


@pytest.mark.parametrize("asked", ["ŚRÓDMIEŚCIE", "srodmiescie", "Śródmieście"])
def test_district_match_folds_case_and_letters(asked: str) -> None:
    directory = FakeDistrictDirectory(districts_of(with_service_slug("Śródmieście", "centrum")))
    lists = FakeDistrictLists(search_page(245), frozenset({"centrum"}))

    found = search_in(asked, directory, lists)

    assert found.page.total == 245
    assert lists.searched == [asked, "centrum"]


def test_a_retry_the_service_does_not_know_either_keeps_the_first_answer() -> None:
    directory = FakeDistrictDirectory(districts_of(with_service_slug("Praga-Północ", "praga-pn")))
    lists = FakeDistrictLists(search_page(3))

    with pytest.raises(NotFoundError) as caught:
        search_in("Praga Północ", directory, lists)

    assert str(caught.value) == unknown_district_message("Praga Północ")
    assert lists.searched == ["Praga Północ", "praga-pn"]


def test_a_listed_district_under_the_same_address_is_not_asked_again() -> None:
    """Page 3 of a district the service lists under the slug already sent: the page, not the
    district, is missing, so the list is not asked again and the answer names both."""
    lists = FakeDistrictLists(search_page(3))

    with pytest.raises(NotFoundError) as caught:
        search_in("mokotow", FakeDistrictDirectory(), lists, page=3)

    assert str(caught.value).startswith("Serwis nie ma strony 3 tej listy albo nie zna dzielnicy")
    assert lists.searched == ["mokotow"]


def test_an_unlisted_district_is_refused_on_any_page() -> None:
    with pytest.raises(NotFoundError) as caught:
        search_in("Oliwa", FakeDistrictDirectory(), FakeDistrictLists(search_page(3)), page=4)

    assert str(caught.value) == unlisted_district_message("Oliwa")


def test_city_without_offer_districts_says_so() -> None:
    """An empty list: the service lists no district for the city (or does not know it)."""
    with pytest.raises(NotFoundError) as caught:
        search_in("Oliwa", FakeDistrictDirectory(()), FakeDistrictLists(search_page(3)))

    assert str(caught.value) == no_districts_message("Oliwa", "warszawa")


def test_known_district_never_reads_the_directory() -> None:
    directory = FakeDistrictDirectory()
    request = SearchOffersRequest.parse(city="warszawa", district="Mokotów")

    SearchOffers(
        FakeCatalogs(page=search_page(959)), EchoPageLinks(), directory, FakePlaces()
    ).execute(request)

    assert directory.calls == []


def test_an_unknown_city_never_reads_the_directory() -> None:
    directory = FakeDistrictDirectory()
    fake = FakeCatalogs(errors={"search": NotFoundError("Serwis nie zna żądanych danych.")})

    with pytest.raises(NotFoundError):
        SearchOffers(fake, EchoPageLinks(), directory, FakePlaces()).execute(
            SearchOffersRequest.parse(city="atlantyda")
        )

    assert directory.calls == []


@pytest.mark.parametrize(
    "error",
    [
        NotFoundError("Serwis nie zna żądanych danych."),
        ServiceError("Serwis chwilowo nie odpowiada.", 10.0),
        UnexpectedResponseError("Inny format."),
    ],
)
def test_a_failing_directory_keeps_the_unknown_district_message(error: Exception) -> None:
    """Without the city's districts the search says what it said before it read them."""
    request = SearchOffersRequest.parse(city="warszawa", district=" Mokotow Gorny ")
    lists = FakeDistrictLists(search_page(3))

    with pytest.raises(NotFoundError) as caught:
        SearchOffers(
            lists, EchoPageLinks(), FakeDistrictDirectory(error=error), FakePlaces()
        ).execute(request)

    assert str(caught.value) == (
        "Serwis nie zna dzielnicy 'Mokotow Gorny' w mieście 'warszawa'. Podaj nazwę dzielnicy "
        "z search_locations (kind=district, pole name), razem z city_slug jej miasta."
    )
    assert caught.value.detail == "404"


SERIES_ERRORS = [
    ServiceBlockedError("STOP: 403."),
    RateLimitedError("STOP: 429.", 300.0),
    LimiterWaitError("Kolejka zapytań jest zajęta.", 30.0),
    SessionClosedError("Sesja jest zamknięta."),
]
"""Errors about the series of requests, not about the data: they pass unchanged."""


@pytest.mark.parametrize("error", SERIES_ERRORS)
def test_a_series_error_while_reading_the_directory_passes_unchanged(error: Exception) -> None:
    with pytest.raises(type(error)) as caught:
        search_in("Oliwa", FakeDistrictDirectory(error=error), FakeDistrictLists(search_page(3)))

    assert caught.value is error


@pytest.mark.parametrize("error", SERIES_ERRORS)
def test_a_series_error_of_the_retry_passes_unchanged(error: Exception) -> None:
    lists = FakeDistrictLists(search_page(3), errors={"mokotow": error})

    with pytest.raises(type(error)) as caught:
        search_in("Moko-tów", FakeDistrictDirectory(), lists)

    assert caught.value is error
    assert lists.searched == ["Moko-tów", "mokotow"]


@pytest.mark.parametrize(
    "error",
    [ServiceError("Serwis chwilowo nie odpowiada.", 10.0), UnexpectedResponseError("Inny format.")],
)
def test_a_service_error_of_the_retry_keeps_its_type_and_names_the_asked_district(
    error: ServiceError,
) -> None:
    lists = FakeDistrictLists(search_page(3), errors={"mokotow": error})

    with pytest.raises(type(error)) as caught:
        search_in("Moko-tów", FakeDistrictDirectory(), lists)

    assert str(caught.value) == f"Wyszukiwanie ofert w 'warszawa' (dzielnica 'Moko-tów'): {error}"
    assert caught.value.pause_seconds == error.pause_seconds


def test_a_page_above_1_that_is_not_found_may_be_past_the_last_one() -> None:
    """[P 2026-10-31, live e2e] the 2.0 list answers a page past its last one with the 404
    marker of an unknown city, so a page above 1 names both readings and points to page=1."""
    fake = FakeCatalogs(
        errors={"search": NotFoundError("Serwis nie zna żądanych danych.", detail="d")}
    )

    with pytest.raises(NotFoundError) as caught:
        SearchOffers(fake, EchoPageLinks(), FakeDistrictDirectory(), FakePlaces()).execute(
            SearchOffersRequest.parse(city="sopot", page=2)
        )

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
        SearchOffers(fake, EchoPageLinks(), FakeDistrictDirectory(), FakePlaces()).execute(
            SearchOffersRequest.parse(**given)
        )

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
        SearchOffers(fake, EchoPageLinks(), FakeDistrictDirectory(), FakePlaces()).execute(
            SearchOffersRequest.parse(city="warszawa")
        )

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
