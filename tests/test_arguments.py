"""The parameters of the operations (``application.arguments``): what each takes, the
order they are checked in, and the exact message of every refusal, with the parameter's
name and the operation that gives the right value. The domain refuses in its own words
(tests/test_domain.py); these are the texts the CLI and the MCP server show (the goldens
pin them end to end).
"""

import re
from collections.abc import Callable
from typing import Any

import pytest

from deweloperuch_mcp.application import arguments
from deweloperuch_mcp.domain.errors import InvalidInputError, InvalidValueError, ValueName
from deweloperuch_mcp.domain.statistics import Dataset
from deweloperuch_mcp.domain.values import (
    AmountPln,
    AreaM2,
    CitySlug,
    InvestmentSlug,
    LocationSlug,
    OfferId,
    OffersLimit,
    OfferSort,
    PageNumber,
    PageSize,
)

LOCATION_HELP = (
    "location: oczekiwano polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo "
    "slug miasta bez polskich znaków, np. warszawa, krakow, jastrzebie (Jastrzębie-Zdrój); "
)

REFUSALS: list[tuple[str, Any, str]] = [
    (
        "query",
        lambda: arguments.location_query(" k "),
        "query: podaj od 2 do 100 znaków nazwy miasta, dzielnicy lub ulicy, podano ' k '.",
    ),
    (
        "city",
        lambda: arguments.offer_search(" Kraków "),
        "city: oczekiwano slug miasta (np. warszawa) albo polska; slug podaje "
        "search_locations; podano ' Kraków '.",
    ),
    (
        "price_min",
        lambda: arguments.offer_search("warszawa", price_min=-1),
        "price_min musi być liczbą całkowitą z zakresu 0–99999999 (PLN), podano -1.",
    ),
    (
        "price_max",
        lambda: arguments.offer_search("warszawa", price_max=100_000_000),
        "price_max musi być liczbą całkowitą z zakresu 0–99999999 (PLN), podano 100000000.",
    ),
    (
        "price order",
        lambda: arguments.offer_search("warszawa", price_min=7, price_max=5),
        "price_min (7) jest większe niż price_max (5); zamień je miejscami.",
    ),
    (
        "area_min",
        lambda: arguments.offer_search("warszawa", area_min=40.5),
        "area_min musi być liczbą całkowitą z zakresu 0–9999 (m²), podano 40.5.",
    ),
    (
        "area_max",
        lambda: arguments.offer_search("warszawa", area_max="60"),
        "area_max musi być liczbą całkowitą z zakresu 0–9999 (m²), podano '60'.",
    ),
    (
        "area order",
        lambda: arguments.offer_search("warszawa", area_min=60, area_max=40),
        "area_min (60) jest większe niż area_max (40); zamień je miejscami.",
    ),
    (
        "sort",
        lambda: arguments.offer_search("warszawa", sort="amount"),
        "sort musi być jedną z wartości price_asc, price_desc albo pusty (domyślna kolejność "
        "serwisu), podano 'amount'.",
    ),
    (
        "page",
        lambda: arguments.offer_search("warszawa", page=21),
        "page musi być liczbą całkowitą z zakresu 1–20 (serwis ma najwyżej 20 stron), podano 21.",
    ),
    (
        "per_page",
        lambda: arguments.offer_search("warszawa", per_page=20),
        "per_page musi być jedną z wartości 10, 50, 100 (inne serwis zamienia na 10), podano 20.",
    ),
    (
        "offer_id",
        lambda: arguments.offer(0, "smolna"),
        "offer_id musi być liczbą całkowitą z zakresu 1–9223372036854775807 (identyfikator "
        "oferty z search_offers), podano 0.",
    ),
    (
        "investment_slug",
        lambda: arguments.investment("Smolna"),
        "investment_slug: oczekiwano slug inwestycji, np. smolna; podaje go search_offers "
        "(investment_slug); podano 'Smolna'.",
    ),
    (
        "include_history",
        lambda: arguments.investment("smolna", include_history="yes"),
        "include_history musi być true albo false, podano 'yes'.",
    ),
    (
        "limit",
        lambda: arguments.investment("smolna", limit=-1),
        "limit musi być liczbą całkowitą z zakresu 0–100000 (liczba ofert w wyniku), podano -1.",
    ),
    (
        # The statistics' location repeats the trimmed text (as it always did).
        "location",
        lambda: arguments.government_statistics(" Kraków ", "wages"),
        LOCATION_HELP + "podano 'Kraków'.",
    ),
    (
        "location not text",
        lambda: arguments.government_statistics(7, "wages"),
        LOCATION_HELP + "podano 7.",
    ),
    (
        "dataset",
        lambda: arguments.government_statistics("polska", "prices"),
        "dataset musi być jedną z wartości dwellings_quarterly, dwellings_monthly, "
        "average_area, demography, population, unemployment, wages, nbp_prices, podano "
        "'prices'.",
    ),
    (
        "periods",
        lambda: arguments.government_statistics("polska", "wages", periods=True),
        "periods musi być liczbą całkowitą z zakresu 1–1000 (liczba ostatnich okresów), "
        "podano True.",
    ),
]


