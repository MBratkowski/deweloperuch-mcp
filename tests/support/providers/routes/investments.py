"""respx routes of an investment and its price history, with the bodies of the samples."""

from typing import Any

import respx

from support.providers.samples import body, request_target
from support.providers.service import BASE

INVESTMENT = BASE + request_target("api.map_inv_visible")


INVESTMENT_EVENTS = BASE + request_target("api.inv_sale_events")


SALE_EVENTS = BASE + request_target("api.sale_events")


def investment_routes(
    router: respx.MockRouter, investment: Any = None
) -> tuple[respx.Route, respx.Route, respx.Route]:
    """The investment ``smolna`` (default: the sample), its history and offer 2377's."""
    return (
        router.get(INVESTMENT).respond(
            200, json=body("api.map_inv_visible") if investment is None else investment
        ),
        router.get(INVESTMENT_EVENTS).respond(200, json=body("api.inv_sale_events")),
        router.get(SALE_EVENTS).respond(200, json=body("api.sale_events")),
    )
