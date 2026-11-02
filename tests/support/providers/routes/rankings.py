"""respx routes of the rankings: the transactions of cities and powiats and the indicators
of cities, with the bodies of the samples or of the complete answers of tests/fixtures/api/.
"""

import json
from pathlib import Path
from typing import Any

import respx

from support.paths import API_FIXTURES
from support.providers.samples import body, request_target
from support.providers.service import BASE

CITY_RANKING = BASE + request_target("api.city_tx_stats")


POWIAT_RANKING = BASE + request_target("api.powiat_map_stats")


CITY_INDICATORS = BASE + request_target("api.gov_map_stats")


CITIES_2026_10_15 = API_FIXTURES / "city_tx_stats_20261015.json"
"""Every place of ``/api/city-transaction-stats`` on 2026-10-15: 2529, one of them with
0 as its price per m², area and price (tests/fixtures/api/README.md)."""


POWIATS_2026_11_02 = API_FIXTURES / "powiat_map_stats_20261102.json"
"""Every powiat of ``/api/statystyki/powiat-map-stats`` on 2026-11-02: 380, the primary
market null in 70 of them, the secondary in 16, both in 3."""


INDICATORS_2026_11_02 = API_FIXTURES / "gov_map_stats_20261102.json"
"""The 66 cities of ``/api/statystyki/gov-map-stats`` on 2026-11-02, NBP prices in 17."""


TX_CITIES_2026_11_02 = API_FIXTURES / "tx_cities_20261102.json"
"""The 16,283 rows of ``/api/map/tx-cities`` on 2026-11-02, trimmed to ``slug``, ``name``,
``powiatId`` and ``powiat`` (tests/fixtures/api/README.md)."""


def captured(path: Path) -> Any:
    """The body of a complete answer of tests/fixtures/api/, as the service sent it."""
    return json.loads(path.read_bytes())


def ranking_routes(
    router: respx.MockRouter, cities: Any = None, powiats: Any = None, indicators: Any = None
) -> tuple[respx.Route, respx.Route, respx.Route]:
    """The rankings of cities and powiats and the indicators of cities: the samples (3
    places each) or, when given, those bodies."""
    return (
        router.get(CITY_RANKING).respond(
            200, json=body("api.city_tx_stats") if cities is None else cities
        ),
        router.get(POWIAT_RANKING).respond(
            200, json=body("api.powiat_map_stats") if powiats is None else powiats
        ),
        router.get(CITY_INDICATORS).respond(
            200, json=body("api.gov_map_stats") if indicators is None else indicators
        ),
    )


def captured_ranking_routes(
    router: respx.MockRouter,
) -> tuple[respx.Route, respx.Route, respx.Route]:
    """The three as the service answered in full: the cities on 2026-10-15, the powiats and
    the indicators on 2026-11-02."""
    return ranking_routes(
        router,
        cities=captured(CITIES_2026_10_15),
        powiats=captured(POWIATS_2026_11_02),
        indicators=captured(INDICATORS_2026_11_02),
    )
