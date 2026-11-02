"""respx routes of the transaction statistics: the statistics page of a city (months, as
RSC; the real page of Warsaw, tests/fixtures/rsc/stats_tx_warszawa_20261031.rsc) and
``api.avg_trend_city`` (Warsaw, quarters).
"""

from typing import Any

import respx

from support.providers.error_answers import (
    UNKNOWN_CITY_ERROR,
    unknown_entity,
    unknown_location_page,
)
from support.providers.routes.city_lookup import city_lookup_routes
from support.providers.routes.offers import RSC_HEADERS
from support.providers.rsc import STATS_TX_WARSZAWA_20261031, raw
from support.providers.samples import body, request_target
from support.providers.service import BASE

STATS_PAGE = r"^/statystyki/[^/]+/transakcje$"
"""The path of every city's statistics page (``path__regex``)."""


STATS_PAGE_WARSZAWA = BASE + request_target("page.stats_transactions.v2_view") + "?_rsc="
"""The request of the page of Warsaw, as the sample's (RSC, an empty ``_rsc``)."""


CITY_TREND = BASE + request_target("api.avg_trend_city")
"""The request of the quarterly sample: Warsaw."""


TREND_PATH = "/api/avg-price-trend/city/"


def transaction_routes(
    router: respx.MockRouter, monthly: bytes | None = None, quarterly: Any = None
) -> tuple[respx.Route, respx.Route]:
    """Both channels for any city: the real page of Warsaw and the quarterly sample, or
    ``monthly`` (a page, RSC bytes) and ``quarterly`` (the trend's JSON)."""
    page = raw(STATS_TX_WARSZAWA_20261031) if monthly is None else monthly
    return (
        router.get(path__regex=STATS_PAGE).respond(200, content=page, headers=RSC_HEADERS),
        router.route(method="GET", path__startswith=TREND_PATH).respond(
            200, json=body("api.avg_trend_city") if quarterly is None else quarterly
        ),
    )


def unknown_city_routes(router: respx.MockRouter) -> tuple[respx.Route, respx.Route]:
    """Both channels answer as the service does for a city it does not know: the page a
    404 with a flight stream [P 2026-10-31], the trend a JSON 404 with an ``error``
    [P 2026-10-30] (docs/discovery/endpoints.md section 9); the place lookup that follows
    answers too (``city_lookup_routes``)."""
    city_lookup_routes(router)
    return (
        router.get(path__regex=STATS_PAGE).respond(404, **unknown_location_page()),
        router.route(method="GET", path__startswith=TREND_PATH).respond(
            404, **unknown_entity(UNKNOWN_CITY_ERROR)
        ),
    )


def transaction_answer(status: int, **kw: Any) -> Any:
    """Both channels answer ``status`` with ``kw`` (a router for the golden cases)."""

    def answer(router: respx.MockRouter) -> None:
        router.get(path__regex=STATS_PAGE).respond(status, **kw)
        router.route(method="GET", path__startswith=TREND_PATH).respond(status, **kw)

    return answer
