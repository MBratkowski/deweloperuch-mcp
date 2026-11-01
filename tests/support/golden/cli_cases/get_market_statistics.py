"""The golden cases of ``deweloperuch stats market`` (tests/golden/cli/<case>.json)."""

from support.golden.cli import MARKET, Case, case
from support.providers.routes.offer_snapshot import offer_snapshot_routes, removed_snapshot_route
from support.providers.rsc import UNKNOWN_CITY

CASES: dict[str, Case] = {
    # stats market
    "help_stats_market": case(*MARKET, "--help"),
    "stats_market": case(*MARKET, "sopot", service=offer_snapshot_routes),
    "stats_market_json": case(*MARKET, "sopot", "--json", service=offer_snapshot_routes),
    "stats_market_filters": case(
        *MARKET,
        "warszawa",
        "--price-max",
        "700000",
        "--area-min",
        "40",
        "--top",
        "3",
        service=offer_snapshot_routes,
    ),
    "stats_market_nothing": case(
        *MARKET, "sopot", "--price-max", "1000", service=offer_snapshot_routes
    ),
    "stats_market_whole_country": case(*MARKET, "polska", service=offer_snapshot_routes),
    "stats_market_unknown_city": case(*MARKET, UNKNOWN_CITY, service=offer_snapshot_routes),
    "stats_market_route_removed": case(*MARKET, "sopot", service=removed_snapshot_route),
    "stats_market_top_31": case(*MARKET, "sopot", "--top", "31", service=offer_snapshot_routes),
}
