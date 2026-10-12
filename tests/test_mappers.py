"""DTO -> domain (infrastructure ``mappers``): normalized numbers, dates and empty values,
domain names (D3). No I/O; the DTOs come from the samples in docs/discovery/samples/.

The rules the domain applies to what the mappers build (price per m², the order of an
investment's offers, D4) are in tests/test_domain.py; the views the CLI and the MCP
server show are pinned by the goldens (tests/golden/).
"""

import datetime as dt

import pytest

from deweloperuch_mcp import identity
from deweloperuch_mcp.domain.locations import Location
from deweloperuch_mcp.domain.offers import (
    Developer,
    InvestmentRef,
    ListedOffer,
    Offer,
    PriceChange,
    PriceEvent,
    PriceHistory,
)
from deweloperuch_mcp.infrastructure.deweloperuch import dto, mappers
from deweloperuch_mcp.infrastructure.deweloperuch.links import ServicePageLinks
from discovery_samples import body

PAGES = identity.BASE_URL + "/ceny-ofertowe"
SMOLNA = PAGES + "/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna"
DEVELOPER = PAGES + "/sopot/deweloperzy/invest-komfort-spolka-akcyjna"
LINKS = ServicePageLinks()


def investment_dto(**changes: object) -> dto.InvestmentDto:
    data = body("api.map_inv_visible")
    data.update(changes)
    return dto.InvestmentDto.model_validate(data)


def event(
    event_id: int, kind: str, amount: int | float | str | None, when: str
) -> dto.SaleEventDto:
    return dto.SaleEventDto(
        sale_event_id=event_id, event_type=kind, amount=amount, event_date=when, source=""
    )


# --- values ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("994012", 994012.0),
        (994012, 994012.0),
        ("55.25", 55.25),
        (" -0.6 ", -0.6),
        ("-10795", -10795.0),
        ("", None),
        ("  ", None),
        (None, None),
    ],
)
def test_number(value: int | float | str | None, expected: float | None) -> None:
    assert mappers.number(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-03", dt.date(2026, 10, 3)),
        ("2025-02-25T00:00:00.000Z", dt.date(2025, 2, 25)),
        # A zone other than UTC: the date of the same moment in UTC.
        ("2025-02-25T01:00:00+02:00", dt.date(2025, 2, 24)),
        ("2025-02-25T12:30:00", dt.date(2025, 2, 25)),
        ("", None),
        (None, None),
    ],
)
def test_day(value: str | None, expected: dt.date | None) -> None:
    assert mappers.day(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [("", None), ("   ", None), (None, None), (" Sopot ", "Sopot")]
)
def test_text(value: str | None, expected: str | None) -> None:
    assert mappers.text(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("PRICE_INCREASE", "increase"),
        ("PRICE_DECREASE", "decrease"),
        ("NO_CHANGE", "no_change"),
        ("PRICE_SOMETHING_NEW", "price_something_new"),
        ("", None),
        (None, None),
    ],
)
def test_change_kind(value: str | None, expected: str | None) -> None:
    assert mappers.change_kind(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("OFFER_EVENT", "offer"),
        ("ARCHIVED_EVENT", "archived"),
        ("RESTORED_EVENT", "restored"),
        ("PRICE_CHANGE_EVENT", "price_change"),
    ],
)
def test_event_kind(value: str, expected: str) -> None:
    assert mappers.event_kind(value) == expected


# --- locations ------------------------------------------------------------------------------------


def test_city_location() -> None:
    mapping = dto.CitiesDto.model_validate(body("api.cities_q")).cityMappings[0]

    assert mappers.location_from_city(mapping) == Location(
        kind="city", name="Kraków", city="Kraków", city_slug="krakow", offer_count=8082
    )


def test_district_and_street_locations() -> None:
    district, street = dto.LocationSearchDto.model_validate(body("api.location_search")).suggestions

    assert mappers.location_from_suggestion(district) == Location(
        kind="district",
        name="Mokotów",
        city="Warszawa",
        city_slug="warszawa",
        district="Mokotów",
        lat=52.189818153819054,
        lng=21.05171136865118,
        # [W] count read as the number of offers in the area (no `variant` sent).
        offer_count=1562,
    )
    located = mappers.location_from_suggestion(street)
    assert (located.kind, located.name, located.district, located.street) == (
        "street",
        "Mokotów",
        "Mokotów",
        "Mokotów",
    )


def test_suggestion_of_unknown_kind_keeps_the_kind_and_a_name() -> None:
    suggestion = dto.LocationSuggestionDto(kind="estate", city="Warszawa", citySlug="warszawa")

    located = mappers.location_from_suggestion(suggestion)

    assert (located.kind, located.name) == ("estate", "Warszawa")


def test_coordinates_given_as_strings_become_numbers() -> None:
    suggestion = dto.LocationSuggestionDto(
        kind="street", city="Sopot", citySlug="sopot", street="Morska", lat="54.4", lng=""
    )

    located = mappers.location_from_suggestion(suggestion)

    assert (located.lat, located.lng) == (54.4, None)


# --- offers ---------------------------------------------------------------------------------------


