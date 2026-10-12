"""The domain's rules (D3, D4, D13), on domain objects: value objects and their messages,
search criteria, offers and their price history, investments, and the cut of every result.
Plain Python, no I/O; where realistic data helps, it comes from the samples through the
infrastructure's mappers (tests/test_mappers.py checks those).
"""

import dataclasses
import datetime as dt
import re
from typing import Any

import pytest

from deweloperuch_mcp.domain.errors import (
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
from deweloperuch_mcp.domain.investments import Investment, OfferDetail
from deweloperuch_mcp.domain.locations import Location, LocationMatches, LocationSearchResult
from deweloperuch_mcp.domain.offers import (
    Developer,
    InvestmentRef,
    ListedOffer,
    Offer,
    OfferSearchCriteria,
    OfferSearchPage,
    PriceEvent,
    PriceHistory,
)
from deweloperuch_mcp.domain.values import (
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
    flag,
)
from deweloperuch_mcp.infrastructure.deweloperuch import dto, mappers
from discovery_samples import body


def smolna(**changes: Any) -> Investment:
    data = body("api.map_inv_visible")
    data.update(changes)
    return mappers.investment(dto.InvestmentDto.model_validate(data))


def offer(offer_id: int, status: str = "active", price: float | None = 1.0) -> Offer:
    return Offer(offer_id=offer_id, name=f"M{offer_id}", status=status, price=price, area_m2=50.0)


# --- value objects: what they take, and how they refuse -------------------------------------------


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
            OneOf(("price_asc", "price_desc")),
            "amount",
        ),
        (lambda: OffersLimit.parse(-1), ValueName.OFFERS_LIMIT, WholeNumber(0, 100_000), -1),
        (lambda: LocationQuery.parse(" k "), ValueName.QUERY, TextLength(2, 100), " k "),
        (lambda: flag(ValueName.HISTORY, "yes"), ValueName.HISTORY, TrueOrFalse(), "yes"),
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
    parameters of the CLI and the MCP server are the application's (tests/test_arguments.py)."""
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
    assert flag(ValueName.HISTORY, True) is True
    with pytest.raises(InvalidValueError):
        flag(ValueName.HISTORY, 1)


# --- ranges: open ends have no bound --------------------------------------------------------------


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
    """How the service is told about an open end (the UI's sentinels) is the
    infrastructure's business (tests/test_params.py), not a value of the domain."""
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


# --- offers and their price history ---------------------------------------------------------------


def test_price_per_m2_is_derived_and_rounded() -> None:
    assert dataclasses.replace(offer(1), price=994012.0, area_m2=55.25).price_per_m2 == 17991.17
    assert dataclasses.replace(offer(1), area_m2=0.0).price_per_m2 is None
    assert dataclasses.replace(offer(1), price=None).price_per_m2 is None


def test_events_are_attached_to_the_history_oldest_first() -> None:
    events = [
        PriceEvent(date=dt.date(2025, 2, 25), kind="offer", price=1.0),
        PriceEvent(date=dt.date(2026, 10, 3), kind="restored", price=2.0),
    ]

    with_events = offer(1).with_price_events(events)

    assert offer(1).history.events is None
    assert with_events.history.events == tuple(events)
    with pytest.raises(ValueError, match="kolejności dat"):
        offer(1).with_price_events(reversed(events))


def test_events_without_a_date_come_first() -> None:
    first = PriceEvent(date=None, kind="offer", price=None)
    later = PriceEvent(date=dt.date(2025, 1, 1), kind="offer", price=None)

    assert PriceHistory(events=(first, later)).events == (first, later)
    with pytest.raises(ValueError):
        PriceHistory(events=(later, first))


# --- investments ----------------------------------------------------------------------------------


def test_active_offers_come_first_then_the_rest_in_service_order() -> None:
    investment = smolna()
    mixed = dataclasses.replace(
        investment,
        offers=(offer(2377, "archived"), offer(206087), offer(2386, "archived"), offer(1)),
    )

    listing = mixed.listing()

    assert [(o.offer_id, o.status) for o in listing.offers] == [
        (206087, "active"),
        (1, "active"),
        (2377, "archived"),
        (2386, "archived"),
    ]
    assert listing.omitted == 0


@pytest.mark.parametrize(("limit", "returned", "omitted"), [(None, 3, 0), (2, 2, 1), (0, 0, 3)])
def test_a_limit_says_what_was_omitted(limit: int | None, returned: int, omitted: int) -> None:
    listing = smolna().listing(OffersLimit.parse(limit))

    assert (len(listing.offers), listing.omitted) == (returned, omitted)


def test_histories_are_attached_to_the_offers_kept() -> None:
    events = {206087: (PriceEvent(date=dt.date(2026, 10, 3), kind="offer", price=1679796.0),)}

    listing = smolna().listing(OffersLimit(2)).with_price_events(events)

    first, second = listing.offers
    assert first.history.events == events[206087]
    assert second.history.events == ()  # no entry: no events, not "unknown"


def test_averages_are_those_of_the_active_offers() -> None:
    """In the sample avg_* equal the mean of the active offers (3 of 16, all in the sample)."""
    investment = smolna()
    active = [o for o in investment.offers if o.active]

    assert len(active) == investment.offers_active == 3
    assert investment.avg_price == pytest.approx(sum(o.price or 0 for o in active) / 3)
    assert investment.avg_area_m2 == pytest.approx(
        sum(o.area_m2 or 0 for o in active) / 3, abs=0.01
    )
    assert investment.avg_price_per_m2 == 24487.63


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


