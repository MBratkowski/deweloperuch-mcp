"""Tests of ``deweloperuch_mcp.models.market_statistics``."""

import statistics

import pytest

from deweloperuch_mcp.models.errors import InvalidValueError, OneCity, ValueName
from deweloperuch_mcp.models.market_statistics import (
    DeveloperShare,
    MarketCriteria,
    Spread,
)
from deweloperuch_mcp.models.values import (
    CitySlug,
    DeveloperCount,
    PriceRange,
)
from support.builders.market import KRAKOW, OFFERS


@pytest.mark.parametrize(
    "values",
    [[1.0], [1.0, 2.0], [1.0, 2.0, 3.0, 4.0], [5.0, 1.0, 9.0, 3.0, 7.0, 2.0], list(range(101))],
)
def test_quantiles_are_the_inclusive_ones(values: list[float]) -> None:
    spread = Spread.of(values)
    ordered = sorted(values)
    expected = (
        statistics.quantiles(ordered, n=4, method="inclusive")
        if len(ordered) > 1
        else [ordered[0]] * 3
    )

    assert spread is not None
    assert (spread.min, spread.max) == (ordered[0], ordered[-1])
    assert (spread.p25, spread.median, spread.p75) == pytest.approx(
        (expected[0], statistics.median(ordered), expected[2])
    )


def test_a_quantile_between_ranks_is_linear() -> None:
    assert Spread.quantile([1.0, 2.0, 3.0, 4.0], 0.25) == 1.75
    assert Spread.of([]) is None


def test_the_market_is_of_one_city() -> None:
    with pytest.raises(InvalidValueError) as caught:
        MarketCriteria(city=CitySlug("polska"))

    assert (caught.value.value, caught.value.rule, caught.value.given) == (
        ValueName.CITY,
        OneCity(),
        "polska",
    )
    assert MarketCriteria(city=KRAKOW).top == DeveloperCount(10)


def test_the_summary_of_every_active_offer() -> None:
    result = OFFERS.statistics(MarketCriteria(city=KRAKOW))

    assert (result.offers, result.investments, result.developers) == (8, 4, 3)
    assert result.price_spread == Spread.of(
        [500_000.0, 700_000.0, 600_000.0, 900_000.0, 300_000.0, 400_000.0, 350_000.0]
    )
    assert result.area_spread == Spread.of([50.0, 70.0, 40.0, 60.0, 30.0, 40.0, 45.0])
    assert result.price_per_m2_spread == Spread.of(
        [10_000.0, 10_000.0, 15_000.0, 15_000.0, 10_000.0, 10_000.0]
    )
    assert result.top_developers == (
        DeveloperShare(developer_slug="yit", offers=3, investments=1, median_price_per_m2=10_000),
        DeveloperShare(developer_slug="atal", offers=2, investments=2, median_price_per_m2=10_000),
        DeveloperShare(developer_slug="dom", offers=2, investments=1, median_price_per_m2=15_000),
    )


def test_the_largest_developers_come_first_ties_by_slug_and_are_cut() -> None:
    result = OFFERS.statistics(MarketCriteria(city=KRAKOW, top=DeveloperCount(2)))

    assert [(d.developer_slug, d.offers) for d in result.top_developers] == [
        ("yit", 3),
        ("atal", 2),
    ]
    assert (result.developers, result.developers_omitted) == (3, 1)


def test_nothing_matches() -> None:
    result = OFFERS.statistics(MarketCriteria(city=KRAKOW, price=PriceRange.parse(1, 2)))

    assert (result.offers, result.investments, result.developers) == (0, 0, 0)
    assert (result.price_spread, result.area_spread, result.price_per_m2_spread) == (
        None,
        None,
        None,
    )
    assert result.top_developers == ()
