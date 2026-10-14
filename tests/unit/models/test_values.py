"""Tests of ``deweloperuch_mcp.models.values``."""

from typing import Any

import pytest

from deweloperuch_mcp.models.errors import (
    InvalidInputError,
    InvalidValueError,
    LowNotAboveHigh,
    OneOf,
    SlugText,
    TextLength,
    TrueOrFalse,
    ValueName,
    WholeNumber,
)
from deweloperuch_mcp.models.market_statistics import MarketCriteria
from deweloperuch_mcp.models.offer import InvestmentRef
from deweloperuch_mcp.models.values import (
    AmountPln,
    AreaM2,
    AreaRange,
    CitySlug,
    InvestmentSlug,
    LocationQuery,
    LocationSlug,
    OfferId,
    OffersLimit,
    OfferSort,
    PageNumber,
    PageSize,
    PriceRange,
)
from support.builders.investments import smolna
from support.builders.market import KRAKOW, OFFERS


def test_ranges_keep_their_ends_and_drop_offers_without_the_value() -> None:
    criteria = MarketCriteria(
        city=KRAKOW,
        price=PriceRange.parse(400_000, 700_000),
        area=AreaRange.parse(40, None),
    )

    result = OFFERS.statistics(criteria)

    # 1 (500k, 50), 2 (700k, 70), 3 (600k, 40), 6 (400k, 40); not 7 (no price), 8 (no area)
    assert result.offers == 4
    assert result.price_spread is not None
    assert (result.price_spread.min, result.price_spread.max) == (400_000.0, 700_000.0)


@pytest.mark.parametrize("value", ["warszawa", " polska ", "7-miast", "6-miast-bez-warszawy"])
def test_location_slugs(value: str) -> None:
    assert LocationSlug.parse(value).value == value.strip()


@pytest.mark.parametrize(("value", "slug"), [("Warszawa", "warszawa"), (" POLSKA ", "polska")])
def test_location_slugs_in_capitals(value: str, slug: str) -> None:
    assert LocationSlug.parse(value).value == slug


@pytest.mark.parametrize(
    "value", ["Kraków", "kraków", "", "  ", "a/b", "..", "-x", "a b", 7, None, "x" * 201]
)
def test_anything_else_is_not_a_location(value: object) -> None:
    """The refusal (its text for callers: tests/unit/usecases/)."""
    with pytest.raises(InvalidValueError) as caught:
        LocationSlug.parse(value)

    assert (caught.value.value, caught.value.rule) == (ValueName.STATISTICS_LOCATION, SlugText())


def test_polska_is_the_whole_country() -> None:
    assert LocationSlug("polska").whole_country
    assert not LocationSlug("warszawa").whole_country


