"""The golden cases of ``deweloperuch offers get`` (tests/golden/cli/<case>.json)."""

from support.golden.cli import Case, case, history_missing, sale_events_answer
from support.golden.routes import investment_answer
from support.providers.routes.investments import (
    investment_routes,
)

CASES: dict[str, Case] = {
    "help_offers_get": case("offers", "get", "--help"),
    # offers get
    "offers_get": case(
        "offers", "get", "2377", "--investment", "smolna", service=investment_routes
    ),
    "offers_get_json": case(
        "offers", "get", "2377", "--investment", "smolna", "--json", service=investment_routes
    ),
    "offers_get_not_in_the_investment": case(
        "offers", "get", "999", "--investment", "smolna", service=investment_routes
    ),
    "offers_get_without_history": case(
        "offers", "get", "2377", "--investment", "smolna", service=history_missing
    ),
    "offers_get_history_500": case(
        "offers", "get", "2377", "--investment", "smolna", service=sale_events_answer(500)
    ),
    "offers_get_unknown_investment": case(
        "offers", "get", "2377", "--investment", "smolna", service=investment_answer(404)
    ),
    "offers_get_offer_0": case("offers", "get", "0", "--investment", "smolna"),
    "offers_get_offer_text": case("offers", "get", "abc", "--investment", "smolna"),
    "offers_get_without_investment": case("offers", "get", "2377"),
    "offers_get_investment_capitals": case("offers", "get", "2377", "--investment", "SMOLNA"),
}
