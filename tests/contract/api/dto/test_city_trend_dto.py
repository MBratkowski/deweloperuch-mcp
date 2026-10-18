"""Contract of ``deweloperuch_mcp.api.dto.city_trend_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.city_trend_dto import CityTrendDto
from deweloperuch_mcp.api.dto.monthly_transaction_stats_dto import MonthlyTransactionStatsDto
from deweloperuch_mcp.models.government_statistics import PeriodCount
from deweloperuch_mcp.models.transaction_series import Granularity, TransactionSeries
from support.builders.transactions import WARSZAWA, warszawa_quarters
from support.providers.samples import body, envelope


def test_the_quarterly_sample() -> None:
    parsed = CityTrendDto.model_validate(body("api.avg_trend_city"))

    assert [(row.period, row.avgPriceSqm, row.count) for row in parsed.data] == [
        ("2017-Q1", 7595, 2922),
        ("2017-Q2", 7695, 2854),
        ("2017-Q3", 7844, 2893),
    ]


def test_every_quarter_of_warsaw_ends_with_two_incomplete_ones() -> None:
    """tests/fixtures/api/avg_trend_city_warszawa_20261016.json, whole: 39 quarters;
    2026-Q2 (1,034) and 2026-Q3 (37, its average price per m² about twice the usual) are
    incomplete, 2026-Q1 (3,721) is the last complete quarter."""
    quarters = CityTrendDto.model_validate(warszawa_quarters()).to_model()

    found = TransactionSeries(WARSZAWA, Granularity.QUARTER, quarters).latest(PeriodCount(39))

    assert (found.total, found.available_from) == (39, "2017-Q1")
    assert [item.period for item in found.periods if item.incomplete] == ["2026-Q2", "2026-Q3"]
    assert found.last_complete_period == "2026-Q1"
    assert found.few_transactions is False
    assert [item.transactions for item in found.periods[-3:]] == [3721, 1034, 37]
    assert found.periods[-1].average_price_per_m2 == 33176


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("api.monthly_tx", MonthlyTransactionStatsDto),
        ("api.avg_trend_city", CityTrendDto),
    ],
)
def test_the_dtos_refuse_trimming_markers(name: str, model: type[Any]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(envelope(name)["response"])


def test_the_samples_echo_a_city_as_their_scope() -> None:
    assert MonthlyTransactionStatsDto.model_validate(body("api.monthly_tx")).scope.label
    assert CityTrendDto.model_validate(body("api.avg_trend_city")).scope == "city"


@pytest.mark.parametrize(
    ("name", "model", "scope"),
    [
        ("api.monthly_tx", MonthlyTransactionStatsDto, {"label": "powiat"}),
        ("api.monthly_tx", MonthlyTransactionStatsDto, "city"),
        ("api.monthly_tx", MonthlyTransactionStatsDto, None),
        ("api.avg_trend_city", CityTrendDto, "building"),
        ("api.avg_trend_city", CityTrendDto, {"label": "city"}),
        ("api.avg_trend_city", CityTrendDto, None),
    ],
)
def test_a_scope_other_than_a_city_is_off_the_contract(
    name: str, model: type[Any], scope: object
) -> None:
    data = body(name)
    if scope is None:
        del data["scope"]
    else:
        data["scope"] = scope

    with pytest.raises(ValidationError):
        model.model_validate(data)
