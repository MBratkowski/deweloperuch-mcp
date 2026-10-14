"""The golden cases of the MCP tool ``get_market_statistics`` (tests/golden/mcp/<case>.json)."""

from support.golden.mcp import MARKET, Case, case
from support.providers.routes.city_sales import city_sales_routes

CASES: dict[str, Case] = {
    # get_market_statistics
    "market_sopot": case(MARKET, city_sales_routes, city="sopot"),
    "market_krakow_filters": case(
        MARKET,
        city_sales_routes,
        city="krakow",
        price_min="400000",
        price_max=700_000,
        area_max=60,
        top_developers=5,
    ),
    "market_nothing": case(MARKET, city_sales_routes, city="sopot", price_max=1_000),
    "market_whole_country": case(MARKET, city_sales_routes, city="polska"),
    "market_unknown_city": case(
        MARKET,
        lambda r: r.get("/api/offers/city-sales/nieznane").respond(
            400, json={"error": "Invalid citySlug"}
        ),
        city="nieznane",
    ),
    "market_top_31": case(MARKET, city_sales_routes, city="sopot", top_developers=31),
    "market_area_reversed": case(MARKET, city_sales_routes, city="sopot", area_min=60, area_max=40),
}
