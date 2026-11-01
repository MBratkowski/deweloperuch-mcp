"""respx routes of the government statistics: the real 2.0 pages
(tests/fixtures/rsc/stats_gov_*_20261031.rsc) at ``/statystyki/{location}/dane-rzadowe``.
"""

import respx

from support.providers.error_answers import unknown_location_page
from support.providers.routes.offers import RSC_HEADERS
from support.providers.rsc import (
    STATS_GOV_7_MIAST_20261031,
    STATS_GOV_POLSKA_20261031,
    STATS_GOV_WARSZAWA_20261031,
    raw,
)

STATS_PAGES = {
    "polska": STATS_GOV_POLSKA_20261031,
    "warszawa": STATS_GOV_WARSZAWA_20261031,
    "7-miast": STATS_GOV_7_MIAST_20261031,
}
"""Location -> its real 2.0 page: the whole country, a city with NBP prices, an aggregate."""

UNKNOWN_LOCATION = "nieistniejaca-lokalizacja"


def stats_path(location: str) -> str:
    """The page of ``location`` (the route of ``GovernmentStatisticsApi``)."""
    return f"/statystyki/{location}/dane-rzadowe"


def stats_routes(router: respx.MockRouter) -> dict[str, respx.Route]:
    """The government statistics of ``STATS_PAGES``: their real pages, byte for byte.
    Other locations are not mocked."""
    return {
        location: router.get(path=stats_path(location)).respond(
            200, content=raw(page), headers=RSC_HEADERS
        )
        for location, page in STATS_PAGES.items()
    }


def unknown_location_route(router: respx.MockRouter) -> respx.Route:
    """``UNKNOWN_LOCATION`` answered as the statistics pages answer a location they do not
    know [P 2026-10-31]: a 404 whose body is a flight stream (``text/x-component``)."""
    return router.get(path=stats_path(UNKNOWN_LOCATION)).respond(404, **unknown_location_page())
