"""Tests of ``deweloperuch_mcp.models.investment_summary``."""

from collections.abc import Callable
from typing import Any

import pytest

from deweloperuch_mcp.models.errors import (
    InvalidValueError,
    OneOf,
    SlugText,
    TextLength,
    ValueName,
    WholeNumber,
)
from deweloperuch_mcp.models.investment_summary import (
    InvestmentMatches,
    InvestmentName,
    InvestmentsCity,
    InvestmentSearchCriteria,
    InvestmentSearchResult,
    InvestmentsLimit,
    InvestmentSort,
)
from deweloperuch_mcp.models.values import CitySlug, DeveloperSlug
from deweloperuch_mcp.usecases.support import arguments
from support.builders.investment_search import SOPOT
from support.fakes.investment_search import CITY, summary


def in_city(**given: Any) -> InvestmentSearchCriteria:
    return InvestmentSearchCriteria(city=SOPOT, **given)


def names(result: InvestmentSearchResult) -> list[str]:
    return [item.name for item in result.items]


SORTS = tuple(sort.value for sort in InvestmentSort)


LONG = "x" * 101


def by_name(limit: int = 10) -> InvestmentSearchCriteria:
    return InvestmentSearchCriteria(name=InvestmentName("nowy"), limit=InvestmentsLimit(limit))


def test_folded_ignores_case_polish_diacritics_and_repeated_spaces() -> None:
    assert InvestmentName.folded("  Nowy   TARGÓWEK  ") == "nowy targowek"
    assert InvestmentName.folded("Łąka Źródło Żółć Ćma Ńę Ś") == "laka zrodlo zolc cma ne s"


@pytest.mark.parametrize(
    ("part", "name", "found"),
    [
        ("kolibki", "Nowe Kolibki etap 4", True),
        ("targowek", "Nowy Targówek VI", True),
        ("NOWY  targ", "Apartamenty Nowy Targ", True),
        ("Łąka", "Osiedle Laka", True),
        ("smolna", "Nowe Kolibki etap 4", False),
    ],
)
def test_a_part_of_the_name_matches_regardless_of_case_and_diacritics(
    part: str, name: str, found: bool
) -> None:
    assert InvestmentName(part).matches(name) is found


@pytest.mark.parametrize(
    ("make", "value", "rule", "given"),
    [
        (lambda: InvestmentName.parse(" k "), ValueName.INVESTMENT_NAME, TextLength(2, 100), " k "),
        (lambda: InvestmentName.parse(7), ValueName.INVESTMENT_NAME, TextLength(2, 100), 7),
        (lambda: InvestmentName(LONG), ValueName.INVESTMENT_NAME, TextLength(2, 100), LONG),
        (lambda: DeveloperSlug.parse("ATAL"), ValueName.DEVELOPER, SlugText(), "ATAL"),
        (lambda: InvestmentsCity.parse("Sopot"), ValueName.INVESTMENTS_CITY, SlugText(), "Sopot"),
        (lambda: InvestmentSort.parse("cheap"), ValueName.INVESTMENT_SORT, OneOf(SORTS), "cheap"),
        (lambda: InvestmentsLimit(0), ValueName.INVESTMENTS_LIMIT, WholeNumber(1, 500), 0),
        (
            lambda: InvestmentsLimit.parse(True),
            ValueName.INVESTMENTS_LIMIT,
            WholeNumber(1, 500),
            True,
        ),
    ],
)
def test_the_values_refuse_in_the_domains_words(
    make: Callable[[], object], value: ValueName, rule: object, given: object
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        make()

    assert (caught.value.value, caught.value.rule, caught.value.given) == (value, rule, given)
    # The application words every refusal of the domain (no KeyError).
    assert arguments.ParameterCheck.explained(caught.value).endswith(f"{given!r}.")


def test_the_values_as_given() -> None:
    assert InvestmentName.parse("  Nowe Kolibki ").text == "Nowe Kolibki"
    assert InvestmentsCity.parse(" sopot ") == InvestmentsCity("sopot")
    assert isinstance(InvestmentsCity("sopot"), CitySlug)
    assert InvestmentSort.parse(None) is None
    assert InvestmentSort.parse("name") is InvestmentSort.NAME
    assert InvestmentsLimit().value == 10


@pytest.mark.parametrize(
    "given",
    [
        {},
        {"developer": DeveloperSlug("atal"), "name": InvestmentName("Kolibki")},
        {"sort": InvestmentSort.NAME, "name": InvestmentName("Kolibki")},
        {"city": InvestmentsCity("polska")},
    ],
)
def test_criteria_are_one_city_or_a_name(given: dict[str, Any]) -> None:
    """Invariants (the application refuses these first, in the parameters' words)."""
    with pytest.raises(ValueError):
        InvestmentSearchCriteria(**given)


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        # The most active offers first; ties by name; without a count last.
        (None, ["Ąkacje", "Morskie", "Zielone", "Brzozy", "Akacjowe"]),
        (InvestmentSort.ACTIVE_OFFERS, ["Ąkacje", "Morskie", "Zielone", "Brzozy", "Akacjowe"]),
        # Without an average last in both directions.
        (InvestmentSort.PRICE_PER_M2_ASC, ["Morskie", "Zielone", "Brzozy", "Ąkacje", "Akacjowe"]),
        (InvestmentSort.PRICE_PER_M2_DESC, ["Brzozy", "Zielone", "Morskie", "Ąkacje", "Akacjowe"]),
        (InvestmentSort.PRICE_ASC, ["Brzozy", "Zielone", "Morskie", "Ąkacje", "Akacjowe"]),
        (InvestmentSort.PRICE_DESC, ["Morskie", "Zielone", "Brzozy", "Ąkacje", "Akacjowe"]),
        # Alphabetically without diacritics: "akacje" before "akacjowe".
        (InvestmentSort.NAME, ["Ąkacje", "Akacjowe", "Brzozy", "Morskie", "Zielone"]),
    ],
)
def test_a_city_is_ordered(sort: InvestmentSort | None, expected: list[str]) -> None:
    result = in_city(sort=sort, limit=InvestmentsLimit(50)).select(CITY)

    assert names(result) == expected
    assert (result.total, result.returned, result.truncated) == (5, 5, False)


