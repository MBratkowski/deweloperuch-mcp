"""Tests of ``deweloperuch_mcp.api.dto.cities_dto``."""

import pytest

from deweloperuch_mcp.api.dto.cities_dto import CitiesDto
from deweloperuch_mcp.models.location import Location
from support.providers.samples import body


def test_city_location() -> None:
    mapping = CitiesDto.model_validate(body("api.cities_q")).cityMappings[0]

    assert mapping.to_model() == Location(
        kind="city", name="Kraków", city="Kraków", city_slug="krakow", offer_count=8082
    )


@pytest.mark.parametrize("more", [False, True])
def test_cities_say_whether_the_service_has_more(more: bool) -> None:
    # [W] docs/discovery/endpoints.md, /api/cities: `hasMore` read as "more cities match".
    found = CitiesDto.model_validate(dict(body("api.cities_q"), hasMore=more)).to_model()

    assert [city.city_slug for city in found.items] == ["krakow", "krakowiany", "krakulice"]
    assert found.more is more
