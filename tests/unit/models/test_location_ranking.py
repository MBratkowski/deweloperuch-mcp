"""Tests of ``deweloperuch_mcp.models.location_ranking``."""

from collections.abc import Callable

import pytest

from deweloperuch_mcp.models.errors import (
    InvalidValueError,
    ValueName,
)
from deweloperuch_mcp.models.location_ranking import (
    DEFAULT_RANKING_LIMIT,
    DEFAULT_RANKING_MARKET,
    PRICE_ORDER_MIN_TRANSACTIONS,
    RANKING_LIMIT_MAX,
    TRANSACTIONS_MAX,
    LocationRanking,
    LocationTransactions,
    MinTransactions,
    PlaceNames,
    PowiatTransactions,
    RankingCriteria,
    RankingLevel,
    RankingLimit,
    RankingMarket,
    RankingOrder,
    TransactionPeriod,
)
from support.builders.rankings import criteria, names
from support.fakes.rankings import CITIES, POWIATS, SOPOT_SECONDARY, city


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
@pytest.mark.parametrize("order", [order for order in RankingOrder if not order.by_value])
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
        (RankingOrder.parse, "value_asc", RankingOrder.VALUE_ASC),
        (RankingMarket.parse, " primary ", RankingMarket.PRIMARY),
        (RankingMarket.parse, RankingMarket.ALL, RankingMarket.ALL),
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
        (RankingMarket.parse, "wtorny", ValueName.RANKING_MARKET),
        (RankingMarket.parse, None, ValueName.RANKING_MARKET),
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


# --- powiats: one market over one period -------------------------------------------------------


def test_powiat_ranking_leaves_out_powiats_without_the_market() -> None:
    """[P 2026-11-01] a missing market is no object, not 0 transactions: powiat Sopot has
    none on the primary market. It is not ranked there, and the figures say how many
    powiats were left out for it; on the secondary market it is."""
    primary = POWIATS.on(RankingMarket.PRIMARY)
    secondary = POWIATS.on(RankingMarket.SECONDARY)

    assert "powiat Sopot" not in [place.name for place in primary]
    assert SOPOT_SECONDARY in secondary
    assert (POWIATS.without(RankingMarket.PRIMARY), POWIATS.without(RankingMarket.SECONDARY)) == (
        1,
        0,
    )
    ranking = LocationRanking.of(criteria(level=RankingLevel.POWIAT), primary)
    assert ranking.total == len(primary) == 2


def test_the_period_of_the_powiats_is_the_services() -> None:
    assert POWIATS.period == TransactionPeriod(start="2025-11-01", end="2026-10")


def test_the_market_of_a_powiat_ranking_defaults_to_the_secondary() -> None:
    """The user's decision of 2026-11-01: the service's default view in 343 of 380
    powiats [P 2026-11-01], and the months of the transaction statistics are secondary only."""
    assert DEFAULT_RANKING_MARKET is RankingMarket.SECONDARY
    assert criteria(level=RankingLevel.POWIAT).powiat_market is RankingMarket.SECONDARY
    given = RankingCriteria(level=RankingLevel.POWIAT, market=RankingMarket.ALL)
    assert given.powiat_market is RankingMarket.ALL


def test_market_is_refused_at_city_level() -> None:
    """The city ranking has no market split; the request words the refusal for the caller
    (``RankLocationsRequest``), the domain only refuses the combination."""
    with pytest.raises(ValueError, match="market"):
        RankingCriteria(level=RankingLevel.CITY, market=RankingMarket.PRIMARY)


@pytest.mark.parametrize("order", [RankingOrder.VALUE_DESC, RankingOrder.VALUE_ASC])
def test_value_orders_rank_no_transactions(order: RankingOrder) -> None:
    assert order.by_value is True
    with pytest.raises(ValueError, match="indicator"):
        RankingCriteria(order=order)


def test_an_empty_market_is_no_market() -> None:
    lonely = LocationTransactions(name="powiat Sopot", powiat_id=208, transaction_count=310)
    figures = PowiatTransactions(
        period=TransactionPeriod(start="2025-11-01", end="2026-10"),
        powiats=1,
        markets={RankingMarket.SECONDARY: (lonely,)},
    )

    assert figures.on(RankingMarket.ALL) == ()
    assert figures.without(RankingMarket.ALL) == 1


# --- the names of places ------------------------------------------------------------------------


NAMES = PlaceNames(
    powiats={302: "powiat Warszawa", 117: "powiat Tarnobrzeg"},
    cities={"warszawa": "Warszawa", "tarnobrzeg": "Tarnobrzeg", "lodz": "Łódź"},
)


@pytest.mark.parametrize(
    ("slug", "name"),
    [
        ("tarnobrzeg", "Tarnobrzeg"),
        ("Tarnobrzeg", "Tarnobrzeg"),  # [P 2026-11-01] the one slug of tx-cities not lowercase
        (" WARSZAWA ", "Warszawa"),
        ("Łódź", "Łódź"),
        ("ŁÓDŹ", "Łódź"),
    ],
)
def test_name_table_folds_case(slug: str, name: str) -> None:
    """A slug the service writes in another case or with Polish letters finds its city."""
    assert NAMES.city(slug) == name


def test_unknown_places_are_shown_by_their_identity() -> None:
    assert NAMES.powiat(302) == "powiat Warszawa"
    assert NAMES.powiat(999) == "powiat 999"
    assert NAMES.city("nowe-miasto") == "nowe-miasto"