def test_a_city_is_cut_to_the_limit_and_says_so() -> None:
    result = in_city(limit=InvestmentsLimit(2)).select(CITY)

    assert names(result) == ["Ąkacje", "Morskie"]
    assert (result.total, result.returned, result.truncated) == (5, 2, True)


def test_a_city_is_filtered_by_name_and_developer_before_the_cut() -> None:
    akacje = in_city(name=InvestmentName("AKACJ"), limit=InvestmentsLimit(1)).select(CITY)
    atal = in_city(developer=DeveloperSlug("atal")).select(CITY)
    both = in_city(name=InvestmentName("morsk"), developer=DeveloperSlug("atal")).select(CITY)
    nobody = in_city(developer=DeveloperSlug("nikt")).select(CITY)

    assert (names(akacje), akacje.total, akacje.truncated) == (["Ąkacje"], 2, True)
    assert names(atal) == ["Morskie", "Akacjowe"]
    assert names(both) == ["Morskie"]
    assert (names(nobody), nobody.total, nobody.truncated) == ([], 0, False)


def test_an_investment_without_its_developer_never_matches_a_developer() -> None:
    lone = summary("Samotna", developer=None)

    assert not in_city(developer=DeveloperSlug("atal")).admits(lone)
    assert in_city().admits(lone)
    assert lone.ref is None


@pytest.mark.parametrize(
    ("matches", "limit", "expected"),
    [
        # The service's total and order; fewer than the limit: complete.
        (InvestmentMatches((summary("B"), summary("A")), 2, False), 10, (["B", "A"], 2, False)),
        # The service has more than it gave.
        (InvestmentMatches((summary("B"), summary("A")), 9, True), 10, (["B", "A"], 9, True)),
        # Without a total: unknown, cut by "more" alone.
        (InvestmentMatches((summary("B"),), None, False), 10, (["B"], None, False)),
        (InvestmentMatches((summary("B"),), None, True), 10, (["B"], None, True)),
        # A total below what it gave is raised; more than the limit is cut.
        (InvestmentMatches((summary("B"), summary("A")), 1, False), 1, (["B"], 2, True)),
        # Without a total, more than the limit is cut too: truncated by the cut alone.
        (InvestmentMatches((summary("B"), summary("A")), None, False), 1, (["B"], None, True)),
    ],
)
def test_matches_by_name_as_the_service_gave_them(
    matches: InvestmentMatches, limit: int, expected: tuple[list[str], int | None, bool]
) -> None:
    result = InvestmentSearchResult.of_matches(by_name(limit), matches)

    assert (names(result), result.total, result.truncated) == expected


def test_a_search_by_name_shows_at_most_50() -> None:
    many = InvestmentMatches(tuple(summary(f"N{index}") for index in range(60)), 60)

    result = InvestmentSearchResult.of_matches(by_name(500), many)

    assert by_name(500).shown_at_most == InvestmentsLimit(50)
    assert by_name(7).shown_at_most == InvestmentsLimit(7)
    assert in_city(limit=InvestmentsLimit(500)).shown_at_most == InvestmentsLimit(500)
    assert (result.returned, result.total, result.truncated) == (50, 60, True)


@pytest.mark.parametrize(
    ("criteria", "matches", "larger"),
    [
        (by_name(10), InvestmentMatches((summary("A"),), 9, True), True),
        (by_name(50), InvestmentMatches((summary("A"),), 90, True), False),  # the cap
        (by_name(500), InvestmentMatches((summary("A"),), 90, True), False),
        (by_name(10), InvestmentMatches((summary("A"),), 1, False), False),  # complete
    ],
)
def test_a_larger_limit_helps_only_below_the_cap(
    criteria: InvestmentSearchCriteria, matches: InvestmentMatches, larger: bool
) -> None:
    assert InvestmentSearchResult.of_matches(criteria, matches).larger_limit_shows_more is larger


def test_a_larger_limit_helps_a_city_below_500() -> None:
    assert in_city(limit=InvestmentsLimit(2)).select(CITY).larger_limit_shows_more
    assert not in_city(limit=InvestmentsLimit(5)).select(CITY).larger_limit_shows_more
    many = [summary(f"N{index}") for index in range(501)]
    assert not in_city(limit=InvestmentsLimit(500)).select(many).larger_limit_shows_more
