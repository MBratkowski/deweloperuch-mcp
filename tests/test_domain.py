"""DTO -> domain: normalized numbers, dates and empty values, domain names (D3). No I/O."""

import datetime as dt
import json
import re
from typing import Any

import pytest
from pydantic import BaseModel

from deweloperuch_mcp.client import dto
from deweloperuch_mcp.domain import normalize
from deweloperuch_mcp.domain.models import (
    Investment,
    Location,
    OfferDetail,
    OfferSearchResult,
    OfferSummary,
    PriceEvent,
)
from discovery_samples import body


def investment_dto(**changes: Any) -> dto.InvestmentDto:
    data = body("api.map_inv_visible")
    data.update(changes)
    return dto.InvestmentDto.model_validate(data)


def events_dto() -> dto.InvestmentSaleEventsDto:
    return dto.InvestmentSaleEventsDto.model_validate(body("api.inv_sale_events"))


def event(
    event_id: int, kind: str, amount: int | float | str | None, when: str
) -> dto.SaleEventDto:
    return dto.SaleEventDto(
        sale_event_id=event_id, event_type=kind, amount=amount, event_date=when, source=""
    )


# --- values ------------------------------------------------------------------------------


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
    assert normalize.number(value) == expected


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
    assert normalize.day(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [("", None), ("   ", None), (None, None), (" Sopot ", "Sopot")]
)
def test_text(value: str | None, expected: str | None) -> None:
    assert normalize.text(value) == expected


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
    assert normalize.change_kind(value) == expected


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
    assert normalize.event_kind(value) == expected


# --- locations ---------------------------------------------------------------------------


def test_city_location() -> None:
    mapping = dto.CitiesDto.model_validate(body("api.cities_q")).cityMappings[0]

    assert normalize.location_from_city(mapping) == Location(
        kind="city", name="Kraków", city="Kraków", city_slug="krakow", offer_count=8082
    )


