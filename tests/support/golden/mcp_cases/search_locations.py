"""The golden cases of the MCP tool ``search_locations`` (tests/golden/mcp/<case>.json)."""

from support.golden.mcp import INJECTED, Case, case
from support.golden.routes import FULL_SUGGESTIONS, NO_CITIES, locations_with
from support.providers.routes.locations import location_routes
from support.providers.samples import body

CASES: dict[str, Case] = {
    # search_locations
    "locations": case("search_locations", location_routes, query="krak"),
    "locations_more_cities": case(
        "search_locations", locations_with(dict(body("api.cities_q"), hasMore=True)), query="krak"
    ),
    "locations_full_suggestions": case(
        "search_locations", locations_with(suggestions=FULL_SUGGESTIONS), query="mokot"
    ),
    "locations_nothing": case(
        "search_locations", locations_with(NO_CITIES, {"suggestions": []}), query="xyzzy"
    ),
    "locations_polish_letters": case("search_locations", location_routes, query="  Kraków "),
    "locations_too_short": case("search_locations", location_routes, query="k"),
    "locations_too_long": case("search_locations", location_routes, query="x" * 101),
    "locations_without_query": case("search_locations", location_routes),
    "locations_query_number": case("search_locations", location_routes, query=42),
    "locations_cities_500": case(
        "search_locations",
        lambda r: r.get(path="/api/cities").respond(500, text=INJECTED),
        query="krak",
    ),
    "locations_403": case(
        "search_locations", lambda r: r.get(path="/api/cities").respond(403), query="krak"
    ),
}
