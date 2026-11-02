"""respx routes of the developers' profiles: the real 2.0 pages of 2026-10-31
(tests/fixtures/rsc/developer_*_20261031.rsc).
"""

import respx

from deweloperuch_mcp.flight import component_props
from support.providers.routes.city_lookup import KNOWN_CITY, city_lookup_routes
from support.providers.routes.offers import RSC_HEADERS
from support.providers.rsc import (
    DEVELOPER_CERES_WARSZAWA_20261031,
    DEVELOPER_DOM_DEVELOPMENT_WARSZAWA_20261031,
    DEVELOPER_POLSKA_20261031,
    DEVELOPER_UNKNOWN_20261031,
    DEVELOPER_UNKNOWN_CITY_20261102,
    DEVELOPER_UNKNOWN_POLSKA_20261031,
    DEVELOPER_WARSZAWA_20261031,
    UNKNOWN_CITY,
    UNKNOWN_DEVELOPER,
    raw,
    replace_prop,
)

DEVELOPERS_PATH = "/ceny-ofertowe/{city}/deweloperzy/{developer}"


DEVELOPER_PAGES = {
    ("warszawa", "atal"): DEVELOPER_WARSZAWA_20261031,
    ("polska", "atal"): DEVELOPER_POLSKA_20261031,
    ("warszawa", "ceres-development"): DEVELOPER_CERES_WARSZAWA_20261031,
    ("warszawa", "dom-development"): DEVELOPER_DOM_DEVELOPMENT_WARSZAWA_20261031,
    ("warszawa", UNKNOWN_DEVELOPER): DEVELOPER_UNKNOWN_20261031,
    ("polska", UNKNOWN_DEVELOPER): DEVELOPER_UNKNOWN_POLSKA_20261031,
    (UNKNOWN_CITY, "atal"): DEVELOPER_UNKNOWN_CITY_20261102,
}
"""(city, developer) -> the real page of the developer's profile."""

WITHOUT_OFFERS_CITY = "bialystok"
"""The city of the page of a developer without active offers there."""


def without_offers(payload: bytes) -> bytes:
    """The page of a developer with no active offers in that city: the real page of Warsaw
    without investments.

    [P 2026-10-20] the 1.0 page of such a developer (live: ``atal`` in ``bialystok``)
    listed no investment; how the 2.0 page shows it was not seen [H] (an empty
    ``investments``, as here, or Next.js's 404 marker; the live suite asks a known developer
    in an unknown city). The chart of cities is the developer's, whatever the city.
    """
    return replace_prop(payload, "investments", lambda value: isinstance(value, list), [])


def without_cities_chart(payload: bytes) -> bytes:
    """The page with its chart of cities renamed, as if the service had dropped it (the
    page of a developer in one city has none [P 2026-10-31])."""
    assert payload.count(b'"ceny-w-miastach"') == 1
    return payload.replace(b'"ceny-w-miastach"', b'"ceny-w-regionach"')


def with_cities_reversed(payload: bytes) -> bytes:
    """The page with the rows of its chart of cities in the opposite order (the service
    lists them by price per m², a result by active offers)."""
    rows = next(
        value
        for name, value in component_props(payload)
        if name == "spec" and isinstance(value, dict) and value.get("id") == "ceny-w-miastach"
    )["views"][""]["rows"]
    return replace_prop(payload, "rows", lambda value: value == rows, list(reversed(rows)))


def developer_routes(router: respx.MockRouter) -> dict[tuple[str, str], respx.Route]:
    """The profiles of ATAL in Warsaw and in the whole country, of Ceres Development (one
    city, no chart of cities) and Dom Development in Warsaw, and the pages of an unknown
    developer in Warsaw and in the whole country, byte for byte
    (tests/fixtures/rsc/developer_*_20261031.rsc), ATAL in a city the service does not know
    (T39, tests/fixtures/rsc/developer_unknown_city_20261102.rsc) with the place lookup that
    follows it (``city_lookup_routes``), plus the page of a developer without active offers
    in that city. Add them before ``offers_route`` (it answers every ``/ceny-ofertowe/``
    path)."""
    city_lookup_routes(router)
    routes = {
        key: router.get(path=DEVELOPERS_PATH.format(city=key[0], developer=key[1])).respond(
            200, content=raw(path), headers=RSC_HEADERS
        )
        for key, path in DEVELOPER_PAGES.items()
    }
    routes[(WITHOUT_OFFERS_CITY, "atal")] = router.get(
        path=DEVELOPERS_PATH.format(city=WITHOUT_OFFERS_CITY, developer="atal")
    ).respond(200, content=without_offers(raw(DEVELOPER_WARSZAWA_20261031)), headers=RSC_HEADERS)
    return routes


def known_place_without_offers_route(router: respx.MockRouter) -> respx.Route:
    """ATAL's page in ``city_lookup.KNOWN_CITY`` answered as a page of a place where the
    service shows nothing of the developer: the real T39 page
    (tests/fixtures/rsc/developer_unknown_city_20261102.rsc), whose redirect to ATAL's page
    for the whole country is the same whatever the city. [P 2026-11-02, live e2e
    ``test_developer_in_a_known_place_without_its_offers``] a known place without the
    developer's offers is "not found" too; which marker its page carried was not recorded.
    Add it before ``offers_route``."""
    path = DEVELOPERS_PATH.format(city=KNOWN_CITY, developer="atal")
    return router.get(path=path).respond(
        200, content=raw(DEVELOPER_UNKNOWN_CITY_20261102), headers=RSC_HEADERS
    )
