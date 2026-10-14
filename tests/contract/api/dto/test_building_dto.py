"""Contract of ``deweloperuch_mcp.api.dto.building_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.building_dto import BuildingDto
from deweloperuch_mcp.api.dto.building_trend_dto import BuildingTrendDto
from support.providers.routes.buildings import (
    BUILDING_ID,
    SLUG,
)
from support.providers.samples import body, envelope


def test_the_building_sample_parses() -> None:
    parsed = BuildingDto.model_validate(body("api.tx_visible"))

    assert (parsed.invest_rcn_id, parsed.slug, parsed.city_slug) == (BUILDING_ID, SLUG, "sopot")
    assert [unit.sale_rcn_id for unit in parsed.sale] == [477553, 477335, 477334]
    first = parsed.sale[0]
    assert (first.floor_number, first.rooms_number, first.size) == (1, 5, 122.01)
    (deed,) = first.sale_event_rcn
    assert (deed.amount, deed.amount_sqm, deed.creation_date) == (
        "1900000.47",
        "15572.5",
        "2025-11-17",
    )
    assert (deed.marketType, deed.classification, deed.participation) == (
        "pierwotny",
        "transakcja",
        "1/1",
    )


@pytest.mark.parametrize(
    ("sample", "model"),
    [("api.tx_visible", BuildingDto), ("api.avg_trend_building", BuildingTrendDto)],
)
def test_the_dtos_refuse_trimming_markers(sample: str, model: type[Any]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(envelope(sample)["response"])


def test_the_date_of_a_transaction_is_the_day_of_its_deed() -> None:
    """[W] the mapping takes ``creation_date`` as the day of the deed: in every
    transaction of the sample it is the raw record's ``transactionDate``."""
    deeds = [deed for unit in body("api.tx_visible")["sale"] for deed in unit["sale_event_rcn"]]

    assert len(deeds) == 3
    for deed in deeds:
        assert deed["creation_date"] == deed["additionalData"]["transactionDate"]
