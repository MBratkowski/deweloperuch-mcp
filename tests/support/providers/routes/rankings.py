"""respx routes of the transaction rankings of cities and powiats, with the bodies of the
samples or of the complete answers of 2026-10-15 (tests/fixtures/api/).
"""

import json
from pathlib import Path
from typing import Any

import respx

from support.paths import API_FIXTURES
from support.providers.samples import body, request_target
from support.providers.service import BASE

CITY_RANKING = BASE + request_target("api.city_tx_stats")


POWIAT_RANKING = BASE + request_target("api.powiat_stats")


CITIES_2026_10_15 = API_FIXTURES / "city_tx_stats_20261015.json"
"""Every place of ``/api/city-transaction-stats`` on 2026-10-15: 2529, one of them with
0 as its price per m², area and price (tests/fixtures/api/README.md)."""


POWIATS_2026_10_15 = API_FIXTURES / "powiat_stats_20261015.json"
"""Every powiat of ``/api/map/powiat-stats`` on 2026-10-15: 380, none with a 0."""


def captured(path: Path) -> Any:
    """The body of a complete answer of tests/fixtures/api/, as the service sent it."""
    return json.loads(path.read_bytes())


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


def captured_ranking_routes(router: respx.MockRouter) -> tuple[respx.Route, respx.Route]:
    """The rankings of cities and powiats as the service answered on 2026-10-15, in full."""
    return ranking_routes(
        router, cities=captured(CITIES_2026_10_15), powiats=captured(POWIATS_2026_10_15)
    )
