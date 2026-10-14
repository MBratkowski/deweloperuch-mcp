"""Tests of ``deweloperuch_mcp.usecases.estimate_property_value``."""

from typing import Any

import pytest

from deweloperuch_mcp.models.errors import InvalidInputError, NotFoundError, ServiceError
from deweloperuch_mcp.models.valuation import (
    AddressText,
    ComparablesLimit,
    ComparableTransaction,
    Coordinates,
    Valuation,
    ValuationSubject,
    ValuedArea,
)
from deweloperuch_mcp.usecases.estimate_property_value import (
    EstimatePropertyValue,
    EstimatePropertyValueRequest,
    EstimatePropertyValueResult,
)
from support.builders.valuation import SUBJECT, api_sample, comparable, mapped
from support.fakes.valuation import FakeValuationSource

COORDINATES = (
    "(stopnie; tylko punkty w Polsce, współrzędne ulicy lub dzielnicy podaje search_locations)"
)


NO_ESTIMATE = "Serwis nie podał wyceny dla tego miejsca; w promieniu może nie być transakcji."


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ({"lat": 60}, f"lat musi być liczbą z zakresu 49–54.9 {COORDINATES}, podano 60."),
        ({"lng": 10.5}, f"lng musi być liczbą z zakresu 14.1–24.2 {COORDINATES}, podano 10.5."),
        ({"area_m2": 5}, "area_m2 musi być liczbą z zakresu 10–500 m², podano 5."),
        (
            {"address": "ab"},
            "address: podaj od 3 do 200 znaków adresu albo pomiń ten parametr, podano 'ab'.",
        ),
        (
            {"limit": -1},
            "limit musi być liczbą całkowitą z zakresu 0–100000 (liczba transakcji "
            "porównawczych w wyniku), podano -1.",
        ),
    ],
)
def test_refusals_name_the_parameter_and_what_to_give(given: dict[str, Any], message: str) -> None:
    values: dict[str, Any] = dict(lat=52.2297, lng=21.0122, area_m2=50)
    values.update(given)

    with pytest.raises(InvalidInputError) as caught:
        EstimatePropertyValueRequest.parse(**values)

    assert str(caught.value) == message


def test_the_parameters_are_checked_in_order() -> None:
    with pytest.raises(InvalidInputError, match="^lat "):
        EstimatePropertyValueRequest.parse(lat=0, lng=0, area_m2=0, address="", limit=-1)
    with pytest.raises(InvalidInputError, match="^area_m2 "):
        EstimatePropertyValueRequest.parse(lat=52, lng=21, area_m2=0, address="ab", limit=-1)
    with pytest.raises(InvalidInputError, match="^limit "):
        EstimatePropertyValueRequest.parse(lat=52, lng=21, area_m2=50, address=None, limit=-1)


def test_the_parameters_as_domain_values() -> None:
    given = EstimatePropertyValueRequest.parse(
        lat=52.2297, lng=21.0122, area_m2=48.5, address=" Widok 24 ", limit=3
    )

    assert given.subject == ValuationSubject(
        Coordinates(52.2297, 21.0122), ValuedArea(48.5), AddressText("Widok 24")
    )
    assert given.limit == ComparablesLimit(3)
    assert EstimatePropertyValueRequest.parse(lat=52, lng=21, area_m2=50).limit is None


def test_one_request_and_the_nearest_comparables() -> None:
    source = FakeValuationSource(mapped(api_sample()))

    request = EstimatePropertyValueRequest(subject=SUBJECT, limit=ComparablesLimit(1))
    found = EstimatePropertyValue(source).execute(request)

    assert source.asked == [SUBJECT]
    assert [c.address for c in found.listing.comparables] == ["Ulica Nowogrodzka 38"]
    assert found.listing.omitted == 2
    assert found.hint == (
        "Pokazano 1 najbliższą z 3 transakcji porównawczych; więcej pokaże większy limit."
    )


@pytest.mark.parametrize(
    ("returned", "total", "said"),
    [
        (0, 1, "Pokazano 0 najbliższych z 1 transakcji porównawczej"),
        (1, 3, "Pokazano 1 najbliższą z 3 transakcji porównawczych"),
        (2, 3, "Pokazano 2 najbliższe z 3 transakcji porównawczych"),
        (4, 9, "Pokazano 4 najbliższe z 9 transakcji porównawczych"),
        (5, 9, "Pokazano 5 najbliższych z 9 transakcji porównawczych"),
        (12, 60, "Pokazano 12 najbliższych z 60 transakcji porównawczych"),
        (22, 60, "Pokazano 22 najbliższe z 60 transakcji porównawczych"),
    ],
)
def test_the_words_agree_with_the_numbers(returned: int, total: int, said: str) -> None:
    valuation = Valuation(
        subject=SUBJECT, comparables=tuple(comparable(n, str(n)) for n in range(total))
    )
    result = EstimatePropertyValueResult(listing=valuation.nearest(ComparablesLimit(returned)))

    assert result.nearest_shown() == said


def test_every_comparable_without_a_limit_and_no_hint() -> None:
    request = EstimatePropertyValueRequest(subject=SUBJECT)
    found = EstimatePropertyValue(FakeValuationSource(mapped(api_sample()))).execute(request)

    assert found.listing.returned == 3 and found.hint is None


@pytest.mark.parametrize("comparables", [(), (comparable(100, "a"),)])
def test_a_valuation_without_an_estimate_does_not_guess_why(
    comparables: tuple[ComparableTransaction, ...],
) -> None:
    """[H] why the service gives none: the hint names a possibility only."""
    listing = Valuation(subject=SUBJECT, comparables=comparables).nearest()

    assert EstimatePropertyValueResult(listing=listing).hint == NO_ESTIMATE


def test_not_found_does_not_guess_why() -> None:
    source = FakeValuationSource(
        NotFoundError("Serwis nie zna żądanych danych (HTTP 404).", detail="x")
    )

    with pytest.raises(NotFoundError) as caught:
        EstimatePropertyValue(source).execute(EstimatePropertyValueRequest(subject=SUBJECT))

    assert str(caught.value) == NO_ESTIMATE
    assert caught.value.detail == "x"


def test_a_service_error_says_what_it_is_about() -> None:
    source = FakeValuationSource(
        ServiceError("Serwis odpowiedział błędem HTTP 500.", 10.0, detail="x")
    )

    with pytest.raises(ServiceError) as caught:
        EstimatePropertyValue(source).execute(EstimatePropertyValueRequest(subject=SUBJECT))

    assert str(caught.value) == "Wycena mieszkania: Serwis odpowiedział błędem HTTP 500."
    assert caught.value.pause_seconds == 10.0
