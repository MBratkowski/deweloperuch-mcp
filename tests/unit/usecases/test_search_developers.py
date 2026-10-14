"""Tests of ``deweloperuch_mcp.usecases.search_developers``."""

import pytest

from deweloperuch_mcp.models.developer_match import DEFAULT_MATCHES, DeveloperName, MatchCount
from deweloperuch_mcp.models.errors import InvalidInputError, ServiceError
from deweloperuch_mcp.models.values import CitySlug
from deweloperuch_mcp.usecases.search_developers import SearchDevelopers, SearchDevelopersRequest
from support.builders.developer_search import matches
from support.fakes.developer_search import ATAL, FakeDeveloperLinks, FakeDeveloperSearch


def test_search_developers_asks_once_and_links_each_profile_in_the_whole_country() -> None:
    directory, links = FakeDeveloperSearch(), FakeDeveloperLinks()

    found = SearchDevelopers(directory, links).execute(
        SearchDevelopersRequest(name=DeveloperName("atal"), limit=MatchCount(5))
    )

    assert directory.calls == [(DeveloperName("atal"), MatchCount(5))]
    assert found.search.items == (ATAL,)
    assert found.developer_urls == ("profile:polska/atal",)
    assert links.calls == [("atal", CitySlug("polska"))]
    assert found.hint is None


def test_a_truncated_search_says_to_narrow_the_name_or_raise_the_limit() -> None:
    directory = FakeDeveloperSearch(matches(5, total=12, more=True))

    found = SearchDevelopers(directory, FakeDeveloperLinks()).execute(
        SearchDevelopersRequest(name=DeveloperName("dom"), limit=MatchCount(5))
    )

    assert found.hint == (
        "Pokazano 5 z 12 pasujących deweloperów. Doprecyzuj nazwę albo zwiększ limit (najwyżej 20)."
    )


def test_a_truncated_search_at_the_largest_limit_only_says_to_narrow_the_name() -> None:
    directory = FakeDeveloperSearch(matches(20, total=None, more=True))

    found = SearchDevelopers(directory, FakeDeveloperLinks()).execute(
        SearchDevelopersRequest(name=DeveloperName("dom"), limit=MatchCount(20))
    )

    assert found.hint == (
        "Pokazano 20 pasujących deweloperów, a może ich być więcej. Doprecyzuj nazwę."
    )


def test_nothing_found_says_what_to_try() -> None:
    directory = FakeDeveloperSearch(matches(0, total=0, more=False))

    found = SearchDevelopers(directory, FakeDeveloperLinks()).execute(
        SearchDevelopersRequest(name=DeveloperName("xyzzy"), limit=MatchCount())
    )

    assert found.hint == (
        "Żaden deweloper nie pasuje do 'xyzzy'. Sprawdź pisownię albo podaj krótszy "
        "fragment nazwy, np. jej pierwsze słowo."
    )
    assert found.developer_urls == ()


def test_a_failure_of_the_source_names_the_search() -> None:
    directory = FakeDeveloperSearch(error=ServiceError("Serwis odpowiedział błędem HTTP 500.", 3.0))

    with pytest.raises(ServiceError) as caught:
        SearchDevelopers(directory, FakeDeveloperLinks()).execute(
            SearchDevelopersRequest(name=DeveloperName("atal"), limit=MatchCount())
        )

    assert type(caught.value) is ServiceError
    assert str(caught.value) == "Wyszukiwanie deweloperów: Serwis odpowiedział błędem HTTP 500."
    assert caught.value.pause_seconds == 3.0


def test_the_arguments_are_domain_values() -> None:
    given = SearchDevelopersRequest.parse(name="  atal ", limit=7)

    assert given == SearchDevelopersRequest(name=DeveloperName("atal"), limit=MatchCount(7))
    assert SearchDevelopersRequest.parse(name="atal").limit == MatchCount(DEFAULT_MATCHES)


@pytest.mark.parametrize(
    ("name", "limit", "message"),
    [
        ("a", 5, "name: podaj od 2 do 100 znaków nazwy dewelopera, podano 'a'."),
        (None, 5, "name: podaj od 2 do 100 znaków nazwy dewelopera, podano None."),
        (
            "atal",
            0,
            "limit musi być liczbą całkowitą z zakresu 1–20 (liczba deweloperów w wyniku), "
            "podano 0.",
        ),
        (
            "atal",
            21,
            "limit musi być liczbą całkowitą z zakresu 1–20 (liczba deweloperów w wyniku), "
            "podano 21.",
        ),
        ("a", 0, "name: podaj od 2 do 100 znaków nazwy dewelopera, podano 'a'."),  # name first
    ],
)
def test_refused_arguments_name_the_parameter(name: object, limit: object, message: str) -> None:
    with pytest.raises(InvalidInputError) as caught:
        SearchDevelopersRequest.parse(name=name, limit=limit)

    assert str(caught.value) == message
