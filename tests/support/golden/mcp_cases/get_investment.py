"""The golden cases of the MCP tool ``get_investment`` (tests/golden/mcp/<case>.json)."""

import httpx

from support.builders.investments import investment_with_offers
from support.golden.mcp import (
    INJECTED,
    INVESTMENT_TOOL,
    OFFER,
    OFFER_2377,
    SMOLNA,
    Case,
    case,
    history_missing,
)
from support.golden.routes import investment_answer, investment_is
from support.providers.routes.investments import (
    INVESTMENT,
    investment_routes,
)
from support.providers.routes.locations import location_routes

CASES: dict[str, Case] = {
    "offer_after_investment_from_the_cache": case(
        INVESTMENT_TOOL, investment_routes, then=((OFFER, OFFER_2377),), **SMOLNA
    ),
    # get_investment
    "investment": case(INVESTMENT_TOOL, investment_routes, **SMOLNA),
    "investment_60_offers": case(
        INVESTMENT_TOOL, investment_is(investment_with_offers(60)), **SMOLNA
    ),
    "investment_60_offers_limit_200": case(
        INVESTMENT_TOOL,
        investment_is(investment_with_offers(60)),
        investment_slug="smolna",
        limit=200,
    ),
    "investment_history_limit_1": case(
        INVESTMENT_TOOL, investment_routes, investment_slug="smolna", include_history=True, limit=1
    ),
    "investment_history": case(
        INVESTMENT_TOOL, investment_routes, investment_slug="smolna", include_history=True
    ),
    "investment_limit_0": case(
        INVESTMENT_TOOL, investment_routes, investment_slug="smolna", limit=0
    ),
    "investment_limit_text": case(
        INVESTMENT_TOOL, investment_routes, investment_slug="smolna", limit="1"
    ),
    "investment_nulls": case(
        INVESTMENT_TOOL,
        investment_is(investment_with_offers(30)),
        investment_slug="smolna",
        limit=None,
        include_history=None,
    ),
    "investment_history_text": case(
        INVESTMENT_TOOL, investment_routes, investment_slug="smolna", include_history="yes"
    ),
    "investment_404": case(INVESTMENT_TOOL, investment_answer(404), **SMOLNA),
    "investment_404_with_a_body": case(
        INVESTMENT_TOOL, investment_answer(404, text=INJECTED), **SMOLNA
    ),
    "investment_500": case(INVESTMENT_TOOL, investment_answer(500, text=INJECTED), **SMOLNA),
    "investment_redirect": case(
        INVESTMENT_TOOL, investment_answer(301, headers={"Location": "/api/elsewhere"}), **SMOLNA
    ),
    "investment_html": case(
        INVESTMENT_TOOL,
        investment_answer(
            200, text=f"<html>{INJECTED}</html>", headers={"Content-Type": "text/html"}
        ),
        **SMOLNA,
    ),
    "investment_broken_json": case(
        INVESTMENT_TOOL,
        investment_answer(
            200, content=INJECTED.encode(), headers={"Content-Type": "application/json"}
        ),
        **SMOLNA,
    ),
    "investment_another_shape": case(
        INVESTMENT_TOOL, investment_answer(200, json={INJECTED: True}), **SMOLNA
    ),
    "investment_network_error": case(
        INVESTMENT_TOOL,
        lambda r: r.get(INVESTMENT).mock(side_effect=httpx.ConnectError(INJECTED)),
        **SMOLNA,
    ),
    "investment_history_404": case(
        INVESTMENT_TOOL, history_missing, investment_slug="smolna", include_history=True
    ),
    "investment_slug_capitals": case(INVESTMENT_TOOL, investment_routes, investment_slug="Smolna"),
    "investment_slug_path": case(INVESTMENT_TOOL, investment_routes, investment_slug="smolna/../x"),
    "investment_limit_201": case(
        INVESTMENT_TOOL, investment_routes, investment_slug="smolna", limit=201
    ),
    "investment_limit_float_text": case(
        INVESTMENT_TOOL, investment_routes, investment_slug="smolna", limit="5.0"
    ),
    "investment_limit_false": case(
        INVESTMENT_TOOL, investment_routes, investment_slug="smolna", limit=False
    ),
    "investment_403_then_locations": case(
        INVESTMENT_TOOL,
        (investment_answer(403), location_routes),
        then=(("search_locations", {"query": "krak"}),),
        **SMOLNA,
    ),
}
