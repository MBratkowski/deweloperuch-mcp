"""Tests of ``deweloperuch_mcp.api.adapters.city_sales_api``."""

import pytest
import respx

from deweloperuch_mcp.api.adapters.city_sales_api import CitySalesApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import NotFoundError, UnexpectedResponseError
from support.providers.routes.offer_snapshot import (
    gone_snapshot_route,
    offer_snapshot_routes,
    unknown_city_snapshot_route,
)


def test_the_snapshot_is_requested_as_json(http: HttpClient, service: respx.MockRouter) -> None:
    route = offer_snapshot_routes(service)["sopot"]

    parsed = CitySalesApi(http).offer_snapshot("sopot")

    assert [sale.id for sale in parsed.sales] == [2377, 2386, 206087, 69910, 69931, 206136]
    assert route.calls.last.request.url.path == "/api/map/offer-snapshot/sopot"
    assert route.calls.last.request.headers["accept"] == "application/json"


def test_a_json_404_is_a_city_the_service_does_not_know(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-30] ``nieistniejace-miasto``: HTTP 404 {"error":"Unknown city"}."""
    unknown_city_snapshot_route(service)

    with pytest.raises(NotFoundError) as caught:
        CitySalesApi(http).offer_snapshot("nieznane")

    assert str(caught.value) == "Serwis nie zna żądanych danych (HTTP 404)."


def test_an_html_404_is_a_gone_data_source(http: HttpClient, service: respx.MockRouter) -> None:
    gone_snapshot_route(service)

    with pytest.raises(UnexpectedResponseError, match="nie jest już dostępne"):
        CitySalesApi(http).offer_snapshot("sopot")


def test_an_empty_city_is_read_as_it_is(http: HttpClient, service: respx.MockRouter) -> None:
    """[H] a city without offers might answer 200 with none: an empty market, no error."""
    service.get("/api/map/offer-snapshot/pusta").respond(
        200, json={"citySlug": "pusta", "asOf": "2026-10-30", "investments": [], "sales": []}
    )

    assert CitySalesApi(http).offer_snapshot("pusta").sales == []
