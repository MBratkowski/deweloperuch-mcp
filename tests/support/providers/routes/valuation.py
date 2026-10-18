"""respx routes of the valuation, with the body of the sample or of the Cisna capture."""

import json
from typing import Any

import respx

from support.paths import API_FIXTURES
from support.providers.samples import body, request_target
from support.providers.service import BASE

VALUATION_PATH = "/api/standalone-valuation"


VALUATION = BASE + request_target("api.standalone_val")
"""The sample's request: a flat of 50 m² at Marszałkowska 100 in Warsaw, with the address."""


CISNA = API_FIXTURES / "standalone_val_cisna_20261015.json"
"""The whole answer for a flat of 50 m² in Cisna (49.2167, 22.3333), byte for byte
(tests/fixtures/api/README.md): an estimate from 2 transactions, with the radius at the
service's widest (1000 m)."""


def cisna() -> Any:
    """The Cisna capture as the service sent it, parsed."""
    return json.loads(CISNA.read_text(encoding="utf-8"))


def valuation_route(router: respx.MockRouter, valuation: Any = None) -> respx.Route:
    """Every valuation answers with the sample ``api.standalone_val`` (3 transactions after
    trimming) or with ``valuation``."""
    answer = body("api.standalone_val") if valuation is None else valuation
    return router.get(path=VALUATION_PATH).respond(200, json=answer)


def cisna_route(router: respx.MockRouter) -> respx.Route:
    """Every valuation answers with the Cisna capture, byte for byte."""
    return router.get(path=VALUATION_PATH).respond(
        200, content=CISNA.read_bytes(), headers={"Content-Type": "application/json"}
    )
