"""respx routes of the developer search, with the body of the sample."""

from typing import Any

import respx

from support.providers.samples import body, request_target
from support.providers.service import BASE

DEVELOPERS = BASE + request_target("api.developers_q")
"""The developer search as the sample asked it: ``q=atal&limit=5``."""


def developer_search_route(router: respx.MockRouter, found: Any = None) -> respx.Route:
    """Every developer search answers with the sample (ATAL) or, with ``found``, that."""
    return router.get(path="/api/developers").respond(
        200, json=body("api.developers_q") if found is None else found
    )