def test_listed_offer_from_the_list_page() -> None:
    item = dto.OffersPageDto.model_validate(body("page.offers_list")).data[0]

    listed = mappers.listed_offer(item)

    assert listed == ListedOffer(
        offer=Offer(
            offer_id=4397,
            name="D1.1.1.4",
            status="active",
            price=994012.0,
            currency="PLN",
            area_m2=55.25,
            history=PriceHistory(
                since_start=PriceChange(pln=-5988.0, percent=-0.6),
                last_change=PriceChange(pln=55250.0, percent=5.89, direction="increase"),
                events_count=12,
                created_on=dt.date(2025, 5, 1),
                last_event_on=dt.date(2026, 10, 3),
                last_changed_on=dt.date(2026, 10, 3),
            ),
        ),
        investment=InvestmentRef(
            investment_slug="nowy-targowek-vi",
            name="Nowy Targówek VI",
            city="Warszawa",
            city_slug="warszawa",
            developer=Developer(developer_slug="atal", name="ATAL S.A."),
        ),
    )
    assert listed.offer.price_per_m2 == 17991.17
    assert listed.offer.history.events is None  # not fetched
    assert LINKS.investment(listed.investment) == (
        PAGES + "/warszawa/deweloperzy/atal/nowy-targowek-vi"
    )


@pytest.mark.parametrize("city_slug", ["", None])
def test_listed_offer_without_its_city_slug_has_no_investment_link(city_slug: str | None) -> None:
    """D12: an address is built from the item's own slugs or not at all, never guessed."""
    item = body("page.offers_list")["data"][0]
    item["invest"]["city_slug"] = city_slug

    listed = mappers.listed_offer(dto.SaleListItemDto.model_validate(item))

    assert listed.investment.city_slug is None
    assert LINKS.investment(listed.investment) is None


@pytest.mark.parametrize(("price", "area"), [("", "55.25"), ("994012", ""), ("994012", "0")])
def test_price_per_m2_needs_price_and_area(price: str, area: str) -> None:
    item = body("page.offers_list")["data"][0]
    item.update(amount=price, size=area)

    listed = mappers.listed_offer(dto.SaleListItemDto.model_validate(item))

    assert listed.offer.price_per_m2 is None


def test_price_events_are_chronological_with_domain_kinds() -> None:
    events = [
        event(510028, "ARCHIVED_EVENT", "1620000", "2025-02-25T00:00:00.000Z"),
        event(841366, "RESTORED_EVENT", "1620175", "2026-10-03T00:00:00.000Z"),
        event(145581, "OFFER_EVENT", "1620000", "2025-02-25T00:00:00.000Z"),
        event(900000, "OFFER_EVENT", "", "2026-10-04"),
        event(950000, "SOMETHING_NEW", 1, ""),
    ]

    assert mappers.price_events(events) == (
        PriceEvent(date=None, kind="something_new", price=1.0),
        PriceEvent(date=dt.date(2025, 2, 25), kind="offer", price=1620000.0),
        PriceEvent(date=dt.date(2025, 2, 25), kind="archived", price=1620000.0),
        PriceEvent(date=dt.date(2026, 10, 3), kind="restored", price=1620175.0),
        PriceEvent(date=dt.date(2026, 10, 4), kind="offer", price=None),
    )


def test_offer_of_an_investment() -> None:
    sale = next(s for s in investment_dto().sale if s.sale_id == 2377)

    offer = mappers.offer(sale)

    assert (offer.offer_id, offer.name, offer.price, offer.area_m2) == (
        2377,
        "C224",
        1620175.0,
        69.5,
    )
    assert offer.history.since_start == PriceChange(pln=175.0, percent=0.01)
    assert offer.history.last_change == PriceChange()  # not given for investments
    assert offer.history.created_on == dt.date(2025, 2, 25)


# --- investments ----------------------------------------------------------------------------------


def test_investment_values_are_normalized() -> None:
    investment = mappers.investment(investment_dto())

    assert (investment.investment_id, investment.investment_slug) == (33, "smolna")
    assert (investment.name, investment.status) == ("Smolna", "active")
    assert (investment.city, investment.city_slug, investment.street) == (
        "Sopot",
        "sopot",
        "Świemirowo",
    )
    assert (investment.lat, investment.lng) == (54.42735985, 18.55839032)
    assert investment.developer == Developer(
        developer_slug="invest-komfort-spolka-akcyjna", name="Invest Komfort Spółka Akcyjna Sp.K."
    )
    assert (investment.offers_active, investment.offers_total) == (3, 16)
    assert [offer.offer_id for offer in investment.offers] == [206087, 2377, 2386]
    assert all(offer.history.events is None for offer in investment.offers)
    assert (LINKS.investment(investment.ref), LINKS.developer(investment.ref)) == (
        SMOLNA,
        DEVELOPER,
    )


def test_investment_without_a_developer_slug_has_no_links() -> None:
    sample = body("api.map_inv_visible")
    sample["developer"]["slug"] = ""

    investment = mappers.investment(dto.InvestmentDto.model_validate(sample))

    assert (LINKS.investment(investment.ref), LINKS.developer(investment.ref)) == (None, None)


def test_empty_street_and_missing_coordinates_become_none() -> None:
    investment = mappers.investment(investment_dto(street="", latitude="", longitude=None))

    assert (investment.street, investment.lat, investment.lng) == (None, None, None)


def test_the_events_of_an_investment_by_offer() -> None:
    events = dto.InvestmentSaleEventsDto.model_validate(body("api.inv_sale_events")).root

    by_offer = {offer_id: mappers.price_events(items) for offer_id, items in events.items()}

    assert by_offer[206087] == (
        PriceEvent(date=dt.date(2026, 10, 3), kind="offer", price=1679796.0),
    )
    assert [e.kind for e in by_offer[2377]] == ["offer", "archived", "restored"]


# --- the search page ------------------------------------------------------------------------------


def test_the_search_page_keeps_the_service_paging() -> None:
    page = mappers.offer_search_page(
        dto.OffersPageDto.model_validate(body("page.offers_list.filtered"))
    )

    assert (page.total, page.page, page.per_page, page.returned) == (1192, 2, 50, 3)
    assert page.items[0].offer.offer_id == 120306
