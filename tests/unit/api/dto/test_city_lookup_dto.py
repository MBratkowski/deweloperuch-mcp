"""Tests of ``deweloperuch_mcp.api.dto.city_lookup_dto``: what is no answer of the
dictionary (the real ones are in tests/contract/api/dto/test_city_lookup_dto.py)."""

from typing import Any

import pytest

from deweloperuch_mcp.api.dto.city_lookup_dto import CityLookupDto
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.errors import UnexpectedResponseError
from support.providers.samples import body

VILLAGE = body("api.city_lookup.village_transactions")


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param({"city": None, "city_slug": "ignatki-osiedle"}, id="name-null"),
        pytest.param({"city": "Ignatki-osiedle", "city_slug": None}, id="slug-null"),
        pytest.param({"city_slug": "ignatki-osiedle"}, id="name-absent"),
        pytest.param({"city": None}, id="slug-absent"),
        pytest.param({**VILLAGE, "city": ""}, id="name-empty"),
        pytest.param({**VILLAGE, "city": "x" * 101}, id="name-too-long"),
        pytest.param({**VILLAGE, "city": "Ignatki\x1b[2J"}, id="name-control"),
        pytest.param({**VILLAGE, "city_slug": "Ignatki-Osiedle"}, id="slug-capitals"),
        pytest.param({**VILLAGE, "city": 7}, id="name-number"),
    ],
)
def test_an_answer_the_client_cannot_read_is_a_changed_service(answer: dict[str, Any]) -> None:
    with pytest.raises(UnexpectedResponseError):
        Dto.validated(CityLookupDto, answer, "/api/city-lookup")


def test_extra_fields_are_ignored() -> None:
    found = CityLookupDto.model_validate({**VILLAGE, "woj": "mazowieckie"})

    assert found.to_model() is not None
