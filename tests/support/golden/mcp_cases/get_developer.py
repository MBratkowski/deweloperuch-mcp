"""The golden cases of the MCP tool ``get_developer`` (tests/golden/mcp/<case>.json)."""

from support.golden.mcp import DEVELOPER, Case, case
from support.providers.routes.developer_profiles import developer_routes
from support.providers.rsc import UNKNOWN_DEVELOPER

CASES: dict[str, Case] = {
    # get_developer
    "developer_warszawa": case(DEVELOPER, developer_routes, developer_slug="atal", city="warszawa"),
    "developer_whole_country": case(DEVELOPER, developer_routes, developer_slug="atal"),
    # the 2.0 build: no `data` prop, the summary computed from the investments
    "developer_archicom_2_0": case(DEVELOPER, developer_routes, developer_slug="archicom"),
    "developer_limit_100_from_the_cache": case(
        DEVELOPER,
        developer_routes,
        then=((DEVELOPER, {"developer_slug": "atal", "limit": 100}),),
        developer_slug="atal",
        city=None,
        limit=None,
    ),
    "developer_unknown": case(
        DEVELOPER, developer_routes, developer_slug=UNKNOWN_DEVELOPER, city="warszawa"
    ),
    "developer_slug_capitals": case(DEVELOPER, developer_routes, developer_slug="ATAL"),
    "developer_city_name": case(DEVELOPER, developer_routes, developer_slug="atal", city="Kraków"),
    "developer_limit_0": case(DEVELOPER, developer_routes, developer_slug="atal", limit=0),
    "developer_unknown_argument": case(DEVELOPER, developer_routes, slug="atal"),
}
