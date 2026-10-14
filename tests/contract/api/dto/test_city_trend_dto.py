"""Contract of ``deweloperuch_mcp.api.dto.city_trend_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.city_trend_dto import CityTrendDto
from deweloperuch_mcp.api.dto.monthly_transaction_stats_dto import MonthlyTransactionStatsDto
from support.providers.samples import body, envelope


def test_the_quarterly_sample() -> None:
    parsed = CityTrendDto.model_validate(body("api.avg_trend_city"))

    assert [(row.period, row.avgPriceSqm, row.count) for row in parsed.data] == [
        ("2017-Q1", 7595, 2922),
        ("2017-Q2", 7695, 2854),
        ("2017-Q3", 7844, 2893),
    ]


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
