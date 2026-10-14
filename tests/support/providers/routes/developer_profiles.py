"""respx routes of the developers' profiles: the real pages
(tests/fixtures/rsc/developer_*.rsc).
"""

import respx

from support.providers.routes.offers import RSC_HEADERS
from support.providers.rsc import (
    DEVELOPER_POLSKA,
    DEVELOPER_UNKNOWN,
    DEVELOPER_WARSZAWA,
    UNKNOWN_DEVELOPER,
    raw,
)

DEVELOPERS_PATH = "/ceny-ofertowe/{city}/deweloperzy/{developer}"


DEVELOPER_PAGES = {
    ("warszawa", "atal"): DEVELOPER_WARSZAWA,
    ("polska", "atal"): DEVELOPER_POLSKA,
    ("warszawa", UNKNOWN_DEVELOPER): DEVELOPER_UNKNOWN,
}
"""(city, developer) -> the real page of the developer's profile."""


def developer_routes(router: respx.MockRouter) -> dict[tuple[str, str], respx.Route]:
    """The profiles of ATAL in Warsaw and in the whole country and the page of an unknown
    developer in Warsaw, byte for byte (tests/fixtures/rsc/developer_*.rsc). Add them
    before ``offers_route`` (it answers every ``/ceny-ofertowe/`` path)."""
    return {
        key: router.get(path=DEVELOPERS_PATH.format(city=key[0], developer=key[1])).respond(
            200, content=raw(path), headers=RSC_HEADERS
        )
        for key, path in DEVELOPER_PAGES.items()
    }
