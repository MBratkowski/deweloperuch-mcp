"""respx routes of ``offer-snapshot`` (D20): the real bodies of tests/fixtures/api/ with
their headers, the service's answer about a city it does not know, and two answers of a
changed service.

docs/discovery/endpoints.md section 2 [P 2026-10-31]: ``sopot`` (880 B, 8 offers) and
``warszawa`` (532,198 B, 11,672 offers) with ``Cache-Control: public, max-age=172800,
s-maxage=3600, stale-while-revalidate=86400``; ``wroclaw`` [P 2026-10-30, PR #16]
(261,340 B, 5,836 offers), served with the same headers; section 9 [P 2026-10-31]: an
unknown city is a ``404`` ``application/json`` ``{"error":"Unknown city"}``.
"""

import json
from typing import Any

import respx

from support.paths import API_FIXTURES
from support.providers.error_answers import UNKNOWN_CITY_ERROR, removed_route, unknown_entity
from support.providers.rsc import UNKNOWN_CITY

OFFER_SNAPSHOT_PATH = "/api/map/offer-snapshot/"

OFFER_SNAPSHOT = {
    "sopot": API_FIXTURES / "offer_snapshot_sopot_20261031.json",
    "warszawa": API_FIXTURES / "offer_snapshot_warszawa_20261031.json",
    "wroclaw": API_FIXTURES / "offer_snapshot_wroclaw_20261030.json",
}
"""City -> its real ``/api/map/offer-snapshot/{city}`` body, captured on 2026-10-31
(``wroclaw`` on 2026-10-30, with the package's client, in PR #16)."""

OFFER_SNAPSHOT_HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "public, max-age=172800, s-maxage=3600, stale-while-revalidate=86400",
}


def snapshot(city: str) -> Any:
    """The real snapshot of ``city`` as JSON data, whole (a test may change one thing)."""
    return json.loads(OFFER_SNAPSHOT[city].read_bytes())


def offer_snapshot_routes(router: respx.MockRouter) -> dict[str, respx.Route]:
    """The real snapshots of Sopot, Warszawa and Wrocław, byte for byte, with headers, and
    ``UNKNOWN_CITY`` (the slug the recon asked for), which the service does not know."""
    routes = {
        city: router.get(path=OFFER_SNAPSHOT_PATH + city).respond(
            200, content=path.read_bytes(), headers=OFFER_SNAPSHOT_HEADERS
        )
        for city, path in OFFER_SNAPSHOT.items()
    }
    routes[UNKNOWN_CITY] = router.get(path=OFFER_SNAPSHOT_PATH + UNKNOWN_CITY).respond(
        404, **unknown_entity(UNKNOWN_CITY_ERROR)
    )
    return routes


def removed_snapshot_route(router: respx.MockRouter) -> respx.Route:
    """Sopot's snapshot answered as a removed route answers: the HTML not-found page (D21)."""
    return router.get(path=OFFER_SNAPSHOT_PATH + "sopot").respond(404, **removed_route())


def changed_snapshot_route(router: respx.MockRouter) -> respx.Route:
    """Sopot's real snapshot with its first sale cut to 6 items (position 2 taken out): a
    layout the client cannot read by position (D21)."""
    data = snapshot("sopot")
    del data["sales"][0][2]
    return router.get(path=OFFER_SNAPSHOT_PATH + "sopot").respond(
        200, json=data, headers=OFFER_SNAPSHOT_HEADERS
    )
