"""respx routes of the offers list: the real 2.0 pages (tests/fixtures/rsc/), a page in
their real frame (``rsc.offers_payload``), never a payload built from assumptions.
"""

from typing import Any

import respx

from support.builders.offers import MOKOTOW_OFFERS, offers_page
from support.providers.rsc import (
    OFFERS_UNKNOWN_CITY_20261031,
    OFFERS_UNKNOWN_DISTRICT_20261031,
    OFFERS_WARSZAWA_MOKOTOW_20261031,
    UNKNOWN_CITY,
    offers_payload,
    raw,
)

RSC_HEADERS = {"Content-Type": "text/x-component"}


def offers_route(router: respx.MockRouter, page: Any = None) -> respx.Route:
    """Every offers list (of a city or of a district) answers with the real page of Warszawa
    in the size the search asks for by default: its first 10 offers, ``perPage`` 10, total
    11,672 (``offers_page()``); with ``page`` (the props ``sales`` and
    ``serverPaginationData``), that page in the same real frame."""
    content = offers_payload(offers_page() if page is None else page)
    return router.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
        200, content=content, headers=RSC_HEADERS
    )


def unknown_city_route(router: respx.MockRouter) -> respx.Route:
    """The offers list of ``rsc.UNKNOWN_CITY``: the real 200 without data, with
    Next.js's 404 marker [P 2026-10-31]. Add it before ``offers_route`` (the first match
    answers)."""
    return router.route(method="GET", path=f"/ceny-ofertowe/{UNKNOWN_CITY}/mieszkania").respond(
        200, content=raw(OFFERS_UNKNOWN_CITY_20261031), headers=RSC_HEADERS
    )


def district_route(router: respx.MockRouter) -> respx.Route:
    """The list of the district Mokotów of Warszawa in the size the search asks for by
    default: its first 10 real offers, ``perPage`` 10, total 959, in the real frame of the
    district's page [P 2026-10-31] (the raw page, 25 offers, is the contract tests').
    Add it before ``offers_route``."""
    frame = OFFERS_WARSZAWA_MOKOTOW_20261031
    content = offers_payload(offers_page(total=MOKOTOW_OFFERS, frame=frame), frame)
    return router.route(method="GET", path="/ceny-ofertowe/warszawa/mokotow/mieszkania").respond(
        200, content=content, headers=RSC_HEADERS
    )


def unknown_district_route(router: respx.MockRouter) -> respx.Route:
    """The list of the district ``builders.offers.UNKNOWN_DISTRICT`` of Warszawa (its slug
    ``nieistniejaca-dzielnica``): the real 200 without data, with Next.js's 404 marker
    [P 2026-10-31]. Add it before ``offers_route``."""
    path = "/ceny-ofertowe/warszawa/nieistniejaca-dzielnica/mieszkania"
    return router.route(method="GET", path=path).respond(
        200, content=raw(OFFERS_UNKNOWN_DISTRICT_20261031), headers=RSC_HEADERS
    )
