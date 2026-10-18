"""respx routes of a building of the price register, with the bodies of the samples.

- ``BUILDING``: ``23-marca-79c-sopot``, sample ``api.tx_visible`` (3 of its 86 units);
- ``TREND``: the trend around it. The one sample of a trend (``api.avg_trend_building``)
  was captured for another building (583284); it is a real answer of the service all
  the same, so it answers for this building too.
- ``CISNA_BUILDING`` and ``CISNA_TREND``: the building ``cisna`` and its trend, whole
  and byte for byte (tests/fixtures/api/, [P 2026-10-15]): 6 units with 7 transactions,
  one of them a share and one an enforcement sale, and a trend without quarters.
"""

import json
from pathlib import Path
from typing import Any

import respx

from support.paths import API_FIXTURES
from support.providers.samples import body, request_target
from support.providers.service import BASE

SLUG = "23-marca-79c-sopot"


BUILDING_ID = 1354
"""The sample's building number: the trend is asked for by it."""


BUILDING = BASE + request_target("api.tx_visible")


TREND = BASE + f"/api/avg-price-trend/building/{BUILDING_ID}"


UNKNOWN_BUILDING = "nieistniejacy-budynek"


BUILDING_PAGE = BASE + "/ceny-transakcyjne/sopot/adresy/" + SLUG


CISNA = "cisna"
"""A building of the register without a name or a street: its slug is its town's."""


CISNA_ID = 152198


CISNA_BUILDING = BASE + "/api/map/transactions/visible/" + CISNA


CISNA_TREND = BASE + f"/api/avg-price-trend/building/{CISNA_ID}"


CISNA_BODY = API_FIXTURES / "tx_visible_cisna_20261015.json"
"""5 ``transakcja``, 1 ``udzial`` (1/2) and 1 ``egzekucja``; the service's ``avg_*`` are
those of the 5 ``transakcja`` (tests/fixtures/api/README.md)."""


CISNA_TREND_BODY = API_FIXTURES / "avg_trend_building_152198_20261015.json"
"""``{"data":[],"radiusKm":0}``."""


JSON_TYPE = {"Content-Type": "application/json"}


def fixture_body(path: Path) -> Any:
    """A raw response of tests/fixtures/api/ as data, a fresh copy for every call."""
    return json.loads(path.read_bytes())


def building_routes(
    router: respx.MockRouter, building: Any = None
) -> tuple[respx.Route, respx.Route]:
    """The building (default: the sample) and the trend around it."""
    return (
        router.get(BUILDING).respond(
            200, json=body("api.tx_visible") if building is None else building
        ),
        router.get(TREND).respond(200, json=body("api.avg_trend_building")),
    )


def cisna_routes(router: respx.MockRouter, building: Any = None) -> tuple[respx.Route, respx.Route]:
    """The building ``cisna`` and its trend as the service sent them; ``building``
    answers instead of the building's own body."""
    answer = (
        dict(content=CISNA_BODY.read_bytes(), headers=JSON_TYPE)
        if building is None
        else dict(json=building)
    )
    return (
        router.get(CISNA_BUILDING).respond(200, **answer),
        router.get(CISNA_TREND).respond(
            200, content=CISNA_TREND_BODY.read_bytes(), headers=JSON_TYPE
        ),
    )
