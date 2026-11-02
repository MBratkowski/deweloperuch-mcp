"""Tests of ``deweloperuch_mcp.api.dto.place_names_dto``."""

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.place_names_dto import PlaceNamesDto


def test_the_packaged_table_names_every_powiat_and_the_66_cities() -> None:
    table = PlaceNamesDto.packaged().to_model()

    assert len(table.powiats) == 380
    assert len(table.cities) == 66
    assert table.powiat(302) == "powiat Warszawa"
    assert table.city("Tarnobrzeg") == "Tarnobrzeg"
    assert table.city("jastrzebie-zdroj") == "Jastrzębie-Zdrój"


def test_the_table_is_read_once() -> None:
    assert PlaceNamesDto.packaged() is PlaceNamesDto.packaged()


def test_slugs_of_the_table_are_folded() -> None:
    table = PlaceNamesDto(powiats={}, cities={"Lodz": "Łódź"}).to_model()

    assert table.cities == {"lodz": "Łódź"}
    assert table.city("ŁÓDŹ") == "Łódź"


def test_a_table_of_another_shape_is_refused() -> None:
    with pytest.raises(ValidationError):
        PlaceNamesDto.model_validate({"powiats": {"x": "powiat X"}, "cities": {}})
    with pytest.raises(ValidationError):
        PlaceNamesDto.model_validate({"powiats": {}, "cities": {}, "gminy": {}})
