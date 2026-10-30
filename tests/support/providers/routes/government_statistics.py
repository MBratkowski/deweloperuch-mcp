"""respx routes of the government statistics: the real pages
(tests/fixtures/rsc/stats_gov_*.rsc) at the route of the 2.0 build,
``/statystyki/{location}/dane-rzadowe``.
"""

import respx

from deweloperuch_mcp import identity
from support.providers.routes.offers import RSC_HEADERS
from support.providers.rsc import OFFERS_UNKNOWN_CITY, STATS_FIXTURES, raw

STATS_PATH = "/statystyki/{location}/dane-rzadowe"


def stats_path(location: str) -> str:
    """The path of the government statistics of ``location`` (no query)."""
    return STATS_PATH.format(location=location)


def stats_url(location: str, rest: str = "") -> str:
    """The page's URL on the service, with ``rest`` (an anchor or a query) after it."""
    return identity.BASE_URL + stats_path(location) + rest


UNKNOWN_LOCATION = "nieistniejaca-lokalizacja"


def stats_routes(router: respx.MockRouter) -> dict[str, respx.Route]:
    """The government statistics of ``polska`` and ``warszawa`` (pages of the build before
    2.0) and of ``wroclaw`` (2.0): their real pages, byte for byte
    (tests/fixtures/rsc/stats_gov_*.rsc). Other locations are not mocked."""
    return {
        location: router.get(path=stats_path(location)).respond(
            200, content=raw(path), headers=RSC_HEADERS
        )
        for location, path in STATS_FIXTURES.items()
    }


def unknown_location_route(router: respx.MockRouter) -> respx.Route:
    """``UNKNOWN_LOCATION`` answered the way the service answers an unknown city on the
    offers list (HTTP 200, Next.js's 404 marker, real payload). Whether the statistics
    page answers an unknown location the same way is [H]: the live suite finds out."""
    return router.get(path=stats_path(UNKNOWN_LOCATION)).respond(
        200, content=raw(OFFERS_UNKNOWN_CITY), headers=RSC_HEADERS
    )
