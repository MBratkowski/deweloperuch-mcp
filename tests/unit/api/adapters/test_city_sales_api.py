"""Tests of ``deweloperuch_mcp.api.adapters.city_sales_api``."""

from typing import Any

import pytest
import respx

from deweloperuch_mcp.api.adapters.city_sales_api import CitySalesApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import NotFoundError
from support.providers.rsc import CITY_SALES


def test_city_sales_requests_the_city_as_json(http: HttpClient, service: respx.MockRouter) -> None:
    route = service.get("/api/offers/city-sales/sopot").respond(
        200, content=CITY_SALES["sopot"].read_bytes()
    )

    parsed = CitySalesApi(http).city_sales("sopot")

    assert [sale.id for sale in parsed.sales] == [2377, 2386, 206087, 69910, 69931, 206136]
    assert route.calls.last.request.headers["accept"] == "application/json"


@pytest.mark.parametrize(
    "answer",
    [
        # [P 2026-10-10] `polska`; an unknown city may answer the same way [H].
        {"status_code": 400, "json": {"error": "Invalid citySlug"}},
        {"status_code": 404, "json": {"error": "Not found"}},
    ],
)
def test_city_sales_of_a_city_the_service_does_not_know(
    http: HttpClient, service: respx.MockRouter, answer: dict[str, Any]
) -> None:
    service.get("/api/offers/city-sales/nieznane").respond(**answer)

    with pytest.raises(NotFoundError) as caught:
        CitySalesApi(http).city_sales("nieznane")

    assert str(caught.value) == f"Serwis nie zna żądanych danych (HTTP {answer['status_code']})."


def test_an_empty_city_is_read_as_it_is(http: HttpClient, service: respx.MockRouter) -> None:
    """[H] an unknown city might answer 200 without offers: an empty market, no error."""
    service.get("/api/offers/city-sales/nieznane").respond(
        200, json={"citySlug": "nieznane", "investments": [], "sales": []}
    )

    assert CitySalesApi(http).city_sales("nieznane").sales == []
