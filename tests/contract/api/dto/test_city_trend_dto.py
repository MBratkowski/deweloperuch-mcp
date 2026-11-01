"""Contract of ``deweloperuch_mcp.api.dto.city_trend_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.city_trend_dto import CityTrendDto
from deweloperuch_mcp.flight import component_props
from deweloperuch_mcp.models.government_statistics import PeriodCount
from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionPeriod,
    TransactionSeries,
)
from support.builders.transactions import WARSZAWA, warszawa_page, warszawa_quarters
from support.providers.samples import body, envelope


def test_the_quarterly_sample() -> None:
    parsed = CityTrendDto.model_validate(body("api.avg_trend_city"))

    assert [(row.period, row.avgPriceSqm, row.count) for row in parsed.data] == [
        ("2017-Q1", 7595, 2922),
        ("2017-Q2", 7695, 2854),
        ("2017-Q3", 7844, 2893),
    ]


def test_the_price_of_a_quarter_is_its_median() -> None:
    """[P 2026-10-30] docs/discovery/endpoints.md, avg-price-trend/city: ``avgPriceSqm`` is
    a median despite its name; the trend gives no mean, area or price of a flat."""
    quarters = CityTrendDto.model_validate(body("api.avg_trend_city")).to_model()

    assert quarters[0] == TransactionPeriod("2017-Q1", 2922, median_price_per_m2=7595.0)
    assert all(item.average_price_per_m2 is None for item in quarters)


def test_the_median_is_the_one_of_the_statistics_page() -> None:
    """The quarters of the 2.0 page (``view.quarterly``, tests/fixtures/rsc/
    stats_tx_warszawa_20261031.rsc: 2026-Q1 ``current``, 2025-Q4 ``prev``, 2025-Q1
    ``yearAgo``) against the trend of Warsaw (tests/fixtures/api/
    avg_trend_city_warszawa_20261016.json): ``avgPriceSqm`` is within 2 PLN/m² of the
    page's median and more than 500 from its mean, as in the 36 quarters of endpoints.md."""
    view = next(v for name, v in component_props(warszawa_page()) if name == "view")
    quarterly: dict[str, Any] = view["quarterly"]
    trend = {row["period"]: row["avgPriceSqm"] for row in warszawa_quarters()["data"]}

    assert (view["anchor"], quarterly["quarterLabel"]) == ("2026-Q1", "I kw. 2026")
    for period, key in (("2026-Q1", "current"), ("2025-Q4", "prev"), ("2025-Q1", "yearAgo")):
        assert abs(trend[period] - quarterly[key]["med_price_sqm"]) <= 2, period
        assert abs(trend[period] - quarterly[key]["avg_price_sqm"]) > 500, period


def test_every_quarter_of_warsaw_ends_with_two_incomplete_ones() -> None:
    """tests/fixtures/api/avg_trend_city_warszawa_20261016.json, whole: 39 quarters;
    2026-Q2 (1,034) and 2026-Q3 (37, its median price per m² about twice the usual) are
    incomplete, 2026-Q1 (3,721) is the last complete quarter."""
    quarters = CityTrendDto.model_validate(warszawa_quarters()).to_model()

    found = TransactionSeries(WARSZAWA, Granularity.QUARTER, quarters).latest(PeriodCount(39))

    assert (found.total, found.available_from) == (39, "2017-Q1")
    assert [item.period for item in found.periods if item.incomplete] == ["2026-Q2", "2026-Q3"]
    assert found.last_complete_period == "2026-Q1"
    assert found.few_transactions is False
    assert [item.transactions for item in found.periods[-3:]] == [3721, 1034, 37]
    assert found.periods[-1].median_price_per_m2 == 33176


def test_the_dto_refuses_trimming_markers() -> None:
    with pytest.raises(ValidationError):
        CityTrendDto.model_validate(envelope("api.avg_trend_city")["response"])


def test_the_sample_echoes_a_city_as_its_scope() -> None:
    assert CityTrendDto.model_validate(body("api.avg_trend_city")).scope == "city"


@pytest.mark.parametrize("scope", ["building", {"label": "city"}, None])
def test_a_scope_other_than_a_city_is_off_the_contract(scope: object) -> None:
    data = body("api.avg_trend_city")
    if scope is None:
        del data["scope"]
    else:
        data["scope"] = scope

    with pytest.raises(ValidationError):
        CityTrendDto.model_validate(data)
