"""Tests of ``deweloperuch_mcp.api.dto.powiat_transactions_list_dto``."""

import pytest

from deweloperuch_mcp.api.adapters.transaction_ranking_api import POWIAT_RANKING
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.powiat_transactions_list_dto import PowiatTransactionsListDto
from support.providers.routes.rankings import POWIATS_2026_10_15, captured


@pytest.mark.parametrize("zero", [0, "0"])
def test_a_zero_is_no_price_area_or_price(zero: int | str) -> None:
    """[W] by analogy with the cities (``Ignatki-osiedle`` [P 2026-10-15]): no powiat had a
    0 on 2026-10-15, so this is a test of the rule on a hand-edited row: the first powiat
    of the complete answer with its three values replaced by 0."""
    rows = captured(POWIATS_2026_10_15)
    rows[0].update(avg_price_sqm=zero, avg_size=zero, avg_amount=zero)

    first, second = Dto.validated(PowiatTransactionsListDto, rows, POWIAT_RANKING).to_model()[:2]

    assert (first.name, first.price_per_m2, first.area_m2, first.price) == (
        "powiat Warszawa",
        None,
        None,
        None,
    )
    assert None not in (second.price_per_m2, second.area_m2, second.price)
