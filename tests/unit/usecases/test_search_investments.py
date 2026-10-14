"""Tests of ``deweloperuch_mcp.usecases.search_investments``."""

import re
from typing import Any

import pytest

from deweloperuch_mcp.api.links import ServicePageLinks
from deweloperuch_mcp.consumers.shared.investment_search_views import InvestmentSearchView
from deweloperuch_mcp.models.errors import (
    InvalidInputError,
    InvalidValueError,
    NotFoundError,
    ServiceError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.models.investment_summary import (
    InvestmentMatches,
    InvestmentName,
    InvestmentSearchCriteria,
    InvestmentsLimit,
    InvestmentSort,
)
from deweloperuch_mcp.models.values import DeveloperSlug
from deweloperuch_mcp.usecases.search_investments import (
    DEVELOPER_NEEDS_CITY,
    NEEDS_CITY_OR_NAME,
    SORT_NEEDS_CITY,
    WHOLE_COUNTRY_INVESTMENTS,
    SearchInvestments,
    SearchInvestmentsRequest,
)
from support.builders.investment_search import SOPOT
from support.fakes.investment_search import FakeInvestmentDirectory, summary
from support.providers.service import PAGES


def search(directory: FakeInvestmentDirectory, **given: Any) -> InvestmentSearchView:
    request = SearchInvestmentsRequest.parse(**given)
    found = SearchInvestments(directory, ServicePageLinks()).execute(request)
    return InvestmentSearchView.from_result(found)


def test_a_city_asks_for_its_list_once_and_links_each_investment() -> None:
    directory = FakeInvestmentDirectory()

    result = search(directory, city="sopot", limit=2)

    assert directory.asked == [("in_city", SOPOT, None)]
    assert [item.name for item in result.items] == ["Ąkacje", "Morskie"]
    first = result.items[0]
    assert first.investment_url == PAGES + "/sopot/deweloperzy/invest-komfort-spolka-akcyjna/akacje"
    assert first.developer_url == PAGES + "/sopot/deweloperzy/invest-komfort-spolka-akcyjna"
    assert (first.developer_slug, result.items[1].developer_slug) == (
        "invest-komfort-spolka-akcyjna",
        "atal",
    )
    assert result.hint == (
        "Pasujących inwestycji jest 5, pokazano pierwsze 2 (sort=active_offers). Zawęź "
        "wyniki przez name lub developer_slug albo zmień sort."
    )


def test_a_name_asks_the_service_with_the_limit_and_has_no_links() -> None:
    directory = FakeInvestmentDirectory()

    result = search(directory, name=" nowy targ ", limit=3)

    assert directory.asked == [("by_name", InvestmentName("nowy targ"), InvestmentsLimit(3))]
    assert [(item.name, item.offers_active) for item in result.items] == [("Nowy Targ", 4)]
    assert (result.items[0].investment_url, result.items[0].developer_url) == (None, None)
    assert (result.total, result.returned, result.truncated, result.hint) == (1, 1, False, None)


@pytest.mark.parametrize(
    ("directory", "given", "hint"),
    [
        (
            FakeInvestmentDirectory(city=()),
            {"city": "sopot"},
            "Serwis nie pokazuje żadnej inwestycji dla 'sopot': miasto może nie mieć "
            "aktywnych ofert deweloperów albo slug jest błędny. Sprawdź slug i offer_count "
            "miasta w search_locations; inwestycję po nazwie znajdziesz też bez city (name).",
        ),
        (
            FakeInvestmentDirectory(),
            {"city": "sopot", "name": "zzz"},
            "Żadna inwestycja w 'sopot' nie pasuje do name i developer_slug. Sprawdź pisownię "
            "albo pomiń te filtry, żeby zobaczyć wszystkie inwestycje miasta.",
        ),
        (
            FakeInvestmentDirectory(matches=InvestmentMatches(())),
            {"name": "zzz"},
            "Nic nie pasuje do 'zzz'. Sprawdź pisownię albo podaj krótszy fragment nazwy; z "
            "city przeszukasz inwestycje jednego miasta.",
        ),
        (
            FakeInvestmentDirectory(matches=InvestmentMatches((summary("A"),), 7, True)),
            {"name": "nowy"},
            "Pasujących inwestycji jest 7 (wg serwisu), pokazano 1. Doprecyzuj nazwę albo "
            "dodaj city.",
        ),
        (
            FakeInvestmentDirectory(matches=InvestmentMatches((summary("A"),), None, True)),
            {"name": "nowy"},
            "Pasujących inwestycji jest więcej, pokazano 1. Doprecyzuj nazwę albo dodaj city.",
        ),
        (
            FakeInvestmentDirectory(),
            {"city": "sopot", "sort": "name", "limit": 1},
            "Pasujących inwestycji jest 5, pokazano pierwsze 1 (sort=name). Zawęź wyniki "
            "przez name lub developer_slug albo zmień sort.",
        ),
    ],
)
def test_the_hint_says_what_to_do(
    directory: FakeInvestmentDirectory, given: dict[str, Any], hint: str
) -> None:
    assert search(directory, **given).hint == hint


def test_a_complete_result_has_no_hint() -> None:
    assert search(FakeInvestmentDirectory(), city="sopot").hint is None


@pytest.mark.parametrize(
    ("given", "error", "kind", "message"),
    [
        (
            {"city": "sopot"},
            NotFoundError("Serwis nie zna żądanych danych (HTTP 404).", detail="/api/x"),
            NotFoundError,
            "Serwis nie zna miasta 'sopot'. Podaj city_slug z search_locations.",
        ),
        (
            {"city": "sopot"},
            ServiceError("Serwis odpowiedział błędem HTTP 400.", detail="/api/x"),
            ServiceError,
            "Wyszukiwanie inwestycji w 'sopot': Serwis odpowiedział błędem HTTP 400.",
        ),
        (
            {"name": "nowy"},
            UnexpectedResponseError("Inny format.", detail="/api/x"),
            UnexpectedResponseError,
            "Wyszukiwanie inwestycji po nazwie: Inny format.",
        ),
    ],
)
def test_a_failure_says_what_it_is_about(
    given: dict[str, Any], error: Exception, kind: type[Exception], message: str
) -> None:
    with pytest.raises(kind) as caught:
        search(FakeInvestmentDirectory(error=error), **given)

    assert str(caught.value) == message
    assert getattr(caught.value, "detail", None) == "/api/x"  # for the log only (D12)


@pytest.mark.parametrize(
    ("given", "message"),
    [
        (
            {"city": "Sopot"},
            "city: oczekiwano slug jednego miasta (np. warszawa, sopot; nie polska); slug "
            "podaje search_locations; podano 'Sopot'.",
        ),
        ({"city": " polska ", "name": "Kolibki"}, WHOLE_COUNTRY_INVESTMENTS),
        ({"name": "k"}, "name: podaj od 2 do 100 znaków nazwy inwestycji, podano 'k'."),
        (
            {"city": "sopot", "developer_slug": "ATAL"},
            "developer_slug: oczekiwano slug dewelopera, np. atal; podają go "
            "search_developers, search_offers i search_investments (developer_slug); podano "
            "'ATAL'.",
        ),
        (
            {"city": "sopot", "sort": "cheap"},
            "sort musi być jedną z wartości active_offers, price_per_m2_asc, "
            "price_per_m2_desc, price_asc, price_desc, name, podano 'cheap'.",
        ),
        (
            {"city": "sopot", "limit": 0},
            "limit musi być liczbą całkowitą z zakresu 1–500 (liczba inwestycji w wyniku), "
            "podano 0.",
        ),
        ({}, NEEDS_CITY_OR_NAME),
        ({"developer_slug": "atal"}, NEEDS_CITY_OR_NAME),
        ({"name": "Kolibki", "developer_slug": "atal"}, DEVELOPER_NEEDS_CITY),
        ({"name": "Kolibki", "sort": "name"}, SORT_NEEDS_CITY),
    ],
)
def test_a_refusal_names_the_parameter_and_what_to_give(
    given: dict[str, Any], message: str
) -> None:
    with pytest.raises(InvalidInputError) as caught:
        SearchInvestmentsRequest.parse(**given)

    assert str(caught.value) == message
    assert not isinstance(caught.value, InvalidValueError)  # worded for the caller


@pytest.mark.parametrize(
    ("given", "first"),
    [
        ({"city": "X", "name": "k", "developer_slug": "X", "sort": "x", "limit": 0}, "city"),
        ({"city": "polska", "name": "k", "sort": "x"}, "city=polska"),
        ({"name": "k", "developer_slug": "X", "sort": "x", "limit": 0}, "name"),
        ({"name": "ok", "developer_slug": "X", "sort": "x", "limit": 0}, "developer_slug"),
        ({"name": "ok", "sort": "x", "limit": 0}, "sort"),
        ({"name": "ok", "limit": 0}, "limit"),
    ],
)
def test_the_arguments_are_checked_in_the_order_of_the_parameters(
    given: dict[str, Any], first: str
) -> None:
    with pytest.raises(InvalidInputError, match=rf"\A{re.escape(first)}"):
        SearchInvestmentsRequest.parse(**given)


def test_the_arguments_taken() -> None:
    assert SearchInvestmentsRequest.parse(city=" sopot ").criteria == InvestmentSearchCriteria(
        city=SOPOT
    )
    assert SearchInvestmentsRequest.parse(
        city="sopot", name=" Kolibki ", developer_slug=" atal ", sort="name", limit=50
    ).criteria == InvestmentSearchCriteria(
        city=SOPOT,
        name=InvestmentName("Kolibki"),
        developer=DeveloperSlug("atal"),
        sort=InvestmentSort.NAME,
        limit=InvestmentsLimit(50),
    )
    assert SearchInvestmentsRequest.parse(name="nowy targ").criteria == InvestmentSearchCriteria(
        name=InvestmentName("nowy targ")
    )
