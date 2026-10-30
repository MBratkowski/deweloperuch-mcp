"""respx routes of the offers list: the real RSC pages (tests/fixtures/rsc/), byte for
byte; a test that needs other offers gets them spliced into the same real frame
(``rsc.offers_payload``), never a payload built from assumptions.
"""

from typing import Any

import respx

from support.providers.rsc import (
    OFFERS_UNKNOWN_CITY,
    OFFERS_WROCLAW_2_0,
    UNKNOWN_CITY,
    offers_payload,
    raw,
)
from support.providers.samples import body

RSC_HEADERS = {"Content-Type": "text/x-component"}


def offers_route(router: respx.MockRouter, page: Any = None) -> respx.Route:
    """Every offers list page answers with the real Warsaw page (10 offers, total 13 324)
    or, with ``page``, with that ``initialData`` in the same real frame."""
    return router.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
        200, content=offers_payload(page), headers=RSC_HEADERS
    )


def unknown_city_route(router: respx.MockRouter) -> respx.Route:
    """The offers list of ``rsc.UNKNOWN_CITY``: the real 200 without data, with
    Next.js's 404 marker. Add it before ``offers_route`` (the first match answers)."""
    return router.route(method="GET", path=f"/ceny-ofertowe/{UNKNOWN_CITY}/mieszkania").respond(
        200, content=raw(OFFERS_UNKNOWN_CITY), headers=RSC_HEADERS
    )


def wroclaw_offers_route(router: respx.MockRouter) -> respx.Route:
    """The offers list of Wrocław as the 2.0 build serves it (``sales``,
    ``serverPaginationData``), byte for byte. Add it before ``offers_route``."""
    return router.route(method="GET", path="/ceny-ofertowe/wroclaw/mieszkania").respond(
        200, content=raw(OFFERS_WROCLAW_2_0), headers=RSC_HEADERS
    )


def sample_offers_route(service: respx.MockRouter, sample: str = "page.offers_list") -> respx.Route:
    """Every offers list page answers with ``sample`` spliced into the real Warsaw frame."""
    return service.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
        200,
        content=offers_payload(body(sample)),
        headers={"Content-Type": "text/x-component"},
    )
