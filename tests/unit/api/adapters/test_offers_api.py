"""Tests of ``deweloperuch_mcp.api.adapters.offers_api``."""

from typing import Any

import httpx
import pytest
import respx

from deweloperuch_mcp.api.adapters.offers_api import OffersApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.links import ServicePageLinks
from deweloperuch_mcp.errors import NotFoundError, UnexpectedResponseError
from deweloperuch_mcp.models.offer import OfferSearchCriteria
from deweloperuch_mcp.usecases.search_offers import SearchOffersRequest
from support.builders.offers import OFFERS_QUERY_CASES, UNKNOWN_DISTRICT, offers_page
from support.providers.rsc import (
    OFFERS_UNKNOWN_CITY_20261031,
    OFFERS_UNKNOWN_DISTRICT_20261031,
    OFFERS_WARSZAWA_MOKOTOW_20261031,
    offers_payload,
    raw,
)
from support.providers.service import BASE

RSC = {"Content-Type": "text/x-component"}
CACHED = {**RSC, "Cache-Control": "private, max-age=172800, must-revalidate", "Age": "1500"}
"""The cache headers of the 2.0 pages [P 2026-10-31] and a Cloudflare age like the fixtures'
HITs: the client keeps such a reply for its full 300 s."""


def criteria(**given: Any) -> OfferSearchCriteria:
    return SearchOffersRequest.parse(**given).criteria


@pytest.mark.parametrize(("given", "query"), OFFERS_QUERY_CASES)
def test_the_catalog_requests_exactly_that_and_the_link_is_the_same_list(
    http: HttpClient, given: dict[str, Any], query: str
) -> None:
    wanted = criteria(city="krakow", **given)
    with respx.mock(assert_all_mocked=True) as router:
        route = router.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
            200, content=offers_payload(), headers=RSC
        )

        OffersApi(http).search(wanted)

    target = f"/ceny-ofertowe/krakow/mieszkania?{query}"
    assert str(route.calls.last.request.url) == f"{BASE}{target}&_rsc="
    assert route.calls.last.request.headers["rsc"] == "1"
    assert ServicePageLinks().offers_list(wanted) == BASE + target


def test_a_district_is_read_from_its_own_list(http: HttpClient) -> None:
    """[P 2026-10-31] the district's list (the real page of Mokotów), at the district's slug,
    with the parameters of the search ([W] on that route, T73); the link is the request."""
    wanted = criteria(city="warszawa", district="Mokotów", price_max=900_000)
    with respx.mock(assert_all_mocked=True) as router:
        route = router.get(path="/ceny-ofertowe/warszawa/mokotow/mieszkania").respond(
            200, content=raw(OFFERS_WARSZAWA_MOKOTOW_20261031), headers=RSC
        )

        found = OffersApi(http).search(wanted)

    target = "/ceny-ofertowe/warszawa/mokotow/mieszkania?filterPrice=0-900000&perPage=10"
    assert str(route.calls.last.request.url) == f"{BASE}{target}&_rsc="
    assert ServicePageLinks().offers_list(wanted) == BASE + target
    assert (found.total, found.page, found.per_page, found.returned) == (959, 1, 25, 25)


def test_an_unknown_district_is_not_found(http: HttpClient) -> None:
    """[P 2026-10-31] the district's list of a district the service does not know: 200
    with Next.js's 404 marker."""
    with respx.mock(assert_all_mocked=True) as router:
        router.get(path="/ceny-ofertowe/warszawa/nieistniejaca-dzielnica/mieszkania").respond(
            200, content=raw(OFFERS_UNKNOWN_DISTRICT_20261031), headers=RSC
        )

        with pytest.raises(NotFoundError) as caught:
            OffersApi(http).search(criteria(city="warszawa", district=UNKNOWN_DISTRICT))

    assert "NEXT_HTTP_ERROR_FALLBACK;404" in (caught.value.detail or "")


def test_a_404_flight_stream_is_a_changed_service_not_an_unknown_city(http: HttpClient) -> None:
    """D21: the offers list does not opt in to ``unknown_404``, because its own "unknown" is a
    200 with Next.js's 404 marker [P 2026-10-31]; a 404 flight stream means a rebuilt route."""
    with respx.mock(assert_all_mocked=True) as router:
        router.get(path="/ceny-ofertowe/warszawa/mieszkania").respond(
            404, content=raw(OFFERS_UNKNOWN_CITY_20261031), headers=RSC
        )

        with pytest.raises(UnexpectedResponseError):
            OffersApi(http).search(criteria(city="warszawa"))


def test_a_district_without_a_slug_is_not_found_without_a_request(http: HttpClient) -> None:
    """No letter or digit the service writes in its addresses: no list to ask for."""
    with respx.mock(assert_all_mocked=True) as router:
        with pytest.raises(NotFoundError) as caught:
            OffersApi(http).search(criteria(city="warszawa", district="Ωμέγα"))

        assert router.calls.call_count == 0

    assert str(caught.value) == "Serwis nie zna żądanych danych (strona nie istnieje)."
    assert ServicePageLinks().offers_list(criteria(city="warszawa", district="--")) is None


@pytest.mark.parametrize(
    "bad",
    [
        # props of another shape (the paging's size as text)
        offers_payload(
            {"serverPaginationData": {"currentPage": 1, "perPage": "dużo", "totalCount": 11672}}
        ),
        # no props and no 404 marker
        raw(OFFERS_UNKNOWN_CITY_20261031).replace(
            b"NEXT_HTTP_ERROR_FALLBACK;404", b"NEXT_HTTP_ERROR_FALLBACK;403"
        ),
    ],
    ids=["another shape", "no props nor marker"],
)
def test_a_page_off_the_contract_is_not_served_again_from_the_cache(
    http: HttpClient, bad: bytes
) -> None:
    """The DTO checks the page inside the transport's decode: a page that does not match is
    never cached (transport.py, the cache), so the next search asks again and gets the good
    one, and keeps that."""
    wanted = criteria(city="warszawa")
    with respx.mock(assert_all_mocked=True) as router:
        route = router.route(method="GET", path="/ceny-ofertowe/warszawa/mieszkania").mock(
            side_effect=[
                httpx.Response(200, content=bad, headers=CACHED),
                httpx.Response(200, content=offers_payload(offers_page()), headers=CACHED),
            ]
        )

        with pytest.raises(UnexpectedResponseError):
            OffersApi(http).search(wanted)
        found = [OffersApi(http).search(wanted).total for _ in range(2)]

    assert found == [11_672, 11_672]
    assert route.call_count == 2  # the bad page again, then the good one from the cache
