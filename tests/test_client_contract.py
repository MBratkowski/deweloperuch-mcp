"""Contract tests: the DTOs parse the real samples from docs/discovery/samples/.

The samples are what the service sent (trimmed); if one stops parsing, the backend
contract and the client disagree. Trimming markers are removed first
(tests/discovery_samples.py): the DTOs must not tolerate them.
"""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.infrastructure.deweloperuch import dto
from discovery_samples import body, envelope, untrimmed

# --- the helper -----------------------------------------------------------------------------------


def test_untrimmed_removes_only_the_markers() -> None:
    value = {
        "a": ["x", "... (2 more, 3 total)"],
        "b": {"1": [1, "... (5 more, 6 total)"], "...": "40 more keys"},
        "c": ["... (2 more, 3 total) but not a marker", "text"],
    }

    assert untrimmed(value) == {
        "a": ["x"],
        "b": {"1": [1]},
        "c": ["... (2 more, 3 total) but not a marker", "text"],
    }


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("api.cities_q", dto.CitiesDto),
        ("api.map_inv_visible", dto.InvestmentDto),
        ("api.sale_events", dto.SaleEventsDto),
        ("api.inv_sale_events", dto.InvestmentSaleEventsDto),
        ("page.offers_list", dto.OffersPageDto),
    ],
)
def test_dtos_refuse_trimming_markers(name: str, model: type[Any]) -> None:
    data = envelope(name)
    raw = data["response"] if "response" in data else data["value"]

    with pytest.raises(ValidationError):
        model.model_validate(raw)


# --- locations ------------------------------------------------------------------------------------


def test_cities_sample() -> None:
    parsed = dto.CitiesDto.model_validate(body("api.cities_q"))

    assert parsed.cities == ["Kraków", "Krakowiany", "Krakulice"]
    assert [(m.city, m.city_slug, m.offerCount) for m in parsed.cityMappings] == [
        ("Kraków", "krakow", 8082),
        ("Krakowiany", "krakowiany", 0),
        ("Krakulice", "krakulice", 0),
    ]
    assert parsed.hasMore is False
    assert parsed.total == 4
    assert parsed.page == 1


def test_location_search_sample() -> None:
    parsed = dto.LocationSearchDto.model_validate(body("api.location_search"))

    district, street = parsed.suggestions
    assert (district.kind, district.city, district.citySlug) == ("district", "Warszawa", "warszawa")
    assert (district.district, district.street, district.count) == ("Mokotów", None, 1562)
    assert district.lat == 52.189818153819054
    assert district.lng == 21.05171136865118
    assert (street.kind, street.street, street.district, street.count) == (
        "street",
        "Mokotów",
        "Mokotów",
        191,
    )


def test_city_lookup_sample() -> None:
    parsed = dto.CityLookupDto.model_validate(body("api.city_lookup"))

    assert (parsed.city, parsed.city_slug) == ("Warszawa", "warszawa")


def test_city_districts_sample() -> None:
    parsed = dto.CityDistrictsDto.model_validate(body("api.city_districts"))

    assert [(d.name, d.count) for d in parsed.districts] == [
        ("Białołęka", 2934),
        ("Mokotów", 1562),
        ("Targówek", 1158),
    ]


# --- offers and investments -----------------------------------------------------------------------


def test_investment_sample_keeps_values_as_sent() -> None:
    parsed = dto.InvestmentDto.model_validate(body("api.map_inv_visible"))

    assert (parsed.invest_id, parsed.slug, parsed.name, parsed.status) == (
        33,
        "smolna",
        "Smolna",
        "active",
    )
    assert (parsed.city, parsed.city_slug, parsed.street) == ("Sopot", "sopot", "Świemirowo")
    # 1:1 with the backend: coordinates and offer amounts arrive as strings [P].
    assert parsed.latitude == "54.42735985"
    assert parsed.longitude == "18.55839032"
    assert (parsed.avg_amount, parsed.avg_size, parsed.avg_price_sqm) == (1566392, 63.97, 24487.63)
    assert (parsed.active_offers, parsed.total_offers) == (3, 16)
    assert parsed.developer.slug == "invest-komfort-spolka-akcyjna"
    assert parsed.developer.description == ""
    assert [sale.sale_id for sale in parsed.sale] == [206087, 2377, 2386]
    first = parsed.sale[0]
    assert (first.amount, first.size, first.type, first.status) == ("1679796", "65.9", "", "active")
    assert parsed.sale[2].start_amount_difference == "-10795"
    assert parsed.sale[2].start_amount_difference_percent == "-0.77"
    assert first.creation_date == "2026-10-03"


def test_investment_sale_events_sample_is_keyed_by_offer_id() -> None:
    parsed = dto.InvestmentSaleEventsDto.model_validate(body("api.inv_sale_events"))

    assert len(parsed.root) == 16
    assert 206087 in parsed.root
    events = parsed.root[2377]
    assert [e.event_type for e in events] == ["OFFER_EVENT", "ARCHIVED_EVENT", "RESTORED_EVENT"]
    assert events[0].event_date == "2025-02-25T00:00:00.000Z"
    assert parsed.root[206087][0].event_data == '{"source":"scraper_pr"}'


