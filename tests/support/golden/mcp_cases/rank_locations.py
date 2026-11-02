"""The golden cases of the MCP tool ``rank_locations`` (tests/golden/mcp/<case>.json)."""

from support.golden.mcp import INJECTED, RANK, Case, case
from support.golden.routes import many_cities
from support.providers.routes.rankings import (
    CITY_INDICATORS,
    CITY_RANKING,
    POWIAT_RANKING,
    captured_ranking_routes,
    ranking_routes,
)

CASES: dict[str, Case] = {
    # rank_locations: the samples (3 places of each level, 3 cities with indicators) and
    # copies of their rows
    "rank_cities": case(RANK, ranking_routes),
    "rank_powiats": case(RANK, ranking_routes, level="powiat"),
    "rank_powiats_primary": case(RANK, ranking_routes, level="powiat", market="primary"),
    "rank_indicator_average_wage": case(RANK, ranking_routes, indicator="average_wage"),
    "rank_indicator_unemployment_asc": case(
        RANK, ranking_routes, indicator="unemployment_rate", sort="value_asc"
    ),
    "rank_market_at_city_level": case(RANK, ranking_routes, market="primary"),
    "rank_indicator_with_min_transactions": case(
        RANK, ranking_routes, indicator="average_wage", min_transactions=20
    ),
    "rank_indicator_with_powiats": case(
        RANK, ranking_routes, indicator="average_wage", level="powiat"
    ),
    "rank_indicator_with_market": case(
        RANK, ranking_routes, indicator="average_wage", market="primary"
    ),
    "rank_indicator_with_price_sort": case(
        RANK, ranking_routes, indicator="average_wage", sort="price_per_m2_desc"
    ),
    "rank_value_sort_without_indicator": case(RANK, ranking_routes, sort="value_desc"),
    "rank_cities_price_desc_min_transactions": case(
        RANK, ranking_routes, sort="price_per_m2_desc", min_transactions=1450
    ),
    "rank_powiats_price_asc_limit_1": case(
        RANK, ranking_routes, level="powiat", sort="price_per_m2_asc", limit=1
    ),
    "rank_cities_5_of_2448": case(RANK, many_cities, limit=5),
    # the complete answers of 2026-10-15: by price without min_transactions (the default
    # threshold of 20) and with min_transactions=0 (every place)
    "rank_cities_price_asc_default_threshold": case(
        RANK, captured_ranking_routes, sort="price_per_m2_asc"
    ),
    "rank_cities_price_asc_min_transactions_0": case(
        RANK, captured_ranking_routes, sort="price_per_m2_asc", min_transactions=0, limit=5
    ),
    # the complete answers of 2026-11-02: powiats without the primary market, NBP prices
    # for 17 of 66 cities
    "rank_powiats_primary_captured": case(
        RANK, captured_ranking_routes, level="powiat", market="primary", limit=5
    ),
    "rank_indicator_nbp_captured": case(
        RANK, captured_ranking_routes, indicator="nbp_price_per_m2", limit=5
    ),
    "rank_nothing_left": case(RANK, ranking_routes, min_transactions=1_000_000),
    "rank_nulls": case(
        RANK, ranking_routes, level=None, sort=None, limit=None, min_transactions=None
    ),
    "rank_blank_choices_and_text_numbers": case(
        RANK, ranking_routes, level=" ", sort="", limit="2", min_transactions=" 5 "
    ),
    "rank_level_unknown": case(RANK, ranking_routes, level="gmina"),
    "rank_sort_unknown": case(RANK, ranking_routes, sort="price_desc"),
    "rank_limit_0": case(RANK, ranking_routes, limit=0),
    "rank_limit_101": case(RANK, ranking_routes, limit=101),
    "rank_limit_true": case(RANK, ranking_routes, limit=True),
    "rank_min_transactions_negative": case(RANK, ranking_routes, min_transactions=-1),
    "rank_500": case(RANK, lambda r: r.get(CITY_RANKING).respond(500, text=INJECTED)),
    "rank_403": case(RANK, lambda r: r.get(CITY_RANKING).respond(403)),
    "rank_another_shape": case(
        RANK,
        lambda r: r.get(POWIAT_RANKING).respond(200, json={INJECTED: True}),
        level="powiat",
    ),
    "rank_indicator_another_shape": case(
        RANK,
        lambda r: r.get(CITY_INDICATORS).respond(200, json={INJECTED: True}),
        indicator="average_wage",
    ),
    "rank_twice_one_request": case(
        RANK, ranking_routes, then=((RANK, {"sort": "price_per_m2_asc"}),)
    ),
}
