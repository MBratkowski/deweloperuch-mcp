"""The golden cases of ``deweloperuch stats market`` (tests/golden/cli/<case>.json)."""

from support.golden.cli import MARKET, Case, case
from support.providers.routes.offer_snapshot import (
    gone_snapshot_route,
    offer_snapshot_routes,
    unknown_city_snapshot_route,
)

CASES: dict[str, Case] = {
    # stats market
    "help_stats_market": case(*MARKET, "--help"),
    "stats_market": case(*MARKET, "sopot", service=offer_snapshot_routes),
    "stats_market_json": case(*MARKET, "sopot", "--json", service=offer_snapshot_routes),
    "stats_market_filters": case(
        *MARKET,
        "krakow",
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
    "stats_market_unknown_city": case(*MARKET, "nieznane", service=unknown_city_snapshot_route),
    "stats_market_route_gone": case(*MARKET, "sopot", service=gone_snapshot_route),
    "stats_market_top_31": case(*MARKET, "sopot", "--top", "31", service=offer_snapshot_routes),
}