def test_sale_events_sample() -> None:
    parsed = dto.SaleEventsDto.model_validate(body("api.sale_events"))

    assert parsed.success is True
    assert parsed.saleData is not None
    assert (parsed.saleData.name, parsed.saleData.amount) == ("C224", "1620175")
    assert [e.sale_event_id for e in parsed.events] == [145581, 510028, 841366]
    assert [e.amount for e in parsed.events] == ["1620000", "1620000", "1620175"]
    assert parsed.events[1].source == ""


@pytest.mark.parametrize(
    ("name", "first_offer", "pagination"),
    [
        ("page.offers_list", 4397, (1, 100, 13324, 20)),
        ("page.offers_list.filtered", 120306, (2, 50, 1192, 20)),
    ],
)
def test_offers_page_samples(
    name: str, first_offer: int, pagination: tuple[int, int, int, int]
) -> None:
    parsed = dto.OffersPageDto.model_validate(body(name))

    page = parsed.pagination
    assert (page.page, page.perPage, page.total, page.totalPages) == pagination
    assert len(parsed.data) == 3
    first = parsed.data[0]
    assert first.sale_id == first_offer
    assert first.invest.slug
    assert first.invest.developer.slug
    assert isinstance(first.amount, str)
    assert first.last_event_type in ("PRICE_INCREASE", "PRICE_DECREASE", "NO_CHANGE")


def test_offers_page_sample_fields() -> None:
    first = dto.OffersPageDto.model_validate(body("page.offers_list")).data[0]

    assert (first.name, first.amount, first.size, first.currency) == (
        "D1.1.1.4",
        "994012",
        "55.25",
        "PLN",
    )
    assert (first.start_amount_difference, first.start_amount_difference_percent) == (
        "-5988",
        "-0.6",
    )
    assert (first.last_amount_difference, first.last_amount_difference_percent) == (
        "55250",
        "5.89",
    )
    assert (first.total_events, first.status) == (12, "active")
    assert (first.creation_date, first.last_event_date, first.last_change_event_date) == (
        "2025-05-01",
        "2026-10-03",
        "2026-10-03",
    )
    assert (first.invest.invest_id, first.invest.name, first.invest.city_slug) == (
        54,
        "Nowy Targówek VI",
        "warszawa",
    )
    assert (first.invest.developer.name, first.invest.developer.slug) == ("ATAL S.A.", "atal")


# --- tolerance ------------------------------------------------------------------------------------


def sale(**changes: Any) -> dict[str, Any]:
    item: dict[str, Any] = body("api.map_inv_visible")["sale"][0]
    item.update(changes)
    return item


@pytest.mark.parametrize("value", ["994012", 994012, 994012.5, "-0.77", "1e3", "", None])
def test_numbers_may_come_as_numbers_or_strings(value: object) -> None:
    parsed = dto.InvestmentSaleDto.model_validate(sale(amount=value))

    assert parsed.amount == value  # kept as sent; the domain normalizes


@pytest.mark.parametrize(
    "value", ["abc", "1,5", "nan", "inf", "1_000", "1e999", "-1e999", True, [1]]
)
def test_numbers_refuse_what_is_not_a_number(value: object) -> None:
    with pytest.raises(ValidationError):
        dto.InvestmentSaleDto.model_validate(sale(amount=value))


@pytest.mark.parametrize(
    "value", ["2026-10-03", "2025-02-25T00:00:00.000Z", "2025-02-25T10:00:00+02:00", "", None]
)
def test_dates_may_come_in_several_formats(value: object) -> None:
    parsed = dto.InvestmentSaleDto.model_validate(sale(creation_date=value))

    assert parsed.creation_date == value


@pytest.mark.parametrize("value", ["03.10.2026", "2026-13-01", "yesterday", 20261003])
def test_dates_refuse_unknown_formats(value: object) -> None:
    with pytest.raises(ValidationError):
        dto.InvestmentSaleDto.model_validate(sale(creation_date=value))


def test_ids_given_as_strings_are_accepted() -> None:
    parsed = dto.InvestmentSaleDto.model_validate(sale(sale_id="206087"))

    assert parsed.sale_id == 206087


def test_unknown_fields_are_ignored() -> None:
    parsed = dto.InvestmentSaleDto.model_validate(sale(new_backend_field={"x": 1}))

    assert parsed.sale_id == 206087


@pytest.mark.parametrize("field", ["sale_id", "name", "amount", "size", "status"])
def test_core_offer_fields_are_required(field: str) -> None:
    item = sale()
    del item[field]

    with pytest.raises(ValidationError):
        dto.InvestmentSaleDto.model_validate(item)


def test_dtos_are_immutable() -> None:
    parsed = dto.CityLookupDto.model_validate(body("api.city_lookup"))

    with pytest.raises(ValidationError):
        parsed.city = "Kraków"


def test_iso_dates_in_samples_are_valid_dates() -> None:
    """Every date in the samples is one of the accepted formats (documents [P] formats)."""
    parsed = dto.InvestmentSaleEventsDto.model_validate(body("api.inv_sale_events"))

    dates = {e.event_date for events in parsed.root.values() for e in events}
    assert {d[:10] for d in dates} <= {"2025-02-25", "2026-10-03"}
    assert all(date.fromisoformat(d[:10]) for d in dates)
