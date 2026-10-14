"""The golden cases of ``deweloperuch stats market`` (tests/golden/cli/<case>.json)."""

from support.golden.cli import MARKET, Case, case
from support.providers.routes.city_sales import city_sales_routes

CASES: dict[str, Case] = {
    # stats market
    "help_stats_market": case(*MARKET, "--help"),
    "stats_market": case(*MARKET, "sopot", service=city_sales_routes),
    "stats_market_json": case(*MARKET, "sopot", "--json", service=city_sales_routes),
    "stats_market_filters": case(
        *MARKET,
        "krakow",
        "--price-max",
        "700000",
        "--area-min",
        "40",
        "--top",
        "3",
        service=city_sales_routes,
    ),
    "stats_market_nothing": case(
        *MARKET, "sopot", "--price-max", "1000", service=city_sales_routes
    ),
    "stats_market_whole_country": case(*MARKET, "polska", service=city_sales_routes),
    "stats_market_unknown_city": case(
        *MARKET,
        "nieznane",
        service=lambda r: r.get("/api/offers/city-sales/nieznane").respond(
            400, json={"error": "Invalid citySlug"}
        ),
    ),
    "stats_market_top_31": case(*MARKET, "sopot", "--top", "31", service=city_sales_routes),
}
