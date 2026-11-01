"""Tests of ``deweloperuch_mcp.api.adapters.offer_snapshot_api``."""

import datetime as dt
from typing import Any

import pytest
import respx

from deweloperuch_mcp.api.adapters.offer_snapshot_api import OfferSnapshotApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError
from deweloperuch_mcp.models.values import CitySlug
from support.providers.error_answers import removed_route
from support.providers.routes.offer_snapshot import (
    OFFER_SNAPSHOT,
    OFFER_SNAPSHOT_HEADERS,
    OFFER_SNAPSHOT_PATH,
    offer_snapshot_routes,
)
from support.providers.rsc import UNKNOWN_CITY


def test_the_offers_of_a_city_are_its_snapshot_read_as_json(
    http: HttpClient, service: respx.MockRouter
) -> None:
    routes = offer_snapshot_routes(service)

    found = OfferSnapshotApi(http).city_offers(CitySlug("sopot"))

    assert (found.city, found.as_of, len(found.offers)) == (
        CitySlug("sopot"),
        dt.date(2026, 10, 31),
        8,
    )
    request = routes["sopot"].calls.last.request
    assert request.url.path == "/api/map/offer-snapshot/sopot"
    assert request.headers["accept"] == "application/json"


def test_the_snapshot_comes_from_the_cache_the_second_time(
    http: HttpClient, service: respx.MockRouter
) -> None:
    routes = offer_snapshot_routes(service)
    snapshots = OfferSnapshotApi(http)

    assert snapshots.city_offers(CitySlug("sopot")) == snapshots.city_offers(CitySlug("sopot"))
    assert routes["sopot"].call_count == 1


def test_a_city_the_service_does_not_know_is_not_found(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-31] endpoints.md section 9: ``404`` ``{"error":"Unknown city"}``."""
    offer_snapshot_routes(service)

    with pytest.raises(NotFoundError) as caught:
        OfferSnapshotApi(http).city_offers(CitySlug(UNKNOWN_CITY))

    assert caught.value.detail == (
        f"{OFFER_SNAPSHOT_PATH}{UNKNOWN_CITY}: HTTP 404, application/json"
    )


def test_a_snapshot_of_another_city_is_a_changed_service(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-31] a snapshot names the city asked for (``citySlug``, both fixtures): one
    of another city is no market of the city asked for."""
    service.get(OFFER_SNAPSHOT_PATH + "sopot").respond(
        200, content=OFFER_SNAPSHOT["warszawa"].read_bytes(), headers=OFFER_SNAPSHOT_HEADERS
    )

    with pytest.raises(UnexpectedResponseError) as caught:
        OfferSnapshotApi(http).city_offers(CitySlug("sopot"))

    assert str(caught.value) == f"Serwis zwrócił oferty innego miasta niż żądane. {SERVICE_CHANGED}"
    assert caught.value.detail == f"{OFFER_SNAPSHOT_PATH}sopot: citySlug 'warszawa'"


@pytest.mark.parametrize(
    "answer",
    [
        # [P 2026-10-30] endpoints.md section 9: a removed route answers the Next.js
        # not-found page, whatever the city.
        dict(status_code=404, **removed_route()),
        # A moved route (D21): never followed.
        dict(status_code=308, headers={"Location": "/api/map/offer-snapshot/v2/sopot"}),
    ],
)
def test_a_removed_or_moved_route_is_a_changed_service_not_an_unknown_city(
    http: HttpClient, service: respx.MockRouter, answer: dict[str, Any]
) -> None:
    """D21: an internal route of the service may go away; that never reads as a city the
    service does not know."""
    service.get(OFFER_SNAPSHOT_PATH + "sopot").respond(**answer)

    with pytest.raises(UnexpectedResponseError) as caught:
        OfferSnapshotApi(http).city_offers(CitySlug("sopot"))

    assert str(caught.value).endswith(SERVICE_CHANGED)
