"""Contract of ``deweloperuch_mcp.api.dto.investment_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto import investment_dto
from support.builders.investments import sale
from support.providers.samples import body


def test_investment_sample_keeps_values_as_sent() -> None:
    parsed = investment_dto.InvestmentDto.model_validate(body("api.map_inv_visible"))

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


@pytest.mark.parametrize("value", ["994012", 994012, 994012.5, "-0.77", "1e3", "", None])
def test_numbers_may_come_as_numbers_or_strings(value: object) -> None:
    parsed = investment_dto.InvestmentSaleDto.model_validate(sale(amount=value))

    assert parsed.amount == value  # kept as sent; the domain normalizes


@pytest.mark.parametrize(
    "value", ["abc", "1,5", "nan", "inf", "1_000", "1e999", "-1e999", True, [1]]
)
def test_numbers_refuse_what_is_not_a_number(value: object) -> None:
    with pytest.raises(ValidationError):
        investment_dto.InvestmentSaleDto.model_validate(sale(amount=value))


@pytest.mark.parametrize(
    "value", ["2026-10-03", "2025-02-25T00:00:00.000Z", "2025-02-25T10:00:00+02:00", "", None]
)
def test_dates_may_come_in_several_formats(value: object) -> None:
    parsed = investment_dto.InvestmentSaleDto.model_validate(sale(creation_date=value))

    assert parsed.creation_date == value


@pytest.mark.parametrize("value", ["03.10.2026", "2026-13-01", "yesterday", 20261003])
def test_dates_refuse_unknown_formats(value: object) -> None:
    with pytest.raises(ValidationError):
        investment_dto.InvestmentSaleDto.model_validate(sale(creation_date=value))


def test_ids_given_as_strings_are_accepted() -> None:
    parsed = investment_dto.InvestmentSaleDto.model_validate(sale(sale_id="206087"))

    assert parsed.sale_id == 206087


def test_unknown_fields_are_ignored() -> None:
    parsed = investment_dto.InvestmentSaleDto.model_validate(sale(new_backend_field={"x": 1}))

    assert parsed.sale_id == 206087


@pytest.mark.parametrize("field", ["sale_id", "name", "amount", "size", "status"])
def test_core_offer_fields_are_required(field: str) -> None:
    item = sale()
    del item[field]

    with pytest.raises(ValidationError):
        investment_dto.InvestmentSaleDto.model_validate(item)
