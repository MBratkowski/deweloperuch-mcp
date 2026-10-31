"""respx routes of the developers' profiles: the real pages
(tests/fixtures/rsc/developer_*.rsc).
"""

import respx

from deweloperuch_mcp.flight import component_props
from support.providers.routes.offers import RSC_HEADERS
from support.providers.rsc import (
    DEVELOPER_ARCHICOM_2_0,
    DEVELOPER_POLSKA,
    DEVELOPER_UNKNOWN,
    DEVELOPER_WARSZAWA,
    UNKNOWN_DEVELOPER,
    raw,
    replace_prop,
)

DEVELOPERS_PATH = "/ceny-ofertowe/{city}/deweloperzy/{developer}"


DEVELOPER_PAGES = {
    ("warszawa", "atal"): DEVELOPER_WARSZAWA,
    ("polska", "atal"): DEVELOPER_POLSKA,
    ("warszawa", UNKNOWN_DEVELOPER): DEVELOPER_UNKNOWN,
    ("polska", "archicom"): DEVELOPER_ARCHICOM_2_0,
}
"""(city, developer) -> the real page of the developer's profile."""

WITHOUT_OFFERS_CITY = "bialystok"
"""The city of the page of a developer without active offers there."""


def without_offers(payload: bytes) -> bytes:
    """The page of a developer with no active offers in that city.

    The service writes 0 for the averages of such a page (``averagePrice``,
    ``averageSize``, ``avgAmountPerM2``) and lists no investment [P 2026-10-20] (live:
    ``atal`` in ``bialystok``); the real page of Warsaw with those figures replaced.
    """
    props = list(component_props(payload))
    data = next(value for name, value in props if name == "data" and isinstance(value, dict))
    edited = {
        **data,
        "investments": [],
        "filteredStats": {
            **data["filteredStats"],
            "totalProjects": 0,
            "totalSales": 0,
            "totalCities": 0,
            "averagePrice": 0,
            "averageSize": 0,
            "avgAmountPerM2": 0,
        },
    }
    return replace_prop(payload, "data", lambda value: isinstance(value, dict), edited)


def developer_routes(router: respx.MockRouter) -> dict[tuple[str, str], respx.Route]:
    """The profiles of ATAL in Warsaw and in the whole country and the page of an unknown
    developer in Warsaw, byte for byte (tests/fixtures/rsc/developer_*.rsc), plus the page
    of a developer without active offers in that city. Add them before ``offers_route``
    (it answers every ``/ceny-ofertowe/`` path)."""
    routes = {
        key: router.get(path=DEVELOPERS_PATH.format(city=key[0], developer=key[1])).respond(
            200, content=raw(path), headers=RSC_HEADERS
        )
        for key, path in DEVELOPER_PAGES.items()
    }
    routes[(WITHOUT_OFFERS_CITY, "atal")] = router.get(
        path=DEVELOPERS_PATH.format(city=WITHOUT_OFFERS_CITY, developer="atal")
    ).respond(200, content=without_offers(raw(DEVELOPER_WARSZAWA)), headers=RSC_HEADERS)
    return routes
