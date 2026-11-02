"""Tests of ``deweloperuch_mcp.api.dto.powiat_map_stats_dto``."""

import pytest

from deweloperuch_mcp.api.adapters.transaction_ranking_api import POWIAT_RANKING
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.powiat_map_stats_dto import (
    PowiatMapStatsDto,
    PowiatMarketDto,
    PowiatRowDto,
)
from deweloperuch_mcp.models.location_ranking import PlaceNames, RankingMarket
from support.providers.routes.rankings import POWIATS_2026_11_02, captured

NO_NAMES = PlaceNames(powiats={}, cities={})


@pytest.mark.parametrize("zero", [0, "0"])
def test_a_zero_is_no_price_area_or_price(zero: int | str) -> None:
    """[W] by analogy with the cities (``Ignatki-osiedle`` [P 2026-10-15]): no market object
    had a 0 on 2026-11-02, so this is a test of the rule on a hand-edited row: the
    secondary market of powiat 302 with its three values replaced by 0."""
    answer = captured(POWIATS_2026_11_02)
    warszawa = next(row for row in answer["rows"] if row["id"] == 302)
    warszawa["wtorny"].update(m2=zero, size=zero, price=zero)

    powiats = Dto.validated(PowiatMapStatsDto, answer, POWIAT_RANKING).to_model(NO_NAMES)

    secondary = next(p for p in powiats.on(RankingMarket.SECONDARY) if p.powiat_id == 302)
    primary = next(p for p in powiats.on(RankingMarket.PRIMARY) if p.powiat_id == 302)
    assert (secondary.price_per_m2, secondary.area_m2, secondary.price) == (None, None, None)
    assert secondary.transaction_count == 14563
    assert None not in (primary.price_per_m2, primary.area_m2, primary.price)


def test_a_powiat_missing_from_the_table_is_named_by_its_id() -> None:
    powiats = Dto.validated(
        PowiatMapStatsDto, captured(POWIATS_2026_11_02), POWIAT_RANKING
    ).to_model(PlaceNames(powiats={302: "powiat Warszawa"}, cities={}))

    names = {p.powiat_id: p.name for p in powiats.on(RankingMarket.ALL)}
    assert (names[302], names[208]) == ("powiat Warszawa", "powiat 208")


def test_internal_fields_are_not_read() -> None:
    """T86: ``primary`` has a base of its own; ``def``, ``q`` and ``w`` are the map's."""
    read = {
        *PowiatMapStatsDto.model_fields,
        *PowiatRowDto.model_fields,
        *PowiatMarketDto.model_fields,
    }

    assert read == {
        "periodStart",
        "periodEndMonth",
        "rows",
        "id",
        "wtorny",
        "pierwotny",
        "oba",
        "n",
        "m2",
        "price",
        "size",
    }
