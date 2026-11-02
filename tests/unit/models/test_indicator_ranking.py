"""Tests of ``deweloperuch_mcp.models.indicator_ranking``."""

import pytest

from deweloperuch_mcp.models.errors import InvalidValueError, ValueName
from deweloperuch_mcp.models.indicator_ranking import (
    CityIndicator,
    Indicator,
    IndicatorCriteria,
    IndicatorRanking,
    IndicatorValues,
)
from deweloperuch_mcp.models.location_ranking import RankingLimit, RankingOrder
from support.fakes.rankings import NBP_PRICES, UNEMPLOYMENT


def ranked(ranking: IndicatorRanking) -> list[tuple[str, float | None]]:
    return [(item.name, item.value) for item in ranking.items]


def test_indicator_ranking_leaves_out_cities_without_it() -> None:
    """[P 2026-11-02] gov_map_stats_20261102.json: NBP prices for 17 of the 66 cities; the
    49 others are left out and counted, never ranked as 0."""
    ranking = IndicatorRanking.of(
        IndicatorCriteria(Indicator.NBP_PRICE_PER_M2, limit=RankingLimit(100)), NBP_PRICES
    )

    assert (ranking.total, ranking.returned, ranking.left_out) == (17, 17, 49)
    assert ranking.truncated is False
    assert None not in [item.value for item in ranking.items]
    assert ranking.items[0].name == "Warszawa"
    assert ranking.period == "2026-Q2"


def test_the_highest_value_comes_first_by_default_ties_by_name() -> None:
    ranking = IndicatorRanking.of(IndicatorCriteria(Indicator.UNEMPLOYMENT_RATE), UNEMPLOYMENT)

    assert ranking.criteria.order is RankingOrder.VALUE_DESC
    assert ranked(ranking) == [
        ("Radom", 10.4),
        ("Białystok", 6.0),
        ("Poznań", 1.6),
        ("Warszawa", 1.6),
    ]


def test_value_asc_puts_the_lowest_first_and_the_limit_cuts() -> None:
    ranking = IndicatorRanking.of(
        IndicatorCriteria(
            Indicator.UNEMPLOYMENT_RATE, order=RankingOrder.VALUE_ASC, limit=RankingLimit(2)
        ),
        UNEMPLOYMENT,
    )

    assert ranked(ranking) == [("Poznań", 1.6), ("Warszawa", 1.6)]
    assert (ranking.total, ranking.returned, ranking.truncated) == (4, 2, True)


def test_a_value_of_0_is_a_value() -> None:
    """Natural increase may be 0; only a missing value leaves a city out."""
    values = IndicatorValues(
        indicator=Indicator.NATURAL_INCREASE,
        period="2025",
        cities=(
            CityIndicator(city_slug="a", name="A", value=0.0),
            CityIndicator(city_slug="b", name="B", value=-5.0),
        ),
    )

    ranking = IndicatorRanking.of(IndicatorCriteria(Indicator.NATURAL_INCREASE), values)

    assert ranked(ranking) == [("A", 0.0), ("B", -5.0)]
    assert ranking.left_out == 0


@pytest.mark.parametrize("order", [RankingOrder.TRANSACTIONS_DESC, RankingOrder.PRICE_PER_M2_DESC])
def test_transaction_orders_rank_no_indicator(order: RankingOrder) -> None:
    with pytest.raises(ValueError, match="value_"):
        IndicatorCriteria(Indicator.AVERAGE_WAGE, order=order)


def test_values_of_another_indicator_are_refused() -> None:
    with pytest.raises(ValueError, match="nbp_price_per_m2"):
        IndicatorRanking.of(IndicatorCriteria(Indicator.AVERAGE_WAGE), NBP_PRICES)


@pytest.mark.parametrize(
    ("indicator", "unit"),
    [
        (Indicator.UNEMPLOYMENT_RATE, "%"),
        (Indicator.AVERAGE_WAGE, "PLN/mies."),
        (Indicator.DWELLINGS_COMPLETED, "mieszkania (suma 12 miesięcy)"),
        (Indicator.DWELLINGS_STARTED, "mieszkania (suma 12 miesięcy)"),
        (Indicator.AVERAGE_DWELLING_AREA, "m²"),
        (Indicator.NATURAL_INCREASE, "osoby"),
        (Indicator.NBP_PRICE_PER_M2, "PLN/m²"),
    ],
)
def test_every_indicator_has_its_unit(indicator: Indicator, unit: str) -> None:
    """The wage is monthly, the dwellings a sum of 12 months [P 2026-11-02]."""
    assert indicator.unit == unit


def test_indicators_parse_their_values() -> None:
    assert Indicator.parse(" nbp_price_per_m2 ") is Indicator.NBP_PRICE_PER_M2
    with pytest.raises(InvalidValueError) as caught:
        Indicator.parse("bezrobocie")
    assert caught.value.value is ValueName.INDICATOR
