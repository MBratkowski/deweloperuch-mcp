"""Tests of ``deweloperuch_mcp.api.adapters.developer_profile_api`` on the 2.0 pages of
2026-10-31 (tests/fixtures/rsc/developer_*_20261031.rsc)."""

from pathlib import Path
from typing import Any

import pytest
import respx

from deweloperuch_mcp.api.adapters.developer_profile_api import DeveloperProfileApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError
from deweloperuch_mcp.flight import NOT_FOUND_DIGEST
from deweloperuch_mcp.models.values import CitySlug, DeveloperSlug
from support.providers.error_answers import removed_route
from support.providers.rsc import (
    DEVELOPER_CERES_WARSZAWA_20261031,
    DEVELOPER_POLSKA_20261031,
    DEVELOPER_UNKNOWN_20261031,
    DEVELOPER_UNKNOWN_CITY_20261102,
    DEVELOPER_UNKNOWN_POLSKA_20261031,
    DEVELOPER_WARSZAWA_20261031,
    UNKNOWN_CITY,
    UNKNOWN_DEVELOPER,
    raw,
)

RSC = {"Content-Type": "text/x-component"}
WARSZAWA = "/ceny-ofertowe/warszawa/deweloperzy/atal"


def test_the_profile_is_one_rsc_request_of_the_developer_page(
    http: HttpClient, service: respx.MockRouter
) -> None:
    route = service.get(path=WARSZAWA).respond(
        200, content=raw(DEVELOPER_WARSZAWA_20261031), headers=RSC
    )

    profile = DeveloperProfileApi(http).developer(DeveloperSlug("atal"), CitySlug("warszawa"))

    request = route.calls.last.request
    assert route.call_count == 1
    assert request.url.raw_path.decode() == f"{WARSZAWA}?_rsc="
    assert request.headers["rsc"] == "1"
    assert (profile.developer.developer_slug, profile.developer.name) == ("atal", "ATAL S.A.")
    assert profile.city == CitySlug("warszawa")
    assert [item.investment_slug for item in profile.investments] == [
        "nowy-targowek-vi",
        "osiedle-poematu-ii",
        "warszawska-58a",
        "zakatek-harmonia-ii",
    ]
    assert len(profile.cities) == 14


def test_the_profile_of_the_whole_country(http: HttpClient, service: respx.MockRouter) -> None:
    """[P 2026-10-31] ``polska`` as the city: every investment of the developer."""
    service.get(path="/ceny-ofertowe/polska/deweloperzy/atal").respond(
        200, content=raw(DEVELOPER_POLSKA_20261031), headers=RSC
    )

    profile = DeveloperProfileApi(http).developer(DeveloperSlug("atal"), CitySlug("polska"))

    assert (len(profile.investments), profile.summary.cities, len(profile.cities)) == (42, 14, 14)


