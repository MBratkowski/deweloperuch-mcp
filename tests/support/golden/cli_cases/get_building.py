"""The golden cases of ``deweloperuch buildings get`` (tests/golden/cli/<case>.json)."""

from support.golden.cli import BUILDINGS, INJECTED_BODY, Case, case
from support.golden.routes import building_answer, trend_answer
from support.providers.routes.buildings import CISNA, building_routes, cisna_routes
from support.providers.routes.buildings import SLUG as BUILDING_SLUG

CASES: dict[str, Case] = {
    "help_buildings_get": case("buildings", "get", "--help"),
    "buildings_get": case(*BUILDINGS, BUILDING_SLUG, service=building_routes),
    "buildings_get_json": case(*BUILDINGS, BUILDING_SLUG, "--json", service=building_routes),
    "buildings_get_trend": case(*BUILDINGS, BUILDING_SLUG, "--trend", service=building_routes),
    "buildings_get_trend_json": case(
        *BUILDINGS, BUILDING_SLUG, "--trend", "--json", service=building_routes
    ),
    # The building cisna as sent (tests/fixtures/api/): other transactions, no trend.
    "buildings_get_cisna_trend": case(*BUILDINGS, CISNA, "--trend", service=cisna_routes),
    "buildings_get_cisna_trend_json": case(
        *BUILDINGS, CISNA, "--trend", "--json", service=cisna_routes
    ),
    "buildings_get_limit_1": case(
        *BUILDINGS, BUILDING_SLUG, "--limit", "1", service=building_routes
    ),
    "buildings_get_limit_0_json": case(
        *BUILDINGS, BUILDING_SLUG, "--limit", "0", "--json", service=building_routes
    ),
    "buildings_get_404": case(*BUILDINGS, BUILDING_SLUG, service=building_answer(404)),
    "buildings_get_500": case(
        *BUILDINGS, BUILDING_SLUG, service=building_answer(500, text=INJECTED_BODY)
    ),
    "buildings_get_trend_500": case(
        *BUILDINGS, BUILDING_SLUG, "--trend", service=trend_answer(500, text=INJECTED_BODY)
    ),
    "buildings_get_slug_capitals": case(*BUILDINGS, "23-Marca-79C-Sopot"),
    "buildings_get_limit_negative": case(*BUILDINGS, BUILDING_SLUG, "--limit", "-1"),
    "buildings_get_limit_text": case(*BUILDINGS, BUILDING_SLUG, "--limit", "x"),
}
