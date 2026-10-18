"""Tests of ``deweloperuch_mcp.usecases.estimate_property_value``."""

from typing import Any

import pytest

from deweloperuch_mcp.models.errors import InvalidInputError, NotFoundError, ServiceError
from deweloperuch_mcp.models.valuation import (
    AddressText,
    ComparablesLimit,
    ComparableTransaction,
    Coordinates,
    PricePerM2Stats,
    Valuation,
    ValuationSubject,
    ValuedArea,
)
from deweloperuch_mcp.usecases.estimate_property_value import (
    EstimatePropertyValue,
    EstimatePropertyValueRequest,
    EstimatePropertyValueResult,
)
from support.builders.valuation import (
    AT_THE_WIDEST_RADIUS,
    CISNA_CAVEAT,
    CISNA_SUBJECT,
    SUBJECT,
    api_sample,
    at_the_widest_radius,
    comparable,
    mapped,
)
from support.fakes.valuation import FakeValuationSource
from support.providers.routes.valuation import cisna

COORDINATES = (
    "(stopnie; tylko punkty w Polsce, współrzędne ulicy lub dzielnicy podaje search_locations)"
)


NO_ESTIMATE = "Serwis nie podał wyceny dla tego miejsca; w promieniu może nie być transakcji."
FRACTIONAL_AREA = "Serwis może nie uwzględnić części ułamkowej powierzchni w wycenie."


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
    """9 transactions from 200 m, below the widest radius of 1000 m: no caveat."""
    request = EstimatePropertyValueRequest(subject=SUBJECT)
    found = EstimatePropertyValue(FakeValuationSource(mapped(api_sample()))).execute(request)

    assert found.listing.returned == 3 and found.hint is None
    assert found.caveat() is None


@pytest.mark.parametrize("area", [41.37, 48.5, 41.99])
def test_fractional_areas_carry_a_caution_with_the_service_estimate(area: float) -> None:
    request = EstimatePropertyValueRequest.parse(lat=50.10841762, lng=20.04339151, area_m2=area)
    source = FakeValuationSource(
        Valuation(
            subject=request.subject,
            estimated_value=558_666,
            price_per_m2=13_626,
            comparables=tuple(comparable(100, str(n)) for n in range(11)),
        )
    )

    found = EstimatePropertyValue(source).execute(request)

    assert source.asked[0].area.value == area
    assert found.listing.valuation.subject.area.value == area
    assert found.listing.valuation.estimated_value == 558_666
    assert found.listing.valuation.price_per_m2 == 13_626
    assert found.listing.total == 11
    assert found.hint == FRACTIONAL_AREA


@pytest.mark.parametrize(
    ("estimated_value", "limit", "guidance"),
    [
        (None, None, NO_ESTIMATE),
        (None, 1, NO_ESTIMATE),
        (
            558_666,
            1,
            "Pokazano 1 najbliższą z 3 transakcji porównawczych; więcej pokaże większy limit.",
        ),
    ],
)
def test_fractional_area_caution_keeps_existing_guidance(
    estimated_value: float | None, limit: int | None, guidance: str
) -> None:
    """The statistics count 9 transactions, as in the sample (3 of them given): an
    estimate that is not of low confidence, so no caveat comes first."""
    request = EstimatePropertyValueRequest.parse(lat=52, lng=21, area_m2=41.37, limit=limit)
    source = FakeValuationSource(
        Valuation(
            subject=request.subject,
            estimated_value=estimated_value,
            stats=PricePerM2Stats(count=9),
            comparables=tuple(comparable(100, str(n)) for n in range(3)),
        )
    )

    found = EstimatePropertyValue(source).execute(request)

    assert found.hint == f"{guidance} {FRACTIONAL_AREA}"


@pytest.mark.parametrize(
    ("limit", "guidance"),
    [
        (None, ""),
        (1, "Pokazano 1 najbliższą z 2 transakcji porównawczych; więcej pokaże większy limit. "),
    ],
)
def test_the_caveat_then_the_comparables_left_out_then_the_cautions(
    limit: int | None, guidance: str
) -> None:
    """Cisna asked with a fractional area: the caveat of the few transactions first, the
    comparables left out, then the caution about the area."""
    request = EstimatePropertyValueRequest.parse(
        lat=49.2167, lng=22.3333, area_m2=49.5, limit=limit
    )
    source = FakeValuationSource(mapped(cisna(), request.subject))

    found = EstimatePropertyValue(source).execute(request)

    assert found.listing.valuation.low_confidence is True
    assert found.valuation_hint == FRACTIONAL_AREA
    assert found.hint == f"{CISNA_CAVEAT} {guidance}{FRACTIONAL_AREA}"


def test_an_estimate_of_low_confidence_says_what_it_rests_on() -> None:
    """Cisna: 2 transactions from the widest radius; the hint is the caveat."""
    source = FakeValuationSource(mapped(cisna(), CISNA_SUBJECT))

    found = EstimatePropertyValue(source).execute(
        EstimatePropertyValueRequest(subject=CISNA_SUBJECT)
    )

    assert found.caveat() == CISNA_CAVEAT
    assert found.hint == CISNA_CAVEAT


