"""respx routes of the valuation, with the body of the sample."""

from typing import Any

import respx

from support.providers.samples import body, request_target
from support.providers.service import BASE

VALUATION_PATH = "/api/standalone-valuation"


VALUATION = BASE + request_target("api.standalone_val")
"""The sample's request: a flat of 50 m² at Marszałkowska 100 in Warsaw, with the address."""


def valuation_route(router: respx.MockRouter, valuation: Any = None) -> respx.Route:
    """Every valuation answers with the sample ``api.standalone_val`` (3 transactions after
    trimming) or with ``valuation``."""
    answer = body("api.standalone_val") if valuation is None else valuation
    return router.get(path=VALUATION_PATH).respond(200, json=answer)
