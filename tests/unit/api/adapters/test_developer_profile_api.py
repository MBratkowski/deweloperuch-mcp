"""Tests of ``deweloperuch_mcp.api.adapters.developer_profile_api``."""

import pytest
import respx

from deweloperuch_mcp.api.adapters.developer_profile_api import (
    DEVELOPER_NOT_FOUND,
    DeveloperProfileApi,
)
from deweloperuch_mcp.api.http.rsc_page import RscPage
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError
from deweloperuch_mcp.flight import rsc_token
from support.providers.rsc import (
    DEVELOPER_UNKNOWN,
    DEVELOPER_WARSZAWA,
    OFFERS_UNKNOWN_CITY,
    UNKNOWN_DEVELOPER,
    raw,
)


def test_the_developer_page_requests_the_profile_as_rsc(
    http: HttpClient, service: respx.MockRouter
) -> None:
    route = service.get(path="/ceny-ofertowe/warszawa/deweloperzy/atal").respond(
        200, content=raw(DEVELOPER_WARSZAWA), headers={"Content-Type": "text/x-component"}
    )

    page = DeveloperProfileApi(http).developer_page("warszawa", "atal")

    request = route.calls.last.request
    target = "/ceny-ofertowe/warszawa/deweloperzy/atal"
    assert request.url.raw_path.decode() == f"{target}?_rsc={rsc_token(target)}"
    assert request.headers["rsc"] == "1"
    assert [item.slug for item in page.investments] == [
        "nowy-targowek-vi",
        "osiedle-poematu-ii",
        "warszawska-58a",
        "zakatek-harmonia-ii",
    ]


def test_the_page_of_an_unknown_developer_is_not_found(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-13] no data, no 404 digest: the heading „Deweloper nie znaleziony”."""
    service.get(path=f"/ceny-ofertowe/warszawa/deweloperzy/{UNKNOWN_DEVELOPER}").respond(
        200, content=raw(DEVELOPER_UNKNOWN), headers={"Content-Type": "text/x-component"}
    )

    with pytest.raises(NotFoundError) as caught:
        DeveloperProfileApi(http).developer_page("warszawa", UNKNOWN_DEVELOPER)

    assert caught.value.detail is not None and "Deweloper nie znaleziony" in caught.value.detail


def test_a_developer_page_with_the_404_digest_is_not_found(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[H] an unknown city might answer as on the offers list (Next.js's 404 marker)."""
    service.get(path="/ceny-ofertowe/nieznane/deweloperzy/atal").respond(
        200, content=raw(OFFERS_UNKNOWN_CITY), headers={"Content-Type": "text/x-component"}
    )

    with pytest.raises(NotFoundError):
        DeveloperProfileApi(http).developer_page("nieznane", "atal")


def test_a_developer_page_without_data_nor_its_heading_is_unexpected(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The heading alone tells an unknown developer: without it the service changed."""
    payload = raw(DEVELOPER_UNKNOWN).replace(b"Deweloper nie znaleziony", b"Cos innego xxxxx")
    service.get(path="/ceny-ofertowe/warszawa/deweloperzy/atal").respond(
        200, content=payload, headers={"Content-Type": "text/x-component"}
    )

    with pytest.raises(UnexpectedResponseError, match=SERVICE_CHANGED):
        DeveloperProfileApi(http).developer_page("warszawa", "atal")


def test_the_offers_list_never_takes_a_heading_for_its_404() -> None:
    """Only the developer's page knows its heading; other pages keep their rules."""
    assert RscPage.headings(raw(OFFERS_UNKNOWN_CITY)) == []
    assert RscPage.headings(raw(DEVELOPER_UNKNOWN)) == [DEVELOPER_NOT_FOUND]
