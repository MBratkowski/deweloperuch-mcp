"""The golden cases of the MCP tool ``get_market_statistics`` (tests/golden/mcp/<case>.json)."""

from support.golden.mcp import MARKET, Case, case
from support.providers.routes.offer_snapshot import (
    changed_snapshot_route,
    offer_snapshot_routes,
    removed_snapshot_route,
)
from support.providers.rsc import UNKNOWN_CITY

CASES: dict[str, Case] = {
    # get_market_statistics
    "market_sopot": case(MARKET, offer_snapshot_routes, city="sopot"),
    "market_warszawa_filters": case(
        MARKET,
        offer_snapshot_routes,
        city="warszawa",
        price_min="400000",
        price_max=700_000,
        area_max=60,
        top_developers=5,
    ),
    "market_nothing": case(MARKET, offer_snapshot_routes, city="sopot", price_max=1_000),
    "market_whole_country": case(MARKET, offer_snapshot_routes, city="polska"),
    "market_unknown_city": case(MARKET, offer_snapshot_routes, city=UNKNOWN_CITY),
    "market_route_removed": case(MARKET, removed_snapshot_route, city="sopot"),
    "market_snapshot_changed": case(MARKET, changed_snapshot_route, city="sopot"),
    "market_top_31": case(MARKET, offer_snapshot_routes, city="sopot", top_developers=31),
    "market_area_reversed": case(
        MARKET, offer_snapshot_routes, city="sopot", area_min=60, area_max=40
    ),
}
