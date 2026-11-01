"""How the 2.0 service answers what it no longer has, as respx answers
(``respond(404, **removed_route())``), and what the client says about it.

docs/discovery/endpoints.md section 9 [P 2026-10-30]: an unknown entity on a live JSON
route is a ``404`` ``application/json`` ``{"error": ...}``; a removed route is a ``404``
``text/html``, the Next.js not-found page (the same 36,628 B on every removed route, also
for a request that asks for JSON). docs/discovery/pages-rsc.md [P 2026-10-30]: a removed
page answers ``410``. Section 9, "Pages" [P 2026-10-31]: the statistics pages answer an
unknown location with a ``404`` ``text/x-component``. No sample exists (non-2xx), so the
bodies are the ones quoted there or printed by probe: the JSON whole, the pages only as
far as probe printed them.
"""

from typing import Any

INVESTMENT_NOT_FOUND_ERROR = {"error": "Investment not found"}
"""An unknown investment (``map/investments/visible``) and an unknown RCN building
(``map/transactions/visible``): 32 B."""

UNKNOWN_CITY_ERROR = {"error": "Unknown city"}
"""An unknown city (``avg-price-trend/city``): 24 B."""

NOT_FOUND_PAGE = (
    '<!DOCTYPE html><!--VDpA73sQ_GRMsEMdmIQtu--><html lang="pl"><head><meta charSet="utf-8"/>'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>'
    '<link rel="preload" href="/_next/static/media/26d0ba92e140f0dc-s.p.woff2"'
)
"""The start of the Next.js not-found page of a removed route, as probe printed it."""

UNKNOWN_LOCATION_PAGE = (
    '1:"$Sreact.fragment" 2:I[98202,["9124","static/chunks/9124-322df424d5a63671.js","3412",'
    '"static/chunks/3412-29621067006dac8f.js","7177","static/chunks/app/layout-f759e557877bd3cd'
    '.js"],"GoogleTagManager"] 3:I[67455,["9124","static/chunks/9124-322df424d5a63671.js","3412",'
    '"static/chunks/3412-29621067006'
)
"""The start of a statistics page's 404 for an unknown location, the same for
``/statystyki/nieistniejace-miasto/dane-rzadowe`` (24,757 B) and ``…/transakcje``
(25,204 B) [P 2026-10-31]: the first 300 characters as probe printed them, which joins the
rows of the flight stream with spaces."""


CHANGED_SERVICE = (
    "Narzędzie nie może pobrać tych danych, bo serwis przeniósł je w inne miejsce albo "
    "przestał je udostępniać. To nie musi znaczyć, że argumenty są błędne ani że szukanego "
    "obiektu nie ma. Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: "
    "zgłoś to użytkownikowi."
)
"""The client's message for a redirect, a ``410`` and a ``404`` that is no "unknown" answer
(D21), as a model and a person read it (product text, written out here on purpose)."""


def unknown_entity(error: dict[str, str] = INVESTMENT_NOT_FOUND_ERROR) -> dict[str, Any]:
    """The body of a live route's 404 about an entity it does not know."""
    return {"json": error}


def removed_route() -> dict[str, Any]:
    """The body and media type of the 404 of a route that no longer exists."""
    return {"text": NOT_FOUND_PAGE, "headers": {"Content-Type": "text/html"}}


def unknown_location_page() -> dict[str, Any]:
    """The body and media type of a statistics page's 404 for a location it does not know."""
    return {"text": UNKNOWN_LOCATION_PAGE, "headers": {"Content-Type": "text/x-component"}}
