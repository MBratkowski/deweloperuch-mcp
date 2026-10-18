"""Contract of ``deweloperuch_mcp.api.dto.building_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.building_dto import BuildingDto
from deweloperuch_mcp.api.dto.building_trend_dto import BuildingTrendDto
from deweloperuch_mcp.models.building import ENFORCEMENT, SHARE
from support.providers.routes.buildings import (
    BUILDING_ID,
    CISNA,
    CISNA_BODY,
    CISNA_ID,
    SLUG,
    fixture_body,
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


def test_a_building_without_a_name_or_a_street_parses() -> None:
    """tests/fixtures/api/tx_visible_cisna_20261015.json [P 2026-10-15]: the whole
    building, 6 units with 7 transactions of three classes; its name and street are
    blank, so it has neither."""
    parsed = BuildingDto.model_validate(fixture_body(CISNA_BODY))

    assert (parsed.invest_rcn_id, parsed.slug, parsed.city_slug) == (CISNA_ID, CISNA, "cisna")
    assert (parsed.name, parsed.street) == ("", "")
    assert len(parsed.sale) == 6
    classes = sorted(
        deed.classification or "" for unit in parsed.sale for deed in unit.sale_event_rcn
    )
    assert classes == ["egzekucja"] + ["transakcja"] * 5 + ["udzial"]

    building = parsed.to_model()

    assert (building.name, building.street, building.city) == (None, None, "Cisna")


def test_a_floor_the_register_leaves_blank_is_unknown() -> None:
    """[P 2026-10-15] two units of the building cisna have a blank ``floor`` (so do their
    raw records) and a ``floor_number`` of 0: an unknown floor, not the ground floor.
    Every unit there states its rooms."""
    data = fixture_body(CISNA_BODY)
    raw = {unit["sale_rcn_id"]: (unit["floor"], unit["floor_number"]) for unit in data["sale"]}
    assert raw[3366735] == raw[663401] == ("", 0)
    assert raw[3366736] == ("2", 2)

    units = {unit.unit_id: unit for unit in BuildingDto.model_validate(data).to_model().units}

    assert (units[3366735].floor, units[663401].floor, units[3366736].floor) == (None, None, 2)
    assert [units[unit_id].rooms for unit_id in sorted(units)] == [4, 7, 4, 5, 5, 5]


def test_the_transactions_that_are_no_regular_sale_of_the_building() -> None:
    building = BuildingDto.model_validate(fixture_body(CISNA_BODY)).to_model()

    assert building.transactions_count == 7
    assert building.non_regular_transactions() == {ENFORCEMENT: 1, SHARE: 1}
    (share,) = [
        t for unit in building.units for t in unit.transactions if t.classification == SHARE
    ]
    assert (share.share, share.whole_unit) == ("1/2", False)


def test_the_services_averages_leave_out_the_other_transactions() -> None:
    """[W] open question T48. In this building (tests/fixtures/api/, [P 2026-10-15]) the
    service's ``avg_amount``, ``avg_size`` and ``avg_price_sqm`` and its counter
    ``transactions`` leave out the share and the enforcement sale. The building does not
    tell two readings apart, both give the same numbers:

    (a) the ``transakcja`` transactions: the means of their prices and of their units'
        areas, and their summed price over their summed area;
    (b) the units whose last transaction is a ``transakcja``
        (``last_transaction_classification``), with each unit's own ``amount`` and
        ``size``.

    That every building's averages are so is not known; the client passes them on as
    given."""
    data = fixture_body(CISNA_BODY)
    deeds = [(unit, deed) for unit in data["sale"] for deed in unit["sale_event_rcn"]]
    by_deed = [
        (float(d["amount"]), u["size"]) for u, d in deeds if d["classification"] == "transakcja"
    ]
    by_unit = [
        (float(u["amount"]), u["size"])
        for u in data["sale"]
        if u["last_transaction_classification"] == "transakcja"
    ]

    for regular in (by_deed, by_unit):
        prices, areas = [price for price, _ in regular], [area for _, area in regular]
        assert data["transactions"] == len(regular) == 5
        assert data["avg_amount"] == round(sum(prices) / len(prices), 2) == 274_600
        assert data["avg_size"] == round(sum(areas) / len(areas), 2) == 72.08
        assert data["avg_price_sqm"] == round(sum(prices) / sum(areas), 2) == 3809.76
    every = [float(deed["amount"]) for _, deed in deeds]
    assert round(sum(every) / len(every), 2) != data["avg_amount"]

    building = BuildingDto.model_validate(data).to_model()

    assert (building.avg_price, building.avg_area_m2, building.avg_price_per_m2) == (
        274_600.0,
        72.08,
        3809.76,
    )
