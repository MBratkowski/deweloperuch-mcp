"""The golden cases of ``deweloperuch investments get`` (tests/golden/cli/<case>.json)."""

import httpx

from support.builders.investments import investment_with_offers
from support.golden.cli import (
    ESCAPES,
    INJECTED_BODY,
    Case,
    case,
    history_missing,
    investment_changed,
    investment_fail,
    mixed_statuses,
)
from support.golden.routes import investment_answer, investment_is
from support.providers.routes.investments import (
    investment_routes,
)
from support.providers.samples import body

CASES: dict[str, Case] = {
    "help_investments_get": case("investments", "get", "--help"),
    # investments get
    "investments_get": case("investments", "get", "smolna", service=investment_routes),
    "investments_get_json": case(
        "investments", "get", "smolna", "--json", service=investment_routes
    ),
    "investments_get_history": case(
        "investments", "get", "smolna", "--history", service=investment_routes
    ),
    "investments_get_history_json": case(
        "investments", "get", "smolna", "--history", "--json", service=investment_routes
    ),
    "investments_get_history_limit_1": case(
        "investments", "get", "smolna", "--history", "--limit", "1", service=investment_routes
    ),
    "investments_get_limit_0": case(
        "investments", "get", "smolna", "--limit", "0", service=investment_routes
    ),
    "investments_get_limit_2_json": case(
        "investments", "get", "smolna", "--limit", "2", "--json", service=investment_routes
    ),
    "investments_get_many_offers_limit_5": case(
        "investments",
        "get",
        "smolna",
        "--limit",
        "5",
        service=investment_is(investment_with_offers(30)),
    ),
    "investments_get_active_first": case(
        "investments", "get", "smolna", service=investment_is(mixed_statuses())
    ),
    "investments_get_without_street_and_coordinates": case(
        "investments",
        "get",
        "smolna",
        service=investment_is(investment_changed(street="", latitude="", longitude=None)),
    ),
    "investments_get_without_developer_slug": case(
        "investments",
        "get",
        "smolna",
        "--json",
        service=investment_is(
            investment_changed(developer=dict(body("api.map_inv_visible")["developer"], slug=""))
        ),
    ),
    "investments_get_without_currency": case(
        "investments",
        "get",
        "smolna",
        service=investment_is(investment_changed(currency="", avg_amount="", avg_size=None)),
    ),
    "investments_get_404": case("investments", "get", "smolna", service=investment_answer(404)),
    "investments_get_500": case(
        "investments", "get", "smolna", service=investment_answer(500, text=INJECTED_BODY)
    ),
    "investments_get_escapes_in_the_body": case(
        "investments", "get", "smolna", service=investment_answer(500, text=ESCAPES)
    ),
    "investments_get_403": case("investments", "get", "smolna", service=investment_answer(403)),
    "investments_get_429": case(
        "investments",
        "get",
        "smolna",
        service=investment_answer(429, headers={"Retry-After": "1"}, text="the body"),
    ),
    "investments_get_redirect": case(
        "investments",
        "get",
        "smolna",
        service=investment_answer(301, headers={"Location": "/api/elsewhere"}),
    ),
    "investments_get_html": case(
        "investments",
        "get",
        "smolna",
        service=investment_answer(
            200, text=f"<html>{INJECTED_BODY}</html>", headers={"Content-Type": "text/html"}
        ),
    ),
    "investments_get_broken_json": case(
        "investments",
        "get",
        "smolna",
        service=investment_answer(
            200, content=INJECTED_BODY.encode(), headers={"Content-Type": "application/json"}
        ),
    ),
    "investments_get_another_shape": case(
        "investments", "get", "smolna", service=investment_answer(200, json={"unexpected": True})
    ),
    "investments_get_network_error": case(
        "investments", "get", "smolna", service=investment_fail(httpx.ConnectError(INJECTED_BODY))
    ),
    "investments_get_history_404": case(
        "investments", "get", "smolna", "--history", service=history_missing
    ),
    "investments_get_slug_capitals": case("investments", "get", "Smolna"),
    "investments_get_slug_path": case("investments", "get", "smolna/../x"),
    "investments_get_limit_text": case("investments", "get", "smolna", "--limit", "x"),
    "investments_get_limit_negative": case("investments", "get", "smolna", "--limit", "-1"),
}
