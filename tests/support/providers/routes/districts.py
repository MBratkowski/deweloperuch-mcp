"""respx routes of a city's districts with offers (``city-districts``, offers variant), with
the real answer for Warszawa (``builders.districts``)."""

from typing import Any

import respx

from support.builders.districts import WARSZAWA_DISTRICTS_20261102
from support.providers.service import BASE

DISTRICTS = BASE + "/api/city-districts?citySlug=warszawa"
"""The request of the fixture."""


def districts_route(
    router: respx.MockRouter, found: Any = None, city: str = "warszawa"
) -> respx.Route:
    """The districts of ``city`` answer with the real ones of Warszawa, byte-exact, or, with
    ``found``, that JSON."""
    route = router.get(path="/api/city-districts", params={"citySlug": city})
    if found is None:
        return route.respond(
            200,
            content=WARSZAWA_DISTRICTS_20261102.read_bytes(),
            headers={"Content-Type": "application/json"},
        )
    return route.respond(200, json=found)