def test_district_and_street_locations() -> None:
    district, street = dto.LocationSearchDto.model_validate(body("api.location_search")).suggestions

    assert normalize.location_from_suggestion(district) == Location(
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
    located = normalize.location_from_suggestion(street)
    assert (located.kind, located.name, located.district, located.street) == (
        "street",
        "Mokotów",
        "Mokotów",
        "Mokotów",
    )


def test_suggestion_of_unknown_kind_keeps_the_kind_and_a_name() -> None:
    suggestion = dto.LocationSuggestionDto(kind="estate", city="Warszawa", citySlug="warszawa")

    located = normalize.location_from_suggestion(suggestion)

    assert (located.kind, located.name) == ("estate", "Warszawa")


def test_coordinates_given_as_strings_become_numbers() -> None:
    suggestion = dto.LocationSuggestionDto(
        kind="street", city="Sopot", citySlug="sopot", street="Morska", lat="54.4", lng=""
    )

    located = normalize.location_from_suggestion(suggestion)

    assert (located.lat, located.lng) == (54.4, None)


# --- offers --------------------------------------------------------------------------------


def test_offer_summary_from_the_list_page() -> None:
    item = dto.OffersPageDto.model_validate(body("page.offers_list")).data[0]

    summary = normalize.offer_summary(item)

    assert summary == OfferSummary(
        offer_id=4397,
        name="D1.1.1.4",
        status="active",
        price=994012.0,
        currency="PLN",
        area_m2=55.25,
        price_per_m2=17991.17,
        price_change_since_start=-5988.0,
        price_change_since_start_pct=-0.6,
        creation_date=dt.date(2025, 5, 1),
        last_event_date=dt.date(2026, 10, 3),
        last_change_date=dt.date(2026, 10, 3),
        last_price_change=55250.0,
        last_price_change_pct=5.89,
        last_price_change_kind="increase",
        events_count=12,
        investment_slug="nowy-targowek-vi",
        investment_name="Nowy Targówek VI",
        city="Warszawa",
        city_slug="warszawa",
        developer_slug="atal",
        developer_name="ATAL S.A.",
    )


@pytest.mark.parametrize(("price", "area"), [("", "55.25"), ("994012", ""), ("994012", "0")])
def test_price_per_m2_needs_price_and_area(price: str, area: str) -> None:
    item = body("page.offers_list")["data"][0]
    item.update(amount=price, size=area)

    summary = normalize.offer_summary(dto.SaleListItemDto.model_validate(item))

    assert summary.price_per_m2 is None


def test_price_history_is_chronological_with_domain_kinds() -> None:
    events = [
        event(510028, "ARCHIVED_EVENT", "1620000", "2025-02-25T00:00:00.000Z"),
        event(841366, "RESTORED_EVENT", "1620175", "2026-10-03T00:00:00.000Z"),
        event(145581, "OFFER_EVENT", "1620000", "2025-02-25T00:00:00.000Z"),
        event(900000, "OFFER_EVENT", "", "2026-10-04"),
        event(950000, "SOMETHING_NEW", 1, ""),
    ]

    history = normalize.price_history(events)

    assert history == [
        PriceEvent(date=None, kind="something_new", price=1.0),
        PriceEvent(date=dt.date(2025, 2, 25), kind="offer", price=1620000.0),
        PriceEvent(date=dt.date(2025, 2, 25), kind="archived", price=1620000.0),
        PriceEvent(date=dt.date(2026, 10, 3), kind="restored", price=1620175.0),
        PriceEvent(date=dt.date(2026, 10, 4), kind="offer", price=None),
    ]


def test_offer_detail_combines_investment_offer_and_history() -> None:
    investment = investment_dto()
    sale = next(s for s in investment.sale if s.sale_id == 2377)
    events = dto.SaleEventsDto.model_validate(body("api.sale_events")).events

    detail = normalize.offer_detail(investment, sale, events)

    assert isinstance(detail, OfferDetail)
    assert (detail.offer_id, detail.name, detail.price, detail.area_m2) == (
        2377,
        "C224",
        1620175.0,
        69.5,
    )
    assert (detail.price_change_since_start, detail.price_change_since_start_pct) == (175.0, 0.01)
    assert (detail.investment_slug, detail.investment_name, detail.city_slug) == (
        "smolna",
        "Smolna",
        "sopot",
    )
    assert detail.developer.developer_slug == "invest-komfort-spolka-akcyjna"
    assert [e.kind for e in detail.price_history] == ["offer", "archived", "restored"]


# --- investments -------------------------------------------------------------------------


def test_investment_values_are_normalized() -> None:
    investment = normalize.investment(investment_dto())

    assert isinstance(investment, Investment)
    assert (investment.investment_slug, investment.name, investment.status) == (
        "smolna",
        "Smolna",
        "active",
    )
    assert (investment.city, investment.city_slug, investment.street) == (
        "Sopot",
        "sopot",
        "Świemirowo",
    )
    assert (investment.lat, investment.lng) == (54.42735985, 18.55839032)
    assert investment.developer.model_dump() == {
        "developer_slug": "invest-komfort-spolka-akcyjna",
        "name": "Invest Komfort Spółka Akcyjna Sp.K.",
        "website": None,
        "description": None,
    }
    assert (investment.offers_active, investment.offers_total) == (3, 16)
    assert investment.offers_omitted == 0
    assert all(offer.price_history is None for offer in investment.offers)


def test_investment_averages_are_those_of_its_active_offers() -> None:
    """In the sample avg_* equal the mean of the active offers (3 of 16, all in the sample)."""
    investment = normalize.investment(investment_dto())
    active = [offer for offer in investment.offers if offer.status == "active"]

    assert len(active) == investment.offers_active == 3
    assert investment.avg_price == pytest.approx(sum(o.price or 0 for o in active) / 3)
    assert investment.avg_area_m2 == pytest.approx(
        sum(o.area_m2 or 0 for o in active) / 3, abs=0.01
    )
    assert investment.avg_price_per_m2 == 24487.63


def test_empty_street_and_missing_coordinates_become_none() -> None:
    investment = normalize.investment(investment_dto(street="", latitude="", longitude=None))

    assert (investment.street, investment.lat, investment.lng) == (None, None, None)


def test_active_offers_come_first_then_the_rest_in_service_order() -> None:
    data = body("api.map_inv_visible")
    first, second, third = data["sale"]
    data["sale"] = [dict(first, status="archived"), second, dict(third, status="archived")]
    data["sale"].append(dict(first, sale_id=1, status="active"))

    investment = normalize.investment(dto.InvestmentDto.model_validate(data))

    assert [(o.offer_id, o.status) for o in investment.offers] == [
        (2377, "active"),
        (1, "active"),
        (206087, "archived"),
        (2386, "archived"),
    ]


@pytest.mark.parametrize(("limit", "returned", "omitted"), [(None, 3, 0), (2, 2, 1), (0, 0, 3)])
def test_offers_limit_reports_what_was_omitted(
    limit: int | None, returned: int, omitted: int
) -> None:
    investment = normalize.investment(investment_dto(), limit=limit)

    assert len(investment.offers) == returned
    assert investment.offers_omitted == omitted


def test_history_is_attached_to_returned_offers() -> None:
    investment = normalize.investment(investment_dto(), limit=2, history=events_dto().root)

    first, second = investment.offers
    assert first.offer_id == 206087
    assert first.price_history == [
        PriceEvent(date=dt.date(2026, 10, 3), kind="offer", price=1679796.0)
    ]
    assert second.price_history is not None
    assert [e.kind for e in second.price_history] == ["offer", "archived", "restored"]


def test_offer_without_events_gets_an_empty_history() -> None:
    investment = normalize.investment(investment_dto(), history={})

    assert all(offer.price_history == [] for offer in investment.offers)


# --- search results (D4) -----------------------------------------------------------------


def offers_page(total: int, page: int = 1, per_page: int = 10) -> dto.OffersPageDto:
    data = body("page.offers_list")
    data["pagination"] = {"page": page, "perPage": per_page, "total": total, "totalPages": 1}
    return dto.OffersPageDto.model_validate(data)


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
def test_search_result_says_how_much_can_be_browsed(
    total: int, per_page: int, pages: int, truncated: bool
) -> None:
    result = normalize.offer_search_result(offers_page(total, per_page=per_page), max_pages=20)

    assert isinstance(result, OfferSearchResult)
    assert (result.total, result.returned, result.per_page) == (total, 3, per_page)
    assert (result.pages_available, result.truncated) == (pages, truncated)
    assert (result.hint is not None) == truncated
    if truncated:
        assert "Zawęź" in str(result.hint)


def test_search_result_without_offers_suggests_what_to_check() -> None:
    data = {"data": [], "pagination": {"page": 1, "perPage": 10, "total": 0, "totalPages": 0}}

    result = normalize.offer_search_result(dto.OffersPageDto.model_validate(data), max_pages=20)

    assert (result.total, result.returned, result.pages_available) == (0, 0, 0)
    assert result.hint is not None and "search_locations" in result.hint


def test_empty_page_past_the_last_one_says_which_pages_exist() -> None:
    data = {"data": [], "pagination": {"page": 9, "perPage": 10, "total": 30, "totalPages": 3}}

    result = normalize.offer_search_result(dto.OffersPageDto.model_validate(data), max_pages=20)

    assert result.hint is not None and "1–3" in result.hint


# --- names (D3) ----------------------------------------------------------------------------

BACKEND_KEY = re.compile(r"^(invest|sale)(_|$)|sale|amount|size|sqm|^data$")
BACKEND_VALUES = ("PRICE_INCREASE", "OFFER_EVENT", "ARCHIVED_EVENT", "ANNOUCMENT")


def keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for item in value.values() for k in keys(item)}
    if isinstance(value, list):
        return {k for item in value for k in keys(item)}
    return set()


def domain_results() -> list[BaseModel]:
    investment = investment_dto()
    sale = investment.sale[1]
    events = dto.SaleEventsDto.model_validate(body("api.sale_events")).events
    page = dto.OffersPageDto.model_validate(body("page.offers_list"))
    suggestions = dto.LocationSearchDto.model_validate(body("api.location_search")).suggestions
    return [
        normalize.investment(investment, history=events_dto().root),
        normalize.offer_detail(investment, sale, events),
        normalize.offer_search_result(page, max_pages=20),
        *[normalize.location_from_suggestion(s) for s in suggestions],
    ]


def test_domain_output_has_no_backend_names() -> None:
    for result in domain_results():
        dumped = result.model_dump(mode="json")
        backend = {key for key in keys(dumped) if BACKEND_KEY.search(key)}
        assert backend == set(), type(result).__name__
        text = json.dumps(dumped)
        assert not [value for value in BACKEND_VALUES if value in text]


def test_domain_models_are_immutable() -> None:
    investment = normalize.investment(investment_dto())

    with pytest.raises(ValueError, match="frozen"):
        investment.name = "x"
