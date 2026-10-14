"""The golden cases of the MCP tool ``get_offer`` (tests/golden/mcp/<case>.json)."""

from support.golden.mcp import INJECTED, OFFER, OFFER_2377, Case, case, history_missing
from support.golden.routes import investment_answer
from support.providers.routes.investments import (
    investment_routes,
)

CASES: dict[str, Case] = {
    # get_offer
    "offer": case(OFFER, investment_routes, **OFFER_2377),
    "offer_id_text": case(OFFER, investment_routes, offer_id="2377", investment_slug="smolna"),
    "offer_not_in_the_investment": case(
        OFFER, investment_routes, offer_id=999, investment_slug="smolna"
    ),
    "offer_without_history": case(OFFER, history_missing, **OFFER_2377),
    "offer_unknown_investment": case(OFFER, investment_answer(404), **OFFER_2377),
    "offer_id_0": case(OFFER, investment_routes, offer_id=0, investment_slug="smolna"),
    "offer_id_true": case(OFFER, investment_routes, offer_id=True, investment_slug="smolna"),
    "offer_id_float_text": case(
        OFFER, investment_routes, offer_id="2377.0", investment_slug="smolna"
    ),
    "offer_slug_capitals": case(OFFER, investment_routes, offer_id=2377, investment_slug="SMOLNA"),
    "offer_slug_blank": case(OFFER, investment_routes, offer_id=2377, investment_slug=""),
    "offer_500": case(OFFER, investment_answer(500, text=INJECTED), **OFFER_2377),
}