@pytest.mark.parametrize(
    ("make", "value", "rule", "given"),
    [
        (lambda: CitySlug.parse(" Kraków "), ValueName.CITY, SlugText(), " Kraków "),
        (lambda: InvestmentSlug.parse("Smolna"), ValueName.INVESTMENT, SlugText(), "Smolna"),
        # The statistics' location repeats the trimmed text.
        (
            lambda: LocationSlug.parse(" Kraków "),
            ValueName.STATISTICS_LOCATION,
            SlugText(),
            "Kraków",
        ),
        (lambda: OfferId.parse(0), ValueName.OFFER, WholeNumber(1, 2**63 - 1), 0),
        (lambda: PageNumber.parse(21), ValueName.PAGE, WholeNumber(1, 20), 21),
        (lambda: PageSize.parse(20), ValueName.PAGE_SIZE, OneOf((10, 50, 100)), 20),
        (
            lambda: OfferSort.parse("amount"),
            ValueName.SORT,
            OneOf(tuple(sort.value for sort in OfferSort)),
            "amount",
        ),
        (lambda: OffersLimit.parse(-1), ValueName.OFFERS_LIMIT, WholeNumber(0, 100_000), -1),
        (lambda: LocationQuery.parse(" k "), ValueName.QUERY, TextLength(2, 100), " k "),
        (
            lambda: TrueOrFalse().check(ValueName.HISTORY, "yes"),
            ValueName.HISTORY,
            TrueOrFalse(),
            "yes",
        ),
        (
            lambda: AmountPln.parse(-1, name=ValueName.PRICE_FROM),
            ValueName.PRICE_FROM,
            WholeNumber(0, 99_999_999, "PLN"),
            -1,
        ),
        (lambda: AreaM2(10_000), ValueName.AREA, WholeNumber(0, 9_999, "m²"), 10_000),
    ],
)
def test_a_refused_value_says_which_value_which_rule_and_what_was_given(
    make: Any, value: ValueName, rule: Any, given: object
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        make()

    assert (caught.value.value, caught.value.rule, caught.value.given) == (value, rule, given)
    assert isinstance(caught.value, InvalidInputError)


def test_the_domain_words_a_refusal_in_its_own_terms() -> None:
    """Neutral text: what the value is in the domain, the rule, what was given. The
    parameters of the CLI and the MCP server are the application's (tests/unit/usecases/)."""
    with pytest.raises(InvalidValueError) as caught:
        AmountPln.parse(-1, name=ValueName.PRICE_FROM)
    assert str(caught.value) == (
        "cena od: oczekiwano liczby całkowitej z zakresu 0–99999999 PLN, podano -1."
    )
    with pytest.raises(InvalidValueError) as order:
        PriceRange.parse(7, 5)
    assert str(order.value) == (
        "zakres cen: początek (7) jest większy niż koniec (5), podano (7, 5)."
    )


@pytest.mark.parametrize(
    ("parse", "value", "expected"),
    [
        (CitySlug.parse, " warszawa ", "warszawa"),
        (CitySlug.parse, "polska", "polska"),
        (InvestmentSlug.parse, "nowy-targowek-vi", "nowy-targowek-vi"),
        (LocationSlug.parse, " 6-miast-bez-warszawy ", "6-miast-bez-warszawy"),
        (LocationQuery.parse, "  Kraków ", "Kraków"),
    ],
)
def test_text_values_are_trimmed(parse: Any, value: str, expected: str) -> None:
    assert str(parse(value)) == expected


@pytest.mark.parametrize(
    "value", ["", " ", "Kraków", "KRAKÓW", "a/b", "warszawa/../x", "..", "-x", "x" * 201, None, 7]
)
def test_slugs_refuse_anything_that_could_move_a_path(value: object) -> None:
    for kind in (CitySlug, InvestmentSlug, LocationSlug):
        with pytest.raises(InvalidValueError):
            kind.parse(value)


def test_only_the_statistics_location_is_lowercased() -> None:
    """Models write ``Warszawa``; the statistics take it as ``warszawa`` (Polish letters
    are not replaced). Offers and investments keep refusing capitals."""
    assert LocationSlug.parse(" KRAKOW ") == LocationSlug("krakow")
    assert LocationSlug.parse("Bielsko-Biala").value == "bielsko-biala"
    for kind in (CitySlug, InvestmentSlug):
        with pytest.raises(InvalidValueError):
            kind.parse("KRAKOW")
    with pytest.raises(InvalidValueError):
        LocationSlug("Warszawa")  # made directly: already a slug or nothing


def test_slugs_are_checked_when_made_too() -> None:
    with pytest.raises(InvalidValueError) as caught:
        CitySlug("Kraków")
    assert caught.value.value is ValueName.CITY
    assert CitySlug("polska").whole_country and LocationSlug("polska").whole_country
    assert not CitySlug("warszawa").whole_country


@pytest.mark.parametrize("value", [True, 1.0, "2", None, 0, 21])
def test_pages_are_whole_numbers_within_the_browsable_ones(value: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        PageNumber.parse(value)
    assert caught.value.value is ValueName.PAGE


@pytest.mark.parametrize("value", [True, 10.0, "10", 25, 500])
def test_page_sizes_are_the_service_ones(value: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        PageSize.parse(value)
    assert caught.value.value is ValueName.PAGE_SIZE


def test_sorts() -> None:
    assert OfferSort.parse(None) is None
    assert OfferSort.parse("price_desc") is OfferSort.PRICE_DESC
    for value in ("", " price_asc", ["price_asc"], "PRICE_ASC"):
        with pytest.raises(InvalidValueError):
            OfferSort.parse(value)


def test_include_history_is_a_flag() -> None:
    assert TrueOrFalse().check(ValueName.HISTORY, True) is True
    with pytest.raises(InvalidValueError):
        TrueOrFalse().check(ValueName.HISTORY, 1)


@pytest.mark.parametrize(
    ("low", "high", "ends"),
    [
        (None, 500_000, (None, 500_000)),
        (500_000, None, (500_000, None)),
        (0, 0, (0, 0)),
        (99_999_999, 99_999_999, (99_999_999, 99_999_999)),
    ],
)
def test_price_ranges(low: int | None, high: int | None, ends: tuple[int | None, ...]) -> None:
    price = PriceRange.parse(low, high)

    assert price is not None
    assert tuple(None if end is None else end.value for end in (price.low, price.high)) == ends


def test_an_open_end_has_no_bound_in_the_domain() -> None:
    """How the service is told about an open end (the UI's sentinels) is the api's business
    (tests/unit/api/queries/test_offers_query.py), not a value of the domain."""
    area = AreaRange.parse(40, None)
    price = PriceRange.parse(None, 1)

    assert area is not None and (area.low, area.high) == (AreaM2(40), None)
    assert price is not None and price.low is None


def test_no_range_without_either_end() -> None:
    assert PriceRange.parse(None, None) is None
    assert AreaRange.parse(None, None) is None


@pytest.mark.parametrize(
    ("kind", "low", "high", "value", "rule"),
    [
        (PriceRange, 7, 5, ValueName.PRICE_RANGE, LowNotAboveHigh(7, 5)),
        (AreaRange, 60, 40, ValueName.AREA_RANGE, LowNotAboveHigh(60, 40)),
        (PriceRange, -1, None, ValueName.PRICE_FROM, WholeNumber(0, 99_999_999, "PLN")),
        (PriceRange, None, 10**8, ValueName.PRICE_TO, WholeNumber(0, 99_999_999, "PLN")),
        (AreaRange, 40.5, None, ValueName.AREA_FROM, WholeNumber(0, 9_999, "m²")),
        (AreaRange, None, "60", ValueName.AREA_TO, WholeNumber(0, 9_999, "m²")),
        (PriceRange, -1, -2, ValueName.PRICE_FROM, WholeNumber(0, 99_999_999, "PLN")),
    ],
)
def test_ranges_say_which_end_is_wrong(
    kind: Any, low: object, high: object, value: ValueName, rule: Any
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        kind.parse(low, high)

    assert (caught.value.value, caught.value.rule) == (value, rule)


def test_the_limits_are_the_largest_values_accepted() -> None:
    assert (AmountPln.MAX, AreaM2.MAX) == (99_999_999, 9_999)
    AmountPln(99_999_999)
    with pytest.raises(InvalidValueError):
        AmountPln(100_000_000)


def test_an_offer_is_found_in_its_investment() -> None:
    investment = smolna()

    found = investment.find_offer(OfferId(2377))

    assert found is not None and found.name == "C224"
    assert investment.find_offer(OfferId(999)) is None
    assert investment.ref == InvestmentRef(
        investment_slug="smolna",
        name="Smolna",
        city="Sopot",
        city_slug="sopot",
        developer=investment.developer,
    )
