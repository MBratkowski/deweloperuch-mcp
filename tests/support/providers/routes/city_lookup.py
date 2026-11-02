"""respx routes of ``city-lookup`` with ``source=transactions``: the real answers about a
slug the service does not know and about two places it knows, and a lookup that fails.

docs/discovery/endpoints.md, ``city-lookup``: an unknown place is a 200 with both fields
null [P 2026-11-01, a name; P 2026-11-02, the slug of ``UNKNOWN_SLUG_LOOKUP``]; ``krakow``
[P 2026-10-30, sample ``api.city_lookup.slug_transactions``] and the village
``ignatki-osiedle`` [P 2026-11-01, sample ``api.city_lookup.village_transactions``] answer
with the register's name. Cache-Control of the 2026-11 answers:
``public, max-age=172800, s-maxage=86400, stale-while-revalidate=604800``.

A slug with no real answer here (``warszawa``, ``sopot``...) is no route: a test that needs
its lookup says what it gets, the failure of ``failed_lookup_route`` (the first "not found"
stands, ``PlaceCheck``); otherwise the request is "not mocked" and the test fails, so no
real city ever reads as unknown by accident.
"""

import httpx
import respx

from support.fakes.places import unknown_place_message
from support.paths import API_FIXTURES
from support.providers.rsc import UNKNOWN_CITY
from support.providers.samples import body

CITY_LOOKUP_PATH = "/api/city-lookup"

VILLAGE = "ignatki-osiedle"
"""A village the transactions dictionary knows (its sample). Offline tests pair it with a
mocked "not found" of a tool; live it has offers (12 in the answer of
``get_market_statistics(city="ignatki-osiedle")``, live e2e of 2026-11-02)."""

KNOWN_CITY = "krakow"
"""A city the transactions dictionary knows as „Kraków” (its sample): the known place of
the goldens."""

UNKNOWN_SLUG_LOOKUP = API_FIXTURES / "city_lookup_unknown_slug_20261102.json"
"""``/api/city-lookup?slug=nieistniejace-miasto&source=transactions``, captured on
2026-11-02 with the package's client: ``{"city":null,"city_slug":null}``."""

UNKNOWN_PLACE_MESSAGE = unknown_place_message(UNKNOWN_CITY)
"""What a tool says after the service's "not found" about ``UNKNOWN_CITY`` (``PlaceCheck``),
without an operation's own ending."""

NO_ANSWER = "city-lookup: the lookup failed (tests)"
"""The network failure of ``failed_lookup_route``."""

CITY_LOOKUP_HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "public, max-age=172800, s-maxage=86400, stale-while-revalidate=604800",
}


def _by_slug(router: respx.MockRouter, slug: str) -> respx.Route:
    return router.get(path=CITY_LOOKUP_PATH, params={"slug": slug, "source": "transactions"})


def city_lookup_routes(router: respx.MockRouter) -> dict[str, respx.Route]:
    """``UNKNOWN_CITY`` (the slug of the captured answer), unknown to the service, and
    ``KNOWN_CITY`` and ``VILLAGE``, which it knows; each asked by slug in the transactions
    dictionary and answered as the service did."""
    return {
        UNKNOWN_CITY: _by_slug(router, UNKNOWN_CITY).respond(
            200, content=UNKNOWN_SLUG_LOOKUP.read_bytes(), headers=CITY_LOOKUP_HEADERS
        ),
        KNOWN_CITY: _by_slug(router, KNOWN_CITY).respond(
            200, json=body("api.city_lookup.slug_transactions"), headers=CITY_LOOKUP_HEADERS
        ),
        VILLAGE: _by_slug(router, VILLAGE).respond(
            200, json=body("api.city_lookup.village_transactions"), headers=CITY_LOOKUP_HEADERS
        ),
    }


def failed_lookup_route(router: respx.MockRouter, slug: str) -> respx.Route:
    """The lookup of ``slug`` gets no answer (a network failure, ``NO_ANSWER``): the case of
    a lookup that cannot tell, after which the first "not found" stands."""
    return _by_slug(router, slug).mock(side_effect=httpx.ConnectError(NO_ANSWER))
