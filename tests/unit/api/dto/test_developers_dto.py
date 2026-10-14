"""Tests of ``deweloperuch_mcp.api.dto.developers_dto``."""

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.developers_dto import DevelopersDto
from support.providers.samples import body


def test_the_dto_parses_the_sample() -> None:
    parsed = DevelopersDto.model_validate(body("api.developers_q"))

    assert [(d.name, d.slug, d.offerCount) for d in parsed.developers] == [
        ("ATAL S.A.", "atal", 4265)
    ]
    assert (parsed.hasMore, parsed.total, parsed.page) == (False, 1, 1)


def test_the_dto_tolerates_a_missing_offer_count_and_unknown_fields() -> None:
    data = body("api.developers_q")
    data["developers"][0].pop("offerCount")
    data["developers"][0]["new"] = 1

    parsed = DevelopersDto.model_validate(data)

    assert parsed.developers[0].offerCount is None


@pytest.mark.parametrize("missing", ["developers", "hasMore", "total"])
def test_the_dto_needs_what_the_result_relies_on(missing: str) -> None:
    data = body("api.developers_q")
    data.pop(missing)

    with pytest.raises(ValidationError):
        DevelopersDto.model_validate(data)