def test_an_offer_detail_belongs_to_its_investment() -> None:
    investment = smolna()

    OfferDetail(offer=offer(2377), investment=investment)
    with pytest.raises(ValueError, match="nie należy"):
        OfferDetail(offer=offer(999), investment=investment)


# --- D4: the cut of an offers search --------------------------------------------------------------


def search_page(total: int, page: int = 1, per_page: int = 10, items: int = 3) -> OfferSearchPage:
    ref = InvestmentRef(
        investment_slug="x",
        name="X",
        city=None,
        city_slug=None,
        developer=Developer(developer_slug="d", name="D"),
    )
    listed = tuple(ListedOffer(offer=offer(index), investment=ref) for index in range(items))
    return OfferSearchPage(items=listed, total=total, page=page, per_page=per_page)


@pytest.mark.parametrize(
    ("total", "per_page", "pages", "truncated"),
    [
        (13324, 100, 20, True),
        (1192, 50, 20, True),
        (2000, 100, 20, False),
        (2001, 100, 20, True),
        (120, 10, 12, False),
        (3, 10, 1, False),
    ],
)
def test_a_search_says_how_much_can_be_browsed(
    total: int, per_page: int, pages: int, truncated: bool
) -> None:
    result = search_page(total, per_page=per_page)

    assert (result.total, result.returned, result.per_page) == (total, 3, per_page)
    assert (result.pages_available, result.truncated) == (pages, truncated)
    assert result.browsable == 20 * per_page


def test_a_search_without_offers_has_no_pages() -> None:
    result = search_page(0, items=0)

    assert (result.total, result.returned, result.pages_available) == (0, 0, 0)
    assert not result.truncated


def test_an_empty_page_past_the_last_one_knows_the_pages_that_exist() -> None:
    result = search_page(30, page=9, items=0)

    assert (result.returned, result.pages_available, result.browsable) == (0, 3, 200)


def test_no_pages_without_a_page_size() -> None:
    assert search_page(30, per_page=0).pages_available == 0


# --- D4: the cut of a location search -------------------------------------------------------------


def place(name: str) -> Location:
    return Location.city_of(name=name, city_slug=name.lower(), offer_count=1)


def test_locations_cities_first_with_a_total() -> None:
    result = LocationSearchResult.of(
        LocationQuery("krak"),
        LocationMatches((place("Kraków"),)),
        LocationMatches((place("Mokotów"),)),
    )

    assert [item.name for item in result.items] == ["Kraków", "Mokotów"]
    assert (result.total, result.returned, result.truncated, result.hint) == (2, 2, False, None)


@pytest.mark.parametrize(("cities_more", "places_more"), [(True, False), (False, True)])
def test_locations_that_may_have_more_have_no_total(cities_more: bool, places_more: bool) -> None:
    result = LocationSearchResult.of(
        LocationQuery("krak"),
        LocationMatches((place("Kraków"),), more=cities_more),
        LocationMatches((), more=places_more),
    )

    assert (result.total, result.returned, result.truncated) == (None, 1, True)
    assert result.hint == (
        "Pasujących lokalizacji może być więcej: doprecyzuj nazwę (np. dodaj miasto)."
    )


def test_no_locations_say_what_to_try() -> None:
    result = LocationSearchResult.of(
        LocationQuery("xyzzy"), LocationMatches(()), LocationMatches(())
    )

    assert (result.total, result.returned, result.truncated) == (0, 0, False)
    assert result.hint == (
        "Nic nie pasuje do 'xyzzy'. Sprawdź pisownię (z polskimi znakami) albo podaj początek "
        "nazwy miasta, dzielnicy lub ulicy."
    )


@pytest.mark.parametrize(
    ("kind", "district", "street", "name"),
    [
        ("district", "Mokotów", None, "Mokotów"),
        ("street", "Mokotów", "Puławska", "Puławska"),
        ("estate", "Mokotów", None, "Mokotów"),
        ("estate", None, None, "Warszawa"),
    ],
)
def test_a_place_is_named_after_what_it_is(
    kind: str, district: str | None, street: str | None, name: str
) -> None:
    located = Location.place(
        kind=kind,
        city="Warszawa",
        city_slug="warszawa",
        district=district,
        street=street,
        lat=None,
        lng=None,
        offer_count=None,
    )

    assert (located.kind, located.name) == (kind, name)


# --- names (D3) and immutability ------------------------------------------------------------------

BACKEND_NAME = re.compile(r"^(invest|sale)(_|$)|sale|amount|size|sqm|^data$")
DOMAIN_TYPES = (
    Location,
    LocationSearchResult,
    Developer,
    PriceEvent,
    PriceHistory,
    Offer,
    InvestmentRef,
    ListedOffer,
    OfferSearchCriteria,
    OfferSearchPage,
    Investment,
    OfferDetail,
)


@pytest.mark.parametrize("kind", DOMAIN_TYPES)
def test_domain_names_are_not_the_backend_ones(kind: type[Any]) -> None:
    names = {field.name for field in dataclasses.fields(kind)}
    names |= {name for name in vars(kind) if not name.startswith("_")}

    assert not {name for name in names if BACKEND_NAME.search(name)}


def test_domain_objects_are_immutable() -> None:
    investment = smolna()

    with pytest.raises(dataclasses.FrozenInstanceError):
        investment.name = "x"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        investment.offers[0].history.events = ()  # type: ignore[misc]
