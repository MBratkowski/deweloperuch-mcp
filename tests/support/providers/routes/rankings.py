"""respx routes of the transaction rankings of cities and powiats, with the bodies of the
samples.
"""

from typing import Any

import respx

from support.providers.samples import body, request_target
from support.providers.service import BASE

CITY_RANKING = BASE + request_target("api.city_tx_stats")


POWIAT_RANKING = BASE + request_target("api.powiat_stats")


def ranking_routes(
    router: respx.MockRouter, cities: Any = None, powiats: Any = None
) -> tuple[respx.Route, respx.Route]:
    """The rankings of cities and powiats: the samples (3 places each) or, with
    ``cities`` and ``powiats``, those bodies."""
    return (
        router.get(CITY_RANKING).respond(
            200, json=body("api.city_tx_stats") if cities is None else cities
        ),
        router.get(POWIAT_RANKING).respond(
            200, json=body("api.powiat_stats") if powiats is None else powiats
        ),
    )
