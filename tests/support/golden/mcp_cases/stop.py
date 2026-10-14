"""The golden cases of every tool after a STOP recorded by another process
(tests/golden/mcp/<case>.json).
"""

from support.golden.mcp import (
    BUILDING_TOOL,
    INVESTMENT_TOOL,
    OFFER,
    OFFER_2377,
    OFFERS,
    POINT,
    RANK,
    SEARCH,
    SMOLNA,
    SOPOT,
    STATS,
    TX,
    VALUATION_TOOL,
    WARSZAWA,
    Case,
    every_route,
    stop_429_recorded,
    stop_recorded,
    stop_unreadable,
)
from support.providers.routes.buildings import SLUG as BUILDING_SLUG
from support.providers.routes.investment_search import investment_search_routes
from support.providers.routes.rankings import ranking_routes
from support.providers.routes.transactions import transaction_routes

CASES: dict[str, Case] = {
    "after_stop_search_investments": Case(
        ((SEARCH, SOPOT),), (investment_search_routes,), stop_recorded
    ),
    # a STOP recorded by another process, for every tool
    **{
        f"after_stop_{tool}": Case(((tool, arguments),), (every_route,), stop_recorded)
        for tool, arguments in (
            ("search_locations", {"query": "krak"}),
            (OFFERS, WARSZAWA),
            (OFFER, OFFER_2377),
            (INVESTMENT_TOOL, SMOLNA),
            (STATS, {"location": "warszawa", "dataset": "wages"}),
            ("search_developers", {"name": "atal"}),
            (BUILDING_TOOL, dict(building_slug=BUILDING_SLUG)),
            (VALUATION_TOOL, POINT),
        )
    },
    "after_stop_429": Case(((OFFERS, WARSZAWA),), (every_route,), stop_429_recorded),
    "after_unreadable_stop": Case(((OFFERS, WARSZAWA),), (every_route,), stop_unreadable),
    "after_stop_rank_locations": Case(((RANK, {}),), (every_route, ranking_routes), stop_recorded),
    "after_stop_get_transaction_statistics": Case(
        ((TX, {"city": "warszawa"}),), (every_route, transaction_routes), stop_recorded
    ),
}
