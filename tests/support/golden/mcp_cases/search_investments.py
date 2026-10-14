"""The golden cases of the MCP tool ``search_investments`` (tests/golden/mcp/<case>.json)."""

from support.golden.mcp import (
    INJECTED,
    INVESTMENT_TOOL,
    SEARCH,
    SMOLNA,
    SOPOT,
    Case,
    case,
    search_names_are,
)
from support.golden.routes import search_answer, search_city_is
from support.providers.routes.investment_search import investment_search_routes
from support.providers.routes.investments import (
    investment_routes,
)
from support.providers.samples import body

CASES: dict[str, Case] = {
    # search_investments
    "investments_search": case(SEARCH, investment_search_routes, **SOPOT),
    "investments_search_by_name": case(SEARCH, investment_search_routes, name="nowy targ"),
    "investments_search_every_argument": case(
        SEARCH,
        investment_search_routes,
        city="sopot",
        name="KOLIBKI",
        developer_slug="invest-komfort-spolka-akcyjna",
        sort="price_per_m2_desc",
        limit=1,
    ),
    "investments_search_many": case(SEARCH, search_city_is(60), **SOPOT),
    "investments_search_many_by_price": case(
        SEARCH, search_city_is(60), city="sopot", sort="price_per_m2_asc", limit=3
    ),
    "investments_search_nothing": case(SEARCH, search_city_is(0), **SOPOT),
    "investments_search_filters_match_nothing": case(
        SEARCH, investment_search_routes, city="sopot", developer_slug="atal"
    ),
    "investments_search_name_nothing": case(
        SEARCH,
        search_names_are({"investments": [], "hasMore": False, "total": 0, "page": 1}),
        name="zzqxv",
    ),
    "investments_search_name_more": case(
        SEARCH,
        search_names_are(dict(body("api.investments_q"), hasMore=True, total=9)),
        name="nowy",
        limit=2,
    ),
    "investments_search_without_arguments": case(SEARCH, investment_search_routes),
    "investments_search_polska": case(SEARCH, investment_search_routes, city="polska"),
    "investments_search_city_capitalized": case(SEARCH, investment_search_routes, city="Sopot"),
    "investments_search_city_with_spaces": case(SEARCH, investment_search_routes, city=" sopot "),
    "investments_search_limit_text": case(
        SEARCH, investment_search_routes, city="sopot", limit="1"
    ),
    "investments_search_limit_31": case(SEARCH, investment_search_routes, city="sopot", limit=31),
    "investments_search_limit_true": case(
        SEARCH, investment_search_routes, city="sopot", limit=True
    ),
    "investments_search_sort_unknown": case(
        SEARCH, investment_search_routes, city="sopot", sort="cheap"
    ),
    "investments_search_developer_without_city": case(
        SEARCH, investment_search_routes, name="kolibki", developer_slug="atal"
    ),
    "investments_search_sort_without_city": case(
        SEARCH, investment_search_routes, name="kolibki", sort="name"
    ),
    "investments_search_nulls": case(
        SEARCH,
        investment_search_routes,
        city="sopot",
        name=None,
        developer_slug=None,
        sort=None,
        limit=None,
    ),
    "investments_search_blanks": case(
        SEARCH, investment_search_routes, city="sopot", name="", developer_slug=" ", sort=""
    ),
    "investments_search_404": case(SEARCH, search_answer(404, text=INJECTED), **SOPOT),
    "investments_search_500": case(SEARCH, search_answer(500, text=INJECTED), **SOPOT),
    "investments_search_html": case(
        SEARCH,
        search_answer(200, text=f"<html>{INJECTED}</html>", headers={"Content-Type": "text/html"}),
        **SOPOT,
    ),
    "investments_search_another_shape": case(
        SEARCH, search_answer(200, json={INJECTED: True}), **SOPOT
    ),
    "investments_search_then_investment": case(
        SEARCH,
        (investment_search_routes, investment_routes),
        then=((INVESTMENT_TOOL, SMOLNA),),
        **SOPOT,
    ),
}