def test_the_profile_of_a_developer_in_one_city(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-31] Ceres Development: the page has no chart of cities; its city comes
    from its one investment."""
    service.get(path="/ceny-ofertowe/warszawa/deweloperzy/ceres-development").respond(
        200, content=raw(DEVELOPER_CERES_WARSZAWA_20261031), headers=RSC
    )

    profile = DeveloperProfileApi(http).developer(
        DeveloperSlug("ceres-development"), CitySlug("warszawa")
    )

    assert [item.investment_slug for item in profile.investments] == ["osiedle-sprawna-warszawa"]
    assert [(city.city_slug, city.investments, city.active_offers) for city in profile.cities] == [
        ("warszawa", 1, 110)
    ]


@pytest.mark.parametrize(
    ("city", "fixture"),
    [("warszawa", DEVELOPER_UNKNOWN_20261031), ("polska", DEVELOPER_UNKNOWN_POLSKA_20261031)],
)
def test_the_page_of_an_unknown_developer_is_not_found(
    http: HttpClient, service: respx.MockRouter, city: str, fixture: Path
) -> None:
    """[P 2026-10-31] a 200 with Next.js's 404 marker, for a city and for the whole country
    (1.0 had a heading instead)."""
    service.get(path=f"/ceny-ofertowe/{city}/deweloperzy/{UNKNOWN_DEVELOPER}").respond(
        200, content=raw(fixture), headers=RSC
    )

    with pytest.raises(NotFoundError) as caught:
        DeveloperProfileApi(http).developer_page(city, UNKNOWN_DEVELOPER)

    assert caught.value.detail is not None and NOT_FOUND_DIGEST in caught.value.detail


def test_developer_page_of_an_unknown_city_is_not_found(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """T39 [P 2026-11-02]: a known developer in a city the service does not know; the page
    sends the reader on to the developer's page for the whole country."""
    path = f"/ceny-ofertowe/{UNKNOWN_CITY}/deweloperzy/atal"
    service.get(path=path).respond(200, content=raw(DEVELOPER_UNKNOWN_CITY_20261102), headers=RSC)

    with pytest.raises(NotFoundError) as caught:
        DeveloperProfileApi(http).developer(DeveloperSlug("atal"), CitySlug(UNKNOWN_CITY))

    assert caught.value.detail is not None
    assert caught.value.detail.endswith("przekierowuje do /ceny-ofertowe/polska/deweloperzy/atal")


def test_the_page_of_the_whole_country_sent_on_to_itself_is_a_changed_service(
    http: HttpClient, service: respx.MockRouter
) -> None:
    payload = raw(DEVELOPER_UNKNOWN_CITY_20261102)
    service.get(path="/ceny-ofertowe/polska/deweloperzy/atal").respond(
        200, content=payload, headers=RSC
    )

    with pytest.raises(UnexpectedResponseError, match=SERVICE_CHANGED):
        DeveloperProfileApi(http).developer(DeveloperSlug("atal"), CitySlug("polska"))


def test_a_page_without_data_nor_the_404_marker_is_a_changed_service(
    http: HttpClient, service: respx.MockRouter
) -> None:
    payload = raw(DEVELOPER_UNKNOWN_20261031).replace(
        NOT_FOUND_DIGEST.encode(), b"NEXT_HTTP_ERROR_FALLBACK;500"
    )
    service.get(path=WARSZAWA).respond(200, content=payload, headers=RSC)

    with pytest.raises(UnexpectedResponseError, match=SERVICE_CHANGED):
        DeveloperProfileApi(http).developer_page("warszawa", "atal")


@pytest.mark.parametrize(
    ("status", "answer"),
    [
        (404, removed_route()),
        # The page does not opt in to unknown_404: its own "unknown" is a 200 with the
        # marker [P 2026-10-31], so a 404 flight stream is a rebuilt route, not a developer.
        (404, {"content": raw(DEVELOPER_UNKNOWN_20261031), "headers": RSC}),
        (410, {"text": "<!DOCTYPE html>", "headers": {"Content-Type": "text/html"}}),
        (308, {"headers": {"Location": "/ceny-ofertowe/warszawa/deweloperzy"}}),
    ],
)
def test_a_removed_or_moved_page_is_a_changed_service_not_an_unknown_developer(
    http: HttpClient, service: respx.MockRouter, status: int, answer: dict[str, Any]
) -> None:
    """D21: an HTML 404, a 404 flight stream, a 410 or a redirect of the page tells nothing
    about the developer."""
    service.get(path=WARSZAWA).respond(status, **answer)

    with pytest.raises(UnexpectedResponseError, match=SERVICE_CHANGED):
        DeveloperProfileApi(http).developer_page("warszawa", "atal")


def test_the_path_is_the_profile_route_of_a_city_or_the_whole_country() -> None:
    assert DeveloperProfileApi.path("warszawa", "atal") == WARSZAWA
    assert DeveloperProfileApi.path("polska", "atal") == "/ceny-ofertowe/polska/deweloperzy/atal"
