"""The golden cases of the MCP tool ``get_market_statistics`` (tests/golden/mcp/<case>.json)."""

from support.golden.mcp import MARKET, Case, case
from support.providers.routes.offer_snapshot import (
    gone_snapshot_route,
    offer_snapshot_routes,
    unknown_city_snapshot_route,
)

CASES: dict[str, Case] = {
    # get_market_statistics
    "market_sopot": case(MARKET, offer_snapshot_routes, city="sopot"),
    "market_krakow_filters": case(
        MARKET,
        offer_snapshot_routes,
        city="krakow",
        price_min="400000",
        price_max=700_000,
        area_max=60,
        top_developers=5,
    ),
    "market_nothing": case(MARKET, offer_snapshot_routes, city="sopot", price_max=1_000),
    "market_whole_country": case(MARKET, offer_snapshot_routes, city="polska"),
    "market_wroclaw": case(MARKET, offer_snapshot_routes, city="wroclaw", top_developers=4),
    "market_unknown_city": case(MARKET, unknown_city_snapshot_route, city="nieznane"),
    "market_route_gone": case(MARKET, gone_snapshot_route, city="sopot"),
    "market_top_31": case(MARKET, offer_snapshot_routes, city="sopot", top_developers=31),
    "market_area_reversed": case(
        MARKET, offer_snapshot_routes, city="sopot", area_min=60, area_max=40
    ),
}
