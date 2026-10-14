"""Tests of ``deweloperuch_mcp.api.adapters.offers_api``."""

from typing import Any

import pytest
import respx

from deweloperuch_mcp.api.adapters.offers_api import OffersApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.links import ServicePageLinks
from deweloperuch_mcp.flight import rsc_token
from deweloperuch_mcp.usecases.search_offers import SearchOffersRequest
from support.builders.offers import OFFERS_QUERY_CASES
from support.providers.rsc import offers_payload
from support.providers.service import BASE


@pytest.mark.parametrize(("given", "query"), OFFERS_QUERY_CASES)
def test_the_catalog_requests_exactly_that_and_the_link_is_the_same_list(
    http: HttpClient, given: dict[str, Any], query: str
) -> None:
    criteria = SearchOffersRequest.parse(city="krakow", **given).criteria
    with respx.mock(assert_all_mocked=True) as router:
        route = router.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
            200, content=offers_payload(), headers={"Content-Type": "text/x-component"}
        )

        OffersApi(http).search(criteria)

    target = f"/ceny-ofertowe/krakow/mieszkania?{query}"
    assert str(route.calls.last.request.url) == f"{BASE}{target}&_rsc={rsc_token(target)}"
    assert route.calls.last.request.headers["rsc"] == "1"
    assert ServicePageLinks().offers_list(criteria) == BASE + target
