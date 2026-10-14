"""The golden cases of ``deweloperuch locations search`` (tests/golden/cli/<case>.json)."""

from support.golden.cli import INJECTED_BODY, Case, case
from support.golden.routes import FULL_SUGGESTIONS, NO_CITIES, locations_with
from support.providers.routes.locations import location_routes
from support.providers.samples import body

CASES: dict[str, Case] = {
    "help_locations_search": case("locations", "search", "--help"),
    # locations search
    "locations_search": case("locations", "search", "krak", service=location_routes),
    "locations_search_json": case("locations", "search", "krak", "--json", service=location_routes),
    "locations_search_more_cities": case(
        "locations",
        "search",
        "krak",
        service=locations_with(dict(body("api.cities_q"), hasMore=True)),
    ),
    "locations_search_more_cities_json": case(
        "locations",
        "search",
        "krak",
        "--json",
        service=locations_with(dict(body("api.cities_q"), hasMore=True)),
    ),
    "locations_search_full_suggestions": case(
        "locations", "search", "mokot", service=locations_with(suggestions=FULL_SUGGESTIONS)
    ),
    "locations_search_nothing": case(
        "locations", "search", "xyzzy", service=locations_with(NO_CITIES, {"suggestions": []})
    ),
    "locations_search_nothing_json": case(
        "locations",
        "search",
        "xyzzy",
        "--json",
        service=locations_with(NO_CITIES, {"suggestions": []}),
    ),
    "locations_search_polish_letters": case(
        "locations", "search", "  Kraków ", service=location_routes
    ),
    "locations_search_too_short": case("locations", "search", "k", service=location_routes),
    "locations_search_too_long": case("locations", "search", "x" * 101, service=location_routes),
    "locations_search_cities_500": case(
        "locations",
        "search",
        "krak",
        service=lambda r: r.get(path="/api/cities").respond(500, text=INJECTED_BODY),
    ),
    "locations_search_suggestions_503": case(
        "locations",
        "search",
        "krak",
        service=lambda r: (
            r.get(path="/api/cities").respond(200, json=body("api.cities_q")),
            r.get(path="/api/location-search").respond(503, headers={"Retry-After": "10"}),
        ),
    ),
}
