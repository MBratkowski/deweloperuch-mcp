"""Tests of ``deweloperuch_mcp.api.adapters.city_districts_api``."""

import pytest
import respx

from deweloperuch_mcp.api.adapters.city_districts_api import CityDistrictsApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.errors import NotFoundError, UnexpectedResponseError
from deweloperuch_mcp.models.values import CitySlug
from support.builders.districts import warszawa_districts
from support.providers.routes.districts import DISTRICTS, districts_route
from support.providers.samples import body, request_target


def test_the_request_is_the_samples(http: HttpClient, service: respx.MockRouter) -> None:
    """The offers' districts: ``citySlug`` alone, without ``variant`` [P 2026-11-01]."""
    route = service.get(DISTRICTS).respond(200, json=body("api.city_districts.offers_v2"))

    CityDistrictsApi(http).city_districts("warszawa")

    assert route.call_count == 1
    request = route.calls[0].request
    assert request.url.raw_path.decode() == request_target("api.city_districts.offers_v2")
    assert request.headers["accept"] == "application/json"


def test_the_directory_maps_the_real_answer_to_the_domain(
    http: HttpClient, service: respx.MockRouter
) -> None:
    districts_route(service)

    assert CityDistrictsApi(http).districts(CitySlug("warszawa")) == warszawa_districts()


def test_the_city_is_encoded(http: HttpClient, service: respx.MockRouter) -> None:
    route = districts_route(service, {"districts": []}, city="bielsko-biala")

    assert CityDistrictsApi(http).districts(CitySlug("bielsko-biala")) == ()
    assert route.calls[0].request.url.raw_path.decode() == (
        "/api/city-districts?citySlug=bielsko-biala"
    )


def test_the_services_unknown_answer_is_not_found(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The JSON 404 of a live route [P 2026-10-30, endpoints.md section 9]; the use case keeps
    its own message then."""
    service.get(path="/api/city-districts").respond(404, json={"error": "Not found"})

    with pytest.raises(NotFoundError):
        CityDistrictsApi(http).districts(CitySlug("warszawa"))


def test_data_off_the_contract_is_an_unexpected_response(
    http: HttpClient, service: respx.MockRouter
) -> None:
    service.get(path="/api/city-districts").respond(200, json={"districts": [{"name": "Wola"}]})

    with pytest.raises(UnexpectedResponseError):
        CityDistrictsApi(http).districts(CitySlug("warszawa"))
