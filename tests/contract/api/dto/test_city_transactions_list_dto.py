"""Contract of ``deweloperuch_mcp.api.dto.city_transactions_list_dto`` with the service's
real answers (the samples in docs/discovery/samples/, the raw payloads in
tests/fixtures/).
"""

import pytest

from deweloperuch_mcp.api.adapters.transaction_ranking_api import CITY_RANKING
from deweloperuch_mcp.api.dto.city_transactions_list_dto import CityTransactionsListDto
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.models.location_ranking import (
    PRICE_ORDER_MIN_TRANSACTIONS,
    RANKING_LIMIT_MAX,
    LocationRanking,
    LocationTransactions,
    RankingOrder,
)
from support.builders.rankings import criteria, names
from support.providers.routes.rankings import CITIES_2026_10_15, captured
from support.providers.samples import body, envelope


def places_of_2026_10_15() -> tuple[LocationTransactions, ...]:
    """Every place of the complete answer of 2026-10-15 as the domain has it."""
    rows = captured(CITIES_2026_10_15)
    return Dto.validated(CityTransactionsListDto, rows, CITY_RANKING).to_model()


def test_the_city_slugs_are_those_of_search_locations() -> None:
    """[W] for every place (the MCP description of city_slug): the samples name Kraków
    with the same slug in the ranking and in ``/api/cities`` [P 2026-10-09]."""
    ranked = {city["city"]: city["city_slug"] for city in body("api.city_tx_stats")}
    found = {city["city"]: city["city_slug"] for city in body("api.cities_q")["cityMappings"]}

    shared = ranked.keys() & found.keys()
    assert shared == {"Kraków"}
    assert all(ranked[name] == found[name] for name in shared)


def test_the_city_ranking_has_more_places_than_poland_has_towns() -> None:
    """[W] behind "także małe miasteczka i wsie" (level=city): the service ranks 2448
    places [P 2026-10-09]; Poland has about 1000 towns, so villages are among them."""
    assert envelope("api.city_tx_stats")["response"][-1] == "... (2445 more, 2448 total)"


def test_zeros_are_no_price_area_or_price() -> None:
    """[P 2026-10-15]: one place of 2529 has 0 as its price per m², area and price; the
    service writes 0 where it has no value, so the place has none of the three."""
    places = places_of_2026_10_15()

    assert len(places) == 2529
    assert [p for p in places if None in (p.price_per_m2, p.area_m2, p.price)] == [
        LocationTransactions(
            name="Ignatki-osiedle", city_slug="ignatki-osiedle", transaction_count=8
        )
    ]


@pytest.mark.parametrize("order", [RankingOrder.PRICE_PER_M2_ASC, RankingOrder.PRICE_PER_M2_DESC])
def test_the_place_without_a_price_comes_last_by_price_either_way(order: RankingOrder) -> None:
    """Every place ranked (``min_transactions`` 0): the place of zeros is not the cheapest
    any more (it was, live, on 2026-10-15), and the order of the ranking puts it last. A
    ranking shows at most 100 places, so the last one is seen through the order's key."""
    places = places_of_2026_10_15()

    ranking = LocationRanking.of(criteria(order, RANKING_LIMIT_MAX, 0), places)

    assert ranking.total == 2529
    assert ranking.items[0].price_per_m2 is not None and ranking.items[0].price_per_m2 > 0
    assert "Ignatki-osiedle" not in names(ranking)
    assert sorted(places, key=order.key)[-1].name == "Ignatki-osiedle"


def test_a_price_from_a_handful_of_transactions_is_chance() -> None:
    """[W] behind ``PRICE_ORDER_MIN_TRANSACTIONS`` (the default threshold of the price
    orders): most places have at most 2 transactions [P 2026-10-15], and every one of the
    100 cheapest does, down to a tenth of the cheapest price from 20 transactions."""
    places = places_of_2026_10_15()
    counts = [place.transaction_count for place in places]

    every = LocationRanking.of(
        criteria(RankingOrder.PRICE_PER_M2_ASC, RANKING_LIMIT_MAX, 0), places
    )
    by_default = LocationRanking.of(
        criteria(RankingOrder.PRICE_PER_M2_ASC, RANKING_LIMIT_MAX, None), places
    )

    assert (sum(c <= 2 for c in counts), sum(c >= 20 for c in counts)) == (1628, 258)
    assert sum(c >= 50 for c in counts) == 108
    assert all(place.transaction_count <= 2 for place in every.items)
    assert by_default.total == 258
    assert all(p.transaction_count >= PRICE_ORDER_MIN_TRANSACTIONS for p in by_default.items)
    cheapest, steadier = every.items[0].price_per_m2, by_default.items[0].price_per_m2
    assert cheapest is not None and steadier is not None and cheapest < steadier / 10
