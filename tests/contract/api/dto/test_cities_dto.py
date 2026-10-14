"""Contract of ``deweloperuch_mcp.api.dto.cities_dto`` with the service's real answers (the
samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto import investment_dto, offers_page_dto, sale_events_dto
from deweloperuch_mcp.api.dto.cities_dto import CitiesDto
from deweloperuch_mcp.api.dto.investment_sale_events_dto import InvestmentSaleEventsDto
from support.providers.samples import body, envelope


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("api.cities_q", CitiesDto),
        ("api.map_inv_visible", investment_dto.InvestmentDto),
        ("api.sale_events", sale_events_dto.SaleEventsDto),
        ("api.inv_sale_events", InvestmentSaleEventsDto),
        ("page.offers_list", offers_page_dto.OffersPageDto),
    ],
)
def test_dtos_refuse_trimming_markers(name: str, model: type[Any]) -> None:
    data = envelope(name)
    raw = data["response"] if "response" in data else data["value"]

    with pytest.raises(ValidationError):
        model.model_validate(raw)


def test_cities_sample() -> None:
    parsed = CitiesDto.model_validate(body("api.cities_q"))

    assert parsed.cities == ["Kraków", "Krakowiany", "Krakulice"]
    assert [(m.city, m.city_slug, m.offerCount) for m in parsed.cityMappings] == [
        ("Kraków", "krakow", 8082),
        ("Krakowiany", "krakowiany", 0),
        ("Krakulice", "krakulice", 0),
    ]
    assert parsed.hasMore is False
    assert parsed.total == 4
    assert parsed.page == 1


def test_dtos_are_immutable() -> None:
    parsed = CitiesDto.model_validate(body("api.cities_q"))

    with pytest.raises(ValidationError):
        parsed.total = 5
