"""The golden cases of the MCP tool ``get_building`` (tests/golden/mcp/<case>.json)."""

from support.builders.buildings import building_with_units
from support.golden.mcp import BUILDING_TOOL, INJECTED, Case, building_is, case
from support.golden.routes import building_answer, trend_answer
from support.providers.routes.buildings import SLUG as BUILDING_SLUG
from support.providers.routes.buildings import building_routes

CASES: dict[str, Case] = {
    # get_building
    "building": case(BUILDING_TOOL, building_routes, building_slug=BUILDING_SLUG),
    "building_trend": case(
        BUILDING_TOOL, building_routes, building_slug=BUILDING_SLUG, include_trend=True
    ),
    "building_60_units": case(
        BUILDING_TOOL, building_is(building_with_units(60)), building_slug=BUILDING_SLUG
    ),
    "building_limit_0": case(BUILDING_TOOL, building_routes, building_slug=BUILDING_SLUG, limit=0),
    "building_limit_text": case(
        BUILDING_TOOL, building_routes, building_slug=BUILDING_SLUG, limit="1"
    ),
    "building_limit_51": case(
        BUILDING_TOOL, building_routes, building_slug=BUILDING_SLUG, limit=51
    ),
    "building_12_units_3_transactions": case(
        BUILDING_TOOL, building_is(building_with_units(12, 3)), building_slug=BUILDING_SLUG
    ),
    "building_nulls": case(
        BUILDING_TOOL,
        building_is(building_with_units(30)),
        building_slug=BUILDING_SLUG,
        limit=None,
        include_trend=None,
    ),
    "building_then_from_the_cache": case(
        BUILDING_TOOL,
        building_routes,
        then=((BUILDING_TOOL, dict(building_slug=BUILDING_SLUG, limit=1)),),
        building_slug=BUILDING_SLUG,
    ),
    "building_404": case(
        BUILDING_TOOL, building_answer(404, text=INJECTED), building_slug=BUILDING_SLUG
    ),
    "building_500": case(
        BUILDING_TOOL, building_answer(500, text=INJECTED), building_slug=BUILDING_SLUG
    ),
    "building_another_shape": case(
        BUILDING_TOOL, building_answer(200, json=dict(other=INJECTED)), building_slug=BUILDING_SLUG
    ),
    "building_trend_500": case(
        BUILDING_TOOL,
        trend_answer(500, text=INJECTED),
        building_slug=BUILDING_SLUG,
        include_trend=True,
    ),
    "building_slug_capitals": case(
        BUILDING_TOOL, building_routes, building_slug="23-Marca-79C-Sopot"
    ),
    "building_slug_path": case(BUILDING_TOOL, building_routes, building_slug="sopot/../x"),
    "building_without_slug": case(BUILDING_TOOL, building_routes, limit=1),
}
