"""Tests of ``deweloperuch_mcp.api.adapters.buildings_api``."""

from typing import Any

import pytest
import respx

from deweloperuch_mcp.api.adapters.buildings_api import BuildingsApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.building import BuildingSlug
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError
from support.providers.error_answers import removed_route, unknown_entity
from support.providers.routes.buildings import (
    BUILDING,
    SLUG,
    building_routes,
)


def test_a_building_comes_from_the_cache_the_second_time(
    http: HttpClient, service: respx.MockRouter
) -> None:
    building_route, _ = building_routes(service)
    catalog = BuildingsApi(http)

    assert catalog.building(BuildingSlug(SLUG)) == catalog.building(BuildingSlug(SLUG))
    assert building_route.call_count == 1


@pytest.mark.parametrize(
    "answer",
    [
        # [P 2026-10-30] endpoints.md section 9: what the service answers for an unknown slug.
        dict(status_code=404, **unknown_entity()),
        # [W] the adapter's defence, never seen: a 200 without a building means "none" too.
        dict(status_code=200, content=b"null"),
        dict(status_code=200, json=dict(error="Investment not found")),
    ],
)
def test_an_unknown_building_is_not_found(
    http: HttpClient, service: respx.MockRouter, answer: dict[str, Any]
) -> None:
    route = service.get(BUILDING).respond(**answer)

    with pytest.raises(NotFoundError):
        BuildingsApi(http).building(BuildingSlug(SLUG))
    with pytest.raises(NotFoundError):  # never cached
        BuildingsApi(http).building(BuildingSlug(SLUG))
    assert route.call_count == 2


def test_a_removed_route_is_a_changed_service_not_an_unknown_building(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """D21: the Next.js not-found page (HTML 404) of a route that is gone."""
    service.get(BUILDING).respond(404, **removed_route())

    with pytest.raises(UnexpectedResponseError) as caught:
        BuildingsApi(http).building(BuildingSlug(SLUG))

    assert str(caught.value).endswith(SERVICE_CHANGED)


@pytest.mark.parametrize(
    "answer",
    [
        dict(status_code=200, json=dict(slug=SLUG)),
        dict(status_code=200, json=[1, 2]),
        dict(status_code=200, json=dict(error="x", slug=SLUG)),
        dict(status_code=200, content=b"not json", headers=dict(Accept="x")),
        dict(status_code=200, text="<html></html>", headers=[("Content-Type", "text/html")]),
    ],
)
def test_a_building_of_another_shape_is_an_unexpected_response(
    http: HttpClient, service: respx.MockRouter, answer: dict[str, Any]
) -> None:
    service.get(BUILDING).respond(**answer)

    with pytest.raises(UnexpectedResponseError):
        BuildingsApi(http).building(BuildingSlug(SLUG))
