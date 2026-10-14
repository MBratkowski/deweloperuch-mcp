"""Tests of ``deweloperuch_mcp.api.adapters.developer_search_api``."""

import pytest
import respx

from deweloperuch_mcp.api.adapters.developer_search_api import DeveloperSearchApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.developer_match import DeveloperMatches, DeveloperName, MatchCount
from deweloperuch_mcp.models.errors import UnexpectedResponseError
from support.fakes.developer_search import ATAL
from support.providers.routes.developer_search import DEVELOPERS, developer_search_route
from support.providers.samples import body, request_target


def test_the_request_is_the_samples(http: HttpClient, service: respx.MockRouter) -> None:
    route = service.get(DEVELOPERS).respond(200, json=body("api.developers_q"))

    found = DeveloperSearchApi(http).named_developers("atal", 5)

    assert route.call_count == 1
    request = route.calls[0].request
    assert request.url.raw_path.decode() == request_target("api.developers_q")
    assert request.headers["accept"] == "application/json"
    assert found.developers[0].slug == "atal"


@pytest.mark.parametrize(
    ("query", "sent"),
    [
        ("Dom Development", "q=Dom%20Development&limit=20"),
        ("Śląsk & syn", "q=%C5%9Al%C4%85sk%20%26%20syn&limit=20"),
        ("a/b?c#d", "q=a%2Fb%3Fc%23d&limit=20"),
    ],
)
def test_the_query_is_encoded(
    http: HttpClient, service: respx.MockRouter, query: str, sent: str
) -> None:
    route = service.get(path="/api/developers").respond(200, json=body("api.developers_q"))

    DeveloperSearchApi(http).named_developers(query, 20)

    assert route.calls[0].request.url.raw_path.decode() == "/api/developers?" + sent


def test_the_directory_maps_the_sample_to_the_domain(
    http: HttpClient, service: respx.MockRouter
) -> None:
    developer_search_route(service)

    found = DeveloperSearchApi(http).developers(DeveloperName("atal"), MatchCount())

    assert found == DeveloperMatches((ATAL,), total=1, more=False)


def test_the_directory_asks_for_the_count(http: HttpClient, service: respx.MockRouter) -> None:
    route = developer_search_route(service)

    DeveloperSearchApi(http).developers(DeveloperName("dom"), MatchCount(20))

    assert route.calls[0].request.url.params["limit"] == "20"


def test_an_html_page_instead_of_data_is_an_unexpected_response(
    http: HttpClient, service: respx.MockRouter
) -> None:
    service.get(path="/api/developers").respond(
        200, text="strona", headers={"Content-Type": "text/html; charset=utf-8"}
    )

    with pytest.raises(UnexpectedResponseError):
        DeveloperSearchApi(http).developers(DeveloperName("atal"), MatchCount())


def test_data_off_the_contract_is_an_unexpected_response(
    http: HttpClient, service: respx.MockRouter
) -> None:
    without_slug = {"developers": [{"name": "X"}], "hasMore": False, "total": 1}
    service.get(path="/api/developers").respond(200, json=without_slug)

    with pytest.raises(UnexpectedResponseError):
        DeveloperSearchApi(http).developers(DeveloperName("atal"), MatchCount())
