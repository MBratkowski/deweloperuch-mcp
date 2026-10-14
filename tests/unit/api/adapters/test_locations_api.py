"""Tests of ``deweloperuch_mcp.api.adapters.locations_api``."""

import pytest
import respx

from deweloperuch_mcp import identity
from deweloperuch_mcp.api.adapters.locations_api import LocationsApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import NotFoundError, ServiceError
from support.providers.samples import body


def test_query_values_are_percent_encoded(http: HttpClient, service: respx.MockRouter) -> None:
    url = identity.BASE_URL + "/api/cities?q=%C5%81%C3%B3d%C5%BA%20%26%20okolice&limit=8"
    route = service.get(url).respond(200, json=body("api.cities_q"))

    LocationsApi(http).city_search("Łódź & okolice", 8)

    assert str(route.calls.last.request.url) == url


def test_a_400_of_another_endpoint_is_still_a_service_error(
    http: HttpClient, service: respx.MockRouter
) -> None:
    service.get(path="/api/cities").respond(400, json={"error": "Invalid"})

    with pytest.raises(ServiceError) as caught:
        LocationsApi(http).city_search("krak", 8)

    assert not isinstance(caught.value, NotFoundError)
