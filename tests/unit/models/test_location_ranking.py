"""Tests of ``deweloperuch_mcp.models.location_ranking``."""

from collections.abc import Callable

import pytest

from deweloperuch_mcp.models.errors import (
    InvalidValueError,
    ValueName,
)
from deweloperuch_mcp.models.location_ranking import (
    DEFAULT_RANKING_LIMIT,
    PRICE_ORDER_MIN_TRANSACTIONS,
    RANKING_LIMIT_MAX,
    TRANSACTIONS_MAX,
    LocationRanking,
    MinTransactions,
    RankingCriteria,
    RankingLevel,
    RankingLimit,
    RankingOrder,
)
from support.builders.rankings import criteria, names
from support.fakes.rankings import CITIES, city


def test_the_default_ranking_is_by_transactions_most_first() -> None:
    ranking = LocationRanking.of(RankingCriteria(), CITIES)

    assert names(ranking) == ["Warszawa", "Kraków", "Wrocław", "Bez ceny", "Wieś"]
    assert (ranking.total, ranking.returned, ranking.truncated) == (5, 5, False)
    assert ranking.criteria.level is RankingLevel.CITY
    assert ranking.criteria.limit.value == DEFAULT_RANKING_LIMIT == 20


def test_by_price_per_m2_the_places_without_a_price_come_last_either_way() -> None:
    desc = LocationRanking.of(criteria(RankingOrder.PRICE_PER_M2_DESC), CITIES)
    asc = LocationRanking.of(criteria(RankingOrder.PRICE_PER_M2_ASC), CITIES)

    assert names(desc) == ["Wieś", "Warszawa", "Kraków", "Wrocław", "Bez ceny"]
    assert names(asc) == ["Wrocław", "Kraków", "Warszawa", "Wieś", "Bez ceny"]


def test_ties_go_to_more_transactions_then_the_name() -> None:
    same = (city("B", 5, 100.0), city("A", 5, 100.0), city("C", 9, 100.0))

    assert names(LocationRanking.of(criteria(), same)) == ["C", "A", "B"]
    by_price = LocationRanking.of(criteria(RankingOrder.PRICE_PER_M2_ASC), same)
    assert names(by_price) == ["C", "A", "B"]


def test_min_transactions_leaves_out_the_small_places_before_the_cut() -> None:
    ranking = LocationRanking.of(criteria(RankingOrder.PRICE_PER_M2_DESC, 2, 1443), CITIES)

    assert names(ranking) == ["Warszawa", "Kraków"]
    assert (ranking.total, ranking.returned, ranking.truncated) == (3, 2, True)
    assert ranking.left_out == 2


def test_the_limit_cuts_the_ranking_and_says_so() -> None:
    ranking = LocationRanking.of(criteria(limit=1), CITIES)

    assert names(ranking) == ["Warszawa"]
    assert (ranking.total, ranking.returned, ranking.truncated) == (5, 1, True)


def test_nothing_meets_min_transactions() -> None:
    ranking = LocationRanking.of(criteria(min_transactions=10_000), CITIES)

    assert ranking.items == ()
    assert (ranking.total, ranking.returned, ranking.truncated) == (0, 0, False)


SMALL = (city("Pięć", 5, 1_000.0), city("Dwadzieścia", 20, 2_000.0), city("Sto", 100, 3_000.0))
"""A place below the price orders' default threshold, one at it and one above."""


@pytest.mark.parametrize("order", [RankingOrder.PRICE_PER_M2_ASC, RankingOrder.PRICE_PER_M2_DESC])
def test_by_price_the_places_under_20_transactions_are_left_out_unless_asked(
    order: RankingOrder,
) -> None:
    ranking = LocationRanking.of(criteria(order, min_transactions=None), SMALL)

    assert PRICE_ORDER_MIN_TRANSACTIONS == 20
    assert sorted(names(ranking)) == ["Dwadzieścia", "Sto"]
    assert (ranking.total, ranking.left_out) == (2, 1)
    assert ranking.criteria.threshold == MinTransactions(20)
    assert ranking.criteria.threshold_by_default is True


def test_by_transactions_no_place_is_left_out_unless_asked() -> None:
    ranking = LocationRanking.of(criteria(min_transactions=None), SMALL)

    assert names(ranking) == ["Sto", "Dwadzieścia", "Pięć"]
    assert ranking.left_out == 0
    assert ranking.criteria.threshold == MinTransactions(0)
    assert ranking.criteria.threshold_by_default is False
    assert RankingCriteria().threshold == MinTransactions(0)


@pytest.mark.parametrize("given", [0, 5, 50])
@pytest.mark.parametrize("order", list(RankingOrder))
def test_a_given_threshold_wins_over_the_default_even_0(given: int, order: RankingOrder) -> None:
    ranking = LocationRanking.of(criteria(order, min_transactions=given), SMALL)

    assert ranking.total == sum(place.transaction_count >= given for place in SMALL)
    assert ranking.left_out == len(SMALL) - ranking.total
    assert ranking.criteria.threshold == MinTransactions(given)
    assert ranking.criteria.threshold_by_default is False


@pytest.mark.parametrize(
    ("parse", "given", "parsed"),
    [
        (RankingLevel.parse, "city", RankingLevel.CITY),
        (RankingLevel.parse, " powiat ", RankingLevel.POWIAT),
        (RankingLevel.parse, RankingLevel.POWIAT, RankingLevel.POWIAT),
        (RankingOrder.parse, "price_per_m2_asc", RankingOrder.PRICE_PER_M2_ASC),
        (RankingOrder.parse, " transactions_desc", RankingOrder.TRANSACTIONS_DESC),
        (RankingLimit.parse, 1, RankingLimit(1)),
        (RankingLimit.parse, RANKING_LIMIT_MAX, RankingLimit(100)),
        (MinTransactions.parse, 0, MinTransactions(0)),
        (MinTransactions.parse, TRANSACTIONS_MAX, MinTransactions(TRANSACTIONS_MAX)),
        (MinTransactions.parse, None, None),
    ],
)
def test_value_objects_take_their_values(
    parse: Callable[[object], object], given: object, parsed: object
) -> None:
    assert parse(given) == parsed


@pytest.mark.parametrize(
    ("parse", "given", "value"),
    [
        (RankingLevel.parse, "gmina", ValueName.RANKING_LEVEL),
        (RankingLevel.parse, None, ValueName.RANKING_LEVEL),
        (RankingOrder.parse, "price_desc", ValueName.RANKING_ORDER),
        (RankingOrder.parse, 1, ValueName.RANKING_ORDER),
        (RankingLimit.parse, 0, ValueName.RANKING_LIMIT),
        (RankingLimit.parse, RANKING_LIMIT_MAX + 1, ValueName.RANKING_LIMIT),
        (RankingLimit.parse, True, ValueName.RANKING_LIMIT),
        (RankingLimit.parse, "5", ValueName.RANKING_LIMIT),
        (MinTransactions.parse, -1, ValueName.MIN_TRANSACTIONS),
        (MinTransactions.parse, TRANSACTIONS_MAX + 1, ValueName.MIN_TRANSACTIONS),
        (MinTransactions.parse, 1.5, ValueName.MIN_TRANSACTIONS),
    ],
)
def test_value_objects_refuse_other_values(
    parse: Callable[[object], object], given: object, value: ValueName
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        parse(given)

    assert caught.value.value is value
    assert caught.value.given == given
