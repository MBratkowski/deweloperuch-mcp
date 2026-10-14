"""``search_locations`` through the session: the real use case and adapters, the service mocked
(respx), no network."""

from typing import Any

import pytest
import respx

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.api.adapters.locations_api import SUGGESTIONS_LIMIT
from deweloperuch_mcp.errors import (
    InvalidInputError,
)
from support.providers import operations
from support.providers.routes.locations import location_routes
from support.providers.samples import body, request_target
from support.providers.service import BASE


def test_search_locations_combines_cities_districts_and_streets(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    cities, suggestions = location_routes(service)

    result = operations.search_locations(session, "krak")

    assert str(cities.calls.last.request.url) == BASE + request_target("api.cities_q")
    assert str(suggestions.calls.last.request.url) == BASE + "/api/location-search?q=krak&limit=6"
    assert [(item.kind, item.name, item.city_slug) for item in result.items] == [
        ("city", "Kraków", "krakow"),
        ("city", "Krakowiany", "krakowiany"),
        ("city", "Krakulice", "krakulice"),
        ("district", "Mokotów", "warszawa"),
        ("street", "Mokotów", "warszawa"),
    ]
    assert (result.total, result.returned, result.truncated, result.hint) == (5, 5, False, None)


def test_search_locations_uses_the_limits_of_the_samples(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """Only the [P] `limit` values the UI sends: 8 for cities, 6 for locations."""
    _, suggestions = location_routes(service)

    operations.search_locations(session, "mokot")

    assert str(suggestions.calls.last.request.url) == BASE + request_target("api.location_search")


def test_search_locations_is_truncated_when_cities_have_more(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    location_routes(service, cities=dict(body("api.cities_q"), hasMore=True))

    result = operations.search_locations(session, "krak")

    assert (result.total, result.returned, result.truncated) == (None, 5, True)
    assert result.hint is not None and "doprecyzuj" in result.hint


def test_search_locations_is_truncated_when_suggestions_fill_the_limit(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """[W]: location-search has no `hasMore`; a full page means there may be more."""
    service.get(path="/api/cities").respond(200, json=body("api.cities_q"))
    suggestion = body("api.location_search")["suggestions"][1]
    service.get(path="/api/location-search").respond(
        200, json={"suggestions": [suggestion] * SUGGESTIONS_LIMIT}
    )

    assert operations.search_locations(session, "krak").truncated is True


def test_search_locations_without_matches_explains_what_to_try(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    empty_cities = {"cities": [], "cityMappings": [], "hasMore": False, "total": 0, "page": 1}
    service.get(path="/api/cities").respond(200, json=empty_cities)
    service.get(path="/api/location-search").respond(200, json={"suggestions": []})

    result = operations.search_locations(session, "xyzzy")

    assert (result.total, result.returned, result.truncated) == (0, 0, False)
    assert result.hint is not None and "xyzzy" in result.hint


def test_search_locations_encodes_the_query(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    cities, _ = location_routes(service)

    operations.search_locations(session, "  Kraków ")

    assert cities.calls.last.request.url.raw_path == b"/api/cities?q=Krak%C3%B3w&limit=8"


@pytest.mark.parametrize("query", ["", " ", "k", "x" * 101, 42])
def test_search_locations_rejects_bad_queries_without_requests(
    session: bootstrap.Session, service: respx.MockRouter, query: Any
) -> None:
    with pytest.raises(InvalidInputError, match="query"):
        operations.search_locations(session, query)

    assert service.calls.call_count == 0