def test_the_caveat_comes_before_the_comparables_left_out() -> None:
    source = FakeValuationSource(mapped(cisna(), CISNA_SUBJECT))
    request = EstimatePropertyValueRequest(subject=CISNA_SUBJECT, limit=ComparablesLimit(1))

    found = EstimatePropertyValue(source).execute(request)

    assert found.hint == (
        f"{CISNA_CAVEAT} Pokazano 1 najbliższą z 2 transakcji porównawczych; więcej pokaże "
        "większy limit."
    )


LOW = "to orientacyjna wartość o niskiej wiarygodności. Podaj ją z tym zastrzeżeniem"
COMPARE = "porównaj też z cenami transakcyjnymi miasta (get_transaction_statistics)."


@pytest.mark.parametrize(
    ("count", "radius_m", "months", "said"),
    [
        (
            4,
            200,
            24,
            f"Wycena oparta tylko na 4 transakcjach z promienia 200 m z ostatnich 24 miesięcy: "
            f"{LOW}; {COMPARE}",
        ),
        (
            1,
            200,
            1,
            f"Wycena oparta tylko na 1 transakcji z promienia 200 m z ostatniego miesiąca: "
            f"{LOW}; {COMPARE}",
        ),
        (
            2,
            1000,
            24,
            "Wycena oparta tylko na 2 transakcjach z promienia 1 000 m (największego, jaki "
            f"serwis bierze pod uwagę) z ostatnich 24 miesięcy: {LOW}; {COMPARE}",
        ),
        (3, None, None, f"Wycena oparta tylko na 3 transakcjach: {LOW}; {COMPARE}"),
        (
            0,
            1000,
            24,
            f"Serwis nie podał transakcji, na których oparł wycenę: {LOW}; {COMPARE}",
        ),
        (22, 1000, 24, AT_THE_WIDEST_RADIUS),
        (22, 999, 24, None),
    ],
)
def test_the_caveat_names_the_facts_that_apply(
    count: int, radius_m: int | None, months: int | None, said: str | None
) -> None:
    """[W] the rule of Valuation.low_confidence: fewer than 5 transactions ("tylko"; none at
    all said so, never "na 0 transakcjach"), the widest radius in brackets; the widest
    radius alone is a softer statement, without low confidence. The words agree with the
    numbers; without a lowest and a highest price no spread."""
    valuation = Valuation(
        subject=SUBJECT,
        estimated_value=1.0,
        price_per_m2=1.0,
        radius_m=radius_m,
        radius_ceiling_m=1000,
        period_months=months,
        stats=PricePerM2Stats(count=count),
    )

    assert EstimatePropertyValueResult(listing=valuation.nearest()).caveat() == said


@pytest.mark.parametrize(("low", "high"), [(4040, 4040), (None, 5778), (2302, None)])
def test_without_two_prices_apart_there_is_no_spread(low: float | None, high: float | None) -> None:
    stats = PricePerM2Stats(count=2, min_price_per_m2=low, max_price_per_m2=high)
    valuation = Valuation(subject=SUBJECT, estimated_value=1.0, price_per_m2=1.0, stats=stats)

    caveat = EstimatePropertyValueResult(listing=valuation.nearest()).caveat()

    assert caveat == f"Wycena oparta tylko na 2 transakcjach: {LOW}; {COMPARE}"


def test_22_transactions_at_the_widest_radius_are_no_low_confidence() -> None:
    """A rule test on the sample edited by hand (at_the_widest_radius): the hint has the
    softer statement, then the comparables left out, and no word of low confidence."""
    source = FakeValuationSource(mapped(at_the_widest_radius(22)))
    request = EstimatePropertyValueRequest(subject=SUBJECT, limit=ComparablesLimit(10))

    found = EstimatePropertyValue(source).execute(request)

    assert found.listing.valuation.low_confidence is False
    assert found.hint == (
        f"{AT_THE_WIDEST_RADIUS} Pokazano 10 najbliższych z 22 transakcji porównawczych; "
        "więcej pokaże większy limit."
    )
    assert "wiarygodności" not in (found.hint or "")


@pytest.mark.parametrize(
    ("comparables", "radius_m"),
    [((), None), ((comparable(100, "a"),), None), ((comparable(100, "a"),), 1000)],
)
def test_a_valuation_without_an_estimate_does_not_guess_why(
    comparables: tuple[ComparableTransaction, ...], radius_m: int | None
) -> None:
    """[H] why the service gives none: the hint names a possibility only, and an estimate
    that is not there gets no caveat (however few transactions, even at the widest
    radius)."""
    listing = Valuation(
        subject=SUBJECT, radius_m=radius_m, radius_ceiling_m=1000, comparables=comparables
    ).nearest()
    result = EstimatePropertyValueResult(listing=listing)

    assert result.hint == NO_ESTIMATE
    assert result.caveat() is None


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
