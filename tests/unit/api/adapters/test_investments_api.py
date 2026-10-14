"""Tests of ``deweloperuch_mcp.api.adapters.investments_api``."""

from typing import Any

import pytest
import respx

from deweloperuch_mcp import identity
from deweloperuch_mcp.api.adapters.investments_api import InvestmentsApi
from deweloperuch_mcp.api.adapters.locations_api import LocationsApi
from deweloperuch_mcp.api.adapters.offers_api import OffersApi
from deweloperuch_mcp.api.dto import investment_dto, sale_events_dto
from deweloperuch_mcp.api.dto.cities_dto import CitiesDto
from deweloperuch_mcp.api.dto.investment_sale_events_dto import InvestmentSaleEventsDto
from deweloperuch_mcp.api.dto.location_search_dto import LocationSearchDto
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import InvalidInputError, UnexpectedResponseError
from support.providers.samples import body, request_target


@pytest.mark.parametrize(
    ("sample", "call", "model"),
    [
        ("api.cities_q", lambda http: LocationsApi(http).city_search("krak", 8), CitiesDto),
        (
            "api.location_search",
            lambda http: LocationsApi(http).location_search("mokot", 6),
            LocationSearchDto,
        ),
        (
            "api.map_inv_visible",
            lambda http: InvestmentsApi(http).visible_investment("smolna"),
            investment_dto.InvestmentDto,
        ),
        (
            "api.inv_sale_events",
            lambda http: InvestmentsApi(http).investment_sale_events(33),
            InvestmentSaleEventsDto,
        ),
        (
            "api.sale_events",
            lambda http: OffersApi(http).sale_events(2377),
            sale_events_dto.SaleEventsDto,
        ),
    ],
)
def test_json_endpoint_requests_what_the_sample_requested(
    http: HttpClient, service: respx.MockRouter, sample: str, call: Any, model: type[Any]
) -> None:
    url = identity.BASE_URL + request_target(sample)
    route = service.get(url).respond(200, json=body(sample))

    parsed = call(http)

    assert parsed == model.model_validate(body(sample))
    request = route.calls.last.request
    assert str(request.url) == url
    assert request.headers.get_list("user-agent") == [identity.USER_AGENT]
    assert request.headers["accept"] == "application/json"


@pytest.mark.parametrize("slug", ["a/..?b", "..", "a b", "kraków"])
def test_slugs_with_separators_never_reach_the_service(
    http: HttpClient, service: respx.MockRouter, slug: str
) -> None:
    """Encoded, they cannot change the path; and the transport refuses encoded paths."""
    with pytest.raises(InvalidInputError):
        InvestmentsApi(http).visible_investment(slug)

    assert service.calls.call_count == 0


@pytest.mark.parametrize(
    ("content", "content_type", "message"),
    [
        (b"<!DOCTYPE html><html></html>", "text/html", "HTML"),
        (b"{not json", "application/json", "JSON"),
        (b'{"city": "Warszawa"}', "application/json", "kontrakt"),
    ],
)
def test_json_that_does_not_match_the_contract_is_unexpected(
    http: HttpClient, service: respx.MockRouter, content: bytes, content_type: str, message: str
) -> None:
    service.get(identity.BASE_URL + "/api/map/investments/visible/smolna").respond(
        200, content=content, headers={"Content-Type": content_type}
    )

    with pytest.raises(UnexpectedResponseError, match=message):
        InvestmentsApi(http).visible_investment("smolna")
