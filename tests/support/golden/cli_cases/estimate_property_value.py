"""The golden cases of ``deweloperuch valuation estimate`` (tests/golden/cli/<case>.json)."""

from support.builders.valuation import valuation_with_comparables
from support.golden.cli import ESCAPES, ESTIMATE, INJECTED_BODY, Case, case, with_the_first_address
from support.golden.routes import valuation_answer, without_an_estimate
from support.providers.routes.valuation import valuation_route

CASES: dict[str, Case] = {
    "help_valuation_estimate": case("valuation", "estimate", "--help"),
    # valuation estimate
    "valuation_estimate": case(*ESTIMATE, service=valuation_route),
    "valuation_estimate_json": case(*ESTIMATE, "--json", service=valuation_route),
    "valuation_estimate_address_limit_1": case(
        *ESTIMATE,
        "--address",
        "Marszałkowska 100, Warszawa",
        "--limit",
        "1",
        service=valuation_route,
    ),
    "valuation_estimate_limit_0_json": case(
        *ESTIMATE, "--limit", "0", "--json", service=valuation_route
    ),
    "valuation_estimate_60_comparables": case(
        *ESTIMATE, service=lambda r: valuation_route(r, valuation_with_comparables(60))
    ),
    "valuation_estimate_without_an_estimate": case(
        *ESTIMATE, service=lambda r: valuation_route(r, without_an_estimate())
    ),
    "valuation_estimate_lat_outside_poland": case(*ESTIMATE, "--lat", "60"),
    "valuation_estimate_lng_outside_poland": case(*ESTIMATE, "--lng", "10"),
    "valuation_estimate_area_too_big": case(*ESTIMATE, "--area", "501"),
    "valuation_estimate_lat_text": case(*ESTIMATE, "--lat", "52,2297"),
    "valuation_estimate_address_too_short": case(*ESTIMATE, "--address", "ab"),
    "valuation_estimate_limit_negative": case(*ESTIMATE, "--limit", "-1"),
    "valuation_estimate_without_area": case("valuation", "estimate", "--lat", "52", "--lng", "21"),
    "valuation_estimate_404": case(*ESTIMATE, service=valuation_answer(404)),
    "valuation_estimate_500": case(*ESTIMATE, service=valuation_answer(500, text=INJECTED_BODY)),
    "valuation_estimate_escapes_in_the_address": case(
        *ESTIMATE,
        service=lambda r: valuation_route(r, with_the_first_address(ESCAPES)),
    ),
}
