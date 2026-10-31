"""Tests of ``deweloperuch_mcp.models.market_statistics``."""

import dataclasses
import statistics

import pytest

from deweloperuch_mcp.models.errors import InvalidValueError, OneCity, SlugText, ValueName
from deweloperuch_mcp.models.market_statistics import (
    CityOffers,
    DeveloperShare,
    MarketCity,
    MarketCriteria,
    Spread,
)
from deweloperuch_mcp.models.values import (
    CitySlug,
    DeveloperCount,
    PriceRange,
)
from support.builders.market import AS_OF, KRAKOW, NAMES, OFFERS, sale


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
        ValueName.MARKET_CITY,
        OneCity(),
        "polska",
    )
    assert MarketCriteria(city=KRAKOW).top == DeveloperCount(10)


def test_the_city_of_a_market_is_a_city_slug_refused_in_its_own_words() -> None:
    assert MarketCity.parse(" sopot ") == MarketCity("sopot")
    assert isinstance(MarketCity("sopot"), CitySlug)

    with pytest.raises(InvalidValueError) as caught:
        MarketCity.parse("Kraków")

    assert (caught.value.value, caught.value.rule, caught.value.given) == (
        ValueName.MARKET_CITY,
        SlugText(),
        "Kraków",
    )


def test_the_summary_of_every_active_offer() -> None:
    """The source gives active offers only (D20), so every offer counts."""
    result = OFFERS.statistics(MarketCriteria(city=KRAKOW))

    assert (result.offers, result.investments, result.developers) == (8, 4, 3)
    assert result.price_spread == Spread.of(
        [500_000.0, 700_000.0, 600_000.0, 900_000.0, 300_000.0, 400_000.0, 350_000.0]
    )
    assert result.area_spread == Spread.of([50.0, 70.0, 40.0, 60.0, 30.0, 40.0, 45.0])
    assert result.price_per_m2_spread == Spread.of(
        [10_000.0, 10_000.0, 15_000.0, 15_000.0, 10_000.0, 10_000.0]
    )
    assert result.top_developers == tuple(
        DeveloperShare(
            developer_slug=slug,
            developer_name=NAMES[slug],
            offers=offers,
            investments=investments,
            median_price_per_m2=median,
        )
        for slug, offers, investments, median in (
            ("yit", 3, 1, 10_000),
            ("atal", 2, 2, 10_000),
            ("dom", 2, 1, 15_000),
        )
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


def test_the_summary_is_of_the_day_of_its_offers() -> None:
    """The source's day (``as_of``), also for a summary of nothing; ``None`` without one."""
    nothing = MarketCriteria(city=KRAKOW, price=PriceRange.parse(1, 2))
    undated = CityOffers(city=KRAKOW, offers=OFFERS.offers)

    assert OFFERS.statistics(MarketCriteria(city=KRAKOW)).as_of == AS_OF
    assert OFFERS.statistics(nothing).as_of == AS_OF
    assert undated.statistics(MarketCriteria(city=KRAKOW)).as_of is None


def test_a_developer_is_named_by_its_first_name_in_the_order_of_the_source() -> None:
    """The first non-empty name among every offer of the developer, in the source's order,
    whatever the criteria match; no name when none of them has one."""
    unnamed = dataclasses.replace(sale(1, "atal", 500_000.0, 50.0), developer_name=None)
    offers = CityOffers(
        city=KRAKOW,
        offers=(
            unnamed,
            sale(2, "atal", 700_000.0, 70.0),
            dataclasses.replace(sale(3, "atal", 900_000.0, 60.0), developer_name="ATAL"),
            dataclasses.replace(sale(4, "dom", 600_000.0, 40.0), developer_name=None),
        ),
    )
    expensive = MarketCriteria(city=KRAKOW, price=PriceRange.parse(800_000, None))

    every = offers.statistics(MarketCriteria(city=KRAKOW)).top_developers
    assert [(d.developer_slug, d.developer_name) for d in every] == [
        ("atal", "ATAL S.A."),
        ("dom", None),
    ]
    assert [d.developer_name for d in offers.statistics(expensive).top_developers] == ["ATAL S.A."]