@pytest.mark.parametrize(("parameter", "call", "message"), REFUSALS, ids=[r[0] for r in REFUSALS])
def test_a_refusal_names_the_parameter_and_what_to_give(
    parameter: str, call: Any, message: str
) -> None:
    with pytest.raises(InvalidInputError) as caught:
        call()

    assert str(caught.value) == message
    assert not isinstance(caught.value, InvalidValueError)  # worded for the caller
    assert isinstance(caught.value.__cause__, InvalidValueError)  # the domain's refusal


def test_every_value_of_the_domain_has_a_parameter() -> None:
    assert set(arguments.PARAMETERS) == set(ValueName)


REFUSED: list[Callable[[], object]] = [
    lambda: CitySlug("X"),
    lambda: InvestmentSlug("X"),
    lambda: LocationSlug("X"),
    lambda: OfferId(0),
    lambda: AmountPln(-1),
    lambda: AreaM2(-1),
    lambda: PageNumber(0),
    lambda: PageSize(7),
    lambda: OffersLimit(-1),
    lambda: OfferSort.parse("x"),
    lambda: Dataset.parse("x"),
]


@pytest.mark.parametrize("make", REFUSED)
def test_every_refusal_of_the_domain_can_be_worded(make: Callable[[], object]) -> None:
    """Values made directly (not through a parameter) are worded too: no ``KeyError``."""
    with pytest.raises(InvalidValueError) as caught:
        make()

    assert arguments.explained(caught.value).endswith(f"{caught.value.given!r}.")


# --- what is taken --------------------------------------------------------------------------------


def test_the_search_with_its_defaults() -> None:
    criteria = arguments.offer_search(" warszawa ")

    assert (criteria.city.value, criteria.page.value, criteria.per_page.value) == (
        "warszawa",
        1,
        10,
    )
    assert (criteria.price, criteria.area, criteria.sort) == (None, None, None)


def test_the_other_operations_arguments() -> None:
    assert arguments.location_query("  Kraków ").text == "Kraków"
    assert arguments.offer(2377, " smolna ") == (
        OfferId(2377),
        InvestmentSlug("smolna"),
    )
    assert arguments.investment("smolna", include_history=True, limit=2) == (
        InvestmentSlug("smolna"),
        True,
        OffersLimit(2),
    )
    found = arguments.government_statistics(" Warszawa ", " wages ", periods=3)
    assert (found.location.value, found.dataset, found.periods.value) == (
        "warszawa",
        Dataset.WAGES,
        3,
    )


@pytest.mark.parametrize(
    ("given", "first"),
    [
        ({"city": "X", "price_min": -1, "sort": "x", "page": 0, "per_page": 7}, "city"),
        ({"price_min": -1, "area_min": -1, "sort": "x", "page": 0, "per_page": 7}, "price_min"),
        ({"price_max": 1, "price_min": 2, "area_min": -1}, "price_min (2)"),
        ({"area_max": -1, "sort": "x", "page": 0, "per_page": 7}, "area_max"),
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
        arguments.offer_search(city, **given)


@pytest.mark.parametrize(
    ("call", "first"),
    [
        (lambda: arguments.offer(0, "SMOLNA"), "offer_id"),
        (lambda: arguments.investment("Smolna", include_history="x", limit=-1), "investment_"),
        (lambda: arguments.investment("smolna", include_history="x", limit=-1), "include_"),
        (lambda: arguments.government_statistics("Kraków", "x", periods=0), "location"),
        (lambda: arguments.government_statistics("polska", "x", periods=0), "dataset"),
    ],
)
def test_the_other_operations_are_checked_in_order(call: Any, first: str) -> None:
    with pytest.raises(InvalidInputError, match=f"^{first}"):
        call()
