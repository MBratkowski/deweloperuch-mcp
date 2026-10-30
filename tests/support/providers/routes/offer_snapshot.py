"""respx routes of ``offer-snapshot``: Sopot and Kraków re-shaped from their real
``city-sales`` bodies (tests/fixtures/api/), Wrocław as the service sent it."""

import json
from pathlib import Path

import respx

from support.providers.rsc import CITY_SALES, OFFER_SNAPSHOT_WROCLAW

OFFER_SNAPSHOT_PATH = "/api/map/offer-snapshot/"
SNAPSHOT_HEADERS = {"Content-Type": "application/json"}
UNKNOWN_CITY_ANSWER = {"error": "Unknown city"}
"""[P 2026-10-30] the JSON 404 body for ``nieistniejace-miasto``."""
GONE_PAGE = b"<!DOCTYPE html><html><body><h1>404</h1></body></html>"
"""An HTML 404, what a route that is not there answers instead of the endpoint's JSON."""


def snapshot_of(city_sales: Path) -> bytes:
    """A ``city-sales`` body as an ``offer-snapshot`` body: the same investments and
    offers, each offer the row ``[id, investId, 0, amount, priceSqm, size, null]`` (status
    0 is active; the change since the first price is not in ``city-sales``)."""
    data = json.loads(city_sales.read_bytes())
    rows = [
        [sale["id"], sale["investId"], 0, sale["amount"], sale["priceSqm"], sale["size"], None]
        for sale in data["sales"]
    ]
    body = {"citySlug": data["citySlug"], "investments": data["investments"], "sales": rows}
    return json.dumps(body).encode()


def offer_snapshot_routes(router: respx.MockRouter) -> dict[str, respx.Route]:
    """Sopot and Kraków (the offers of their ``city-sales`` bodies) and Wrocław (byte for
    byte); ``nieznane`` answers the JSON 404 of an unknown city."""
    bodies = {city: snapshot_of(path) for city, path in CITY_SALES.items()}
    bodies["wroclaw"] = OFFER_SNAPSHOT_WROCLAW.read_bytes()
    routes = {
        city: router.get(path=OFFER_SNAPSHOT_PATH + city).respond(
            200, content=body, headers=SNAPSHOT_HEADERS
        )
        for city, body in bodies.items()
    }
    routes["nieznane"] = unknown_city_snapshot_route(router)
    return routes


def unknown_city_snapshot_route(router: respx.MockRouter, city: str = "nieznane") -> respx.Route:
    """The JSON 404 the service answers for a city it does not know [P 2026-10-30]."""
    return router.get(path=OFFER_SNAPSHOT_PATH + city).respond(404, json=UNKNOWN_CITY_ANSWER)


def gone_snapshot_route(router: respx.MockRouter, city: str = "sopot") -> respx.Route:
    """An HTML 404 for ``city``: the route itself is not there."""
    return router.get(path=OFFER_SNAPSHOT_PATH + city).respond(
        404, content=GONE_PAGE, headers={"Content-Type": "text/html; charset=utf-8"}
    )
