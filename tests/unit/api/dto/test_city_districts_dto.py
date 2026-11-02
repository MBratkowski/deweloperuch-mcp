"""Tests of ``deweloperuch_mcp.api.dto.city_districts_dto``."""

from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.city_districts_dto import CityDistrictsDto
from deweloperuch_mcp.models.district import District
from support.builders.districts import warszawa_districts, warszawa_districts_body


def test_the_districts_keep_the_services_order() -> None:
    found = CityDistrictsDto.model_validate(warszawa_districts_body()).to_model()

    assert found == warszawa_districts()
    assert found[:2] == (
        District(name="Białołęka", slug="bialoleka"),
        District(name="Praga-Północ", slug="praga-polnoc"),
    )


def test_no_districts() -> None:
    """An empty list: the service lists no district for the city."""
    assert CityDistrictsDto.model_validate({"districts": []}).to_model() == ()


def test_the_count_is_not_needed() -> None:
    """``count`` only orders the list (not an official number): it is never read."""
    rows = [{"name": "Wola", "slug": "wola"}]

    assert CityDistrictsDto.model_validate({"districts": rows}).to_model() == (
        District(name="Wola", slug="wola"),
    )


@pytest.mark.parametrize(
    "slug", ["", "a", "Wola", "praga polnoc", "-wola", "wola-", "praga--polnoc", "x" * 101, 7]
)
def test_a_slug_that_cannot_address_a_list_is_off_the_contract(slug: Any) -> None:
    """[P 2026-10-30] endpoints.md, city-districts: slugs are ASCII ``[a-z0-9-]``; the client
    sends one back as a district (2 to 100 characters), so anything else is refused."""
    with pytest.raises(ValidationError):
        CityDistrictsDto.model_validate({"districts": [{"name": "Wola", "slug": slug}]})


@pytest.mark.parametrize("row", [{"name": "Wola"}, {"slug": "wola"}])
def test_a_district_needs_its_name_and_slug(row: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        CityDistrictsDto.model_validate({"districts": [row]})
