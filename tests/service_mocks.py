"""respx routes that answer like deweloperuch.pl, with bodies from the samples.

Shared by the adapter tests (CLI, MCP): they go through the real services and the real
client, so only the network is mocked. Paths and queries come from the samples'
``_request`` (``discovery_samples.request_target``).

The offers list answers with a real RSC response (tests/fixtures/rsc/): by default the
Warsaw page byte for byte; a test that needs other offers gets them spliced into that
same frame (``rsc_fixtures.offers_payload``), never a payload built from assumptions.
"""

import copy
from typing import Any

import respx

from deweloperuch_mcp import identity
from discovery_samples import body, request_target
from rsc_fixtures import OFFERS_UNKNOWN_CITY, UNKNOWN_CITY, offers_payload, raw

BASE = identity.BASE_URL
INVESTMENT = BASE + request_target("api.map_inv_visible")
INVESTMENT_EVENTS = BASE + request_target("api.inv_sale_events")
SALE_EVENTS = BASE + request_target("api.sale_events")


def offers_page(sample: str = "page.offers_list", *, count: int | None = None) -> Any:
    """The offers page of ``sample``; with ``count``, that many offers (copies of the
    sample's offers with new ids) and ``perPage`` = ``count``, as a full page would be."""
    page = body(sample)
    if count is not None:
        offers = page["data"]
        page["data"] = []
        for index in range(count):
            offer = copy.deepcopy(offers[index % len(offers)])
            offer["sale_id"] = 900_000 + index
            page["data"].append(offer)
        page["pagination"]["perPage"] = count
    return page


RSC_HEADERS = {"Content-Type": "text/x-component"}


def offers_route(router: respx.MockRouter, page: Any = None) -> respx.Route:
    """Every offers list page answers with the real Warsaw page (10 offers, total 13 324)
    or, with ``page``, with that ``initialData`` in the same real frame."""
    return router.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
        200, content=offers_payload(page), headers=RSC_HEADERS
    )


def unknown_city_route(router: respx.MockRouter) -> respx.Route:
    """The offers list of ``rsc_fixtures.UNKNOWN_CITY``: the real 200 without data, with
    Next.js's 404 marker. Add it before ``offers_route`` (the first match answers)."""
    return router.route(method="GET", path=f"/ceny-ofertowe/{UNKNOWN_CITY}/mieszkania").respond(
        200, content=raw(OFFERS_UNKNOWN_CITY), headers=RSC_HEADERS
    )


def location_routes(router: respx.MockRouter) -> tuple[respx.Route, respx.Route]:
    return (
        router.get(path="/api/cities").respond(200, json=body("api.cities_q")),
        router.get(path="/api/location-search").respond(200, json=body("api.location_search")),
    )


def investment_routes(
    router: respx.MockRouter, investment: Any = None
) -> tuple[respx.Route, respx.Route, respx.Route]:
    """The investment ``smolna`` (default: the sample), its history and offer 2377's."""
    return (
        router.get(INVESTMENT).respond(
            200, json=body("api.map_inv_visible") if investment is None else investment
        ),
        router.get(INVESTMENT_EVENTS).respond(200, json=body("api.inv_sale_events")),
        router.get(SALE_EVENTS).respond(200, json=body("api.sale_events")),
    )


def investment_with_offers(count: int) -> Any:
    """The ``smolna`` sample with ``count`` offers (copies of its offers with new ids)."""
    investment = body("api.map_inv_visible")
    offers = investment["sale"]
    investment["sale"] = []
    for index in range(count):
        offer = copy.deepcopy(offers[index % len(offers)])
        offer["sale_id"] = 800_000 + index
        investment["sale"].append(offer)
    return investment
