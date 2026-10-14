"""The golden cases of every command after a STOP recorded by another process
(tests/golden/cli/<case>.json).
"""

from support.golden.cli import (
    BUILDINGS,
    ESTIMATE,
    OFFERS,
    PLANTED,
    SEARCH,
    TX,
    Case,
    case,
    record_stop,
    stop_file_with,
)
from support.providers.routes.buildings import SLUG as BUILDING_SLUG
from support.providers.routes.buildings import building_routes
from support.providers.routes.developer_search import developer_search_route
from support.providers.routes.government_statistics import (
    stats_routes,
)
from support.providers.routes.investment_search import investment_search_routes
from support.providers.routes.investments import (
    investment_routes,
)
from support.providers.routes.locations import location_routes
from support.providers.routes.offers import offers_route
from support.providers.routes.rankings import ranking_routes
from support.providers.routes.transactions import transaction_routes
from support.providers.routes.valuation import valuation_route

CASES: dict[str, Case] = {
    "after_stop_locations_search": case(
        "locations", "search", "krak", service=location_routes, before=record_stop()
    ),
    "after_stop_offers_search": case(
        *OFFERS, "warszawa", service=offers_route, before=record_stop()
    ),
    "after_stop_offers_get": case(
        "offers",
        "get",
        "2377",
        "--investment",
        "smolna",
        service=investment_routes,
        before=record_stop(429, "limit zapytań", defer=120),
    ),
    "after_stop_investments_get": case(
        "investments", "get", "smolna", service=investment_routes, before=stop_file_with("{")
    ),
    "after_stop_stats_government": case(
        "stats", "government", "polska", "wages", service=stats_routes, before=record_stop()
    ),
    "after_stop_investments_search": case(
        *SEARCH, "sopot", service=investment_search_routes, before=record_stop()
    ),
    "after_planted_stop_locations_search": case(
        "locations", "search", "krak", service=location_routes, before=stop_file_with(PLANTED)
    ),
    "after_stop_developers_search": case(
        "developers", "search", "atal", service=developer_search_route, before=record_stop()
    ),
    "after_stop_valuation_estimate": case(*ESTIMATE, service=valuation_route, before=record_stop()),
    "after_stop_buildings_get": case(
        *BUILDINGS, BUILDING_SLUG, service=building_routes, before=record_stop()
    ),
    "after_stop_stats_transactions": case(
        *TX, "warszawa", service=transaction_routes, before=record_stop()
    ),
    "after_stop_stats_cities": case(
        "stats", "cities", service=ranking_routes, before=record_stop()
    ),
}
