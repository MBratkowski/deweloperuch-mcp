"""respx routes of an investment and its offers' price histories, with the bodies of the
samples or of the 2.0 capture of ``smolna``."""

import json
from typing import Any

import respx

from support.paths import API_FIXTURES
from support.providers.error_answers import removed_route
from support.providers.samples import body, request_target
from support.providers.service import BASE

INVESTMENT = BASE + request_target("api.map_inv_visible")


INVESTMENT_EVENTS = BASE + request_target("api.inv_sale_events")
"""The price events of every offer by the investment's id: a route the service removed in
2.0 (docs/discovery/endpoints.md, section 8). Nothing may request it any more."""


SALE_EVENTS = BASE + request_target("api.sale_events")


SMOLNA_2026_10_31 = API_FIXTURES / "map_inv_visible_smolna_20261031.json"
"""The whole 2.0 answer for ``smolna``, byte for byte (tests/fixtures/api/README.md): 17
offers, each with its price events (``ev``). The sample ``api.map_inv_visible`` is the
answer of 2026-10-09, before 2.0: 3 of 16 offers, no events."""


def smolna_with_events() -> Any:
    """The 2.0 answer for ``smolna`` as the service sent it, parsed (a fresh copy)."""
    return json.loads(SMOLNA_2026_10_31.read_text(encoding="utf-8"))


def investment_routes(
    router: respx.MockRouter, investment: Any = None
) -> tuple[respx.Route, respx.Route, respx.Route]:
    """The investment ``smolna`` (default: the sample, without price events), the removed
    route of its offers' events (the HTML 404 the service sends, D21) and offer 2377's
    history."""
    return (
        router.get(INVESTMENT).respond(
            200, json=body("api.map_inv_visible") if investment is None else investment
        ),
        router.get(INVESTMENT_EVENTS).respond(404, **removed_route()),
        router.get(SALE_EVENTS).respond(200, json=body("api.sale_events")),
    )
