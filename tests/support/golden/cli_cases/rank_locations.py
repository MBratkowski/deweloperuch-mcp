"""The golden cases of ``deweloperuch stats cities`` (tests/golden/cli/<case>.json)."""

from support.golden.cli import Case, case
from support.golden.routes import many_cities
from support.providers.routes.rankings import CITY_RANKING, ranking_routes

CASES: dict[str, Case] = {
    # stats cities: the samples (3 places of each level) and copies of their rows
    "help_stats_cities": case("stats", "cities", "--help"),
    "stats_cities": case("stats", "cities", service=ranking_routes),
    "stats_cities_json": case("stats", "cities", "--json", service=ranking_routes),
    "stats_cities_powiat_price_asc_min_transactions": case(
        "stats",
        "cities",
        "--level",
        "powiat",
        "--sort",
        "price_per_m2_asc",
        "--min-transactions",
        "200000",
        service=ranking_routes,
    ),
    "stats_cities_price_desc_limit_2_of_2448": case(
        "stats", "cities", "--sort", "price_per_m2_desc", "--limit", "2", service=many_cities
    ),
    "stats_cities_limit_0": case("stats", "cities", "--limit", "0", service=ranking_routes),
    "stats_cities_level_unknown": case("stats", "cities", "--level", "gmina"),
    "stats_cities_500": case(
        "stats", "cities", service=lambda r: r.get(CITY_RANKING).respond(500, text="busy")
    ),
}
