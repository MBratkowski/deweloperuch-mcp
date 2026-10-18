"""The golden cases of the MCP tool ``estimate_property_value`` (tests/golden/mcp/<case>.json)."""

from support.builders.valuation import IN_CISNA, valuation_with_comparables
from support.golden.mcp import INJECTED, POINT, VALUATION_TOOL, Case, case, valuation_is
from support.golden.routes import valuation_answer, without_an_estimate
from support.providers.routes.valuation import cisna_route, valuation_route

CASES: dict[str, Case] = {
    # estimate_property_value
    "valuation": case(VALUATION_TOOL, valuation_route, **POINT),
    "valuation_with_address": case(
        VALUATION_TOOL, valuation_route, **POINT, address="Marszałkowska 100, Warszawa"
    ),
    "valuation_limit_1": case(VALUATION_TOOL, valuation_route, **POINT, limit=1),
    "valuation_limit_0": case(VALUATION_TOOL, valuation_route, **POINT, limit=0),
    "valuation_60_comparables": case(
        VALUATION_TOOL, valuation_is(valuation_with_comparables(60)), **POINT
    ),
    "valuation_60_comparables_limit_50": case(
        VALUATION_TOOL, valuation_is(valuation_with_comparables(60)), **POINT, limit=50
    ),
    "valuation_numbers_as_text": case(
        VALUATION_TOOL, valuation_route, lat="52.2297", lng=" 21.0122 ", area_m2="50", limit="2"
    ),
    "valuation_fraction_of_a_m2": case(
        VALUATION_TOOL, valuation_route, **dict(POINT, area_m2=48.5)
    ),
    "valuation_nulls": case(VALUATION_TOOL, valuation_route, **POINT, address=None, limit=None),
    "valuation_blank_address": case(VALUATION_TOOL, valuation_route, **POINT, address="  "),
    "valuation_without_an_estimate": case(
        VALUATION_TOOL, valuation_is(without_an_estimate()), **POINT
    ),
    "valuation_low_confidence": case(VALUATION_TOOL, cisna_route, **IN_CISNA),
    "valuation_low_confidence_limit_1": case(VALUATION_TOOL, cisna_route, **IN_CISNA, limit=1),
    "valuation_lat_outside_poland": case(VALUATION_TOOL, valuation_route, **dict(POINT, lat=60)),
    "valuation_lng_outside_poland": case(VALUATION_TOOL, valuation_route, **dict(POINT, lng=10)),
    "valuation_lat_true": case(VALUATION_TOOL, valuation_route, **dict(POINT, lat=True)),
    "valuation_lat_with_a_comma": case(
        VALUATION_TOOL, valuation_route, **dict(POINT, lat="52,2297")
    ),
    "valuation_area_too_small": case(VALUATION_TOOL, valuation_route, **dict(POINT, area_m2=5)),
    "valuation_address_too_short": case(VALUATION_TOOL, valuation_route, **POINT, address="ab"),
    "valuation_limit_51": case(VALUATION_TOOL, valuation_route, **POINT, limit=51),
    "valuation_without_lat": case(VALUATION_TOOL, valuation_route, lng=21.0122, area_m2=50),
    "valuation_404": case(VALUATION_TOOL, valuation_answer(404, text=INJECTED), **POINT),
    "valuation_500": case(VALUATION_TOOL, valuation_answer(500, text=INJECTED), **POINT),
    "valuation_403": case(VALUATION_TOOL, valuation_answer(403), **POINT),
    "valuation_another_shape": case(
        VALUATION_TOOL, valuation_answer(200, json=dict(error=INJECTED)), **POINT
    ),
}
