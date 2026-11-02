"""Tests of ``deweloperuch_mcp.api.adapters.city_lookup_api``."""

import pytest
import respx

from deweloperuch_mcp.api.adapters.city_lookup_api import CityLookupApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import NotFoundError, ServiceError, UnexpectedResponseError
from deweloperuch_mcp.models.place import Place
from deweloperuch_mcp.models.values import CitySlug
from support.providers.error_answers import removed_route, unknown_entity
from support.providers.routes.city_lookup import (
    CITY_LOOKUP_PATH,
    VILLAGE,
    city_lookup_routes,
)
from support.providers.rsc import UNKNOWN_CITY


def test_a_slug_is_looked_up_in_the_transactions_dictionary(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Never the offers dictionary: without ``source`` it makes a name of any slug
    [P 2026-11-01, endpoints.md ``city-lookup``]."""
    routes = city_lookup_routes(service)

    found = CityLookupApi(http).lookup(CitySlug(VILLAGE))

    assert found == Place(name="Ignatki-osiedle", slug=VILLAGE)
    request = routes[VILLAGE].calls.last.request
    assert request.url.raw_path.decode() == (
        f"{CITY_LOOKUP_PATH}?slug={VILLAGE}&source=transactions"
    )
    assert request.headers["accept"] == "application/json"


def test_an_unknown_slug_is_no_place(http: HttpClient, service: respx.MockRouter) -> None:
    city_lookup_routes(service)

    assert CityLookupApi(http).lookup(CitySlug(UNKNOWN_CITY)) is None


def test_the_answer_comes_from_the_cache_the_second_time(
    http: HttpClient, service: respx.MockRouter
) -> None:
    routes = city_lookup_routes(service)
    places = CityLookupApi(http)

    assert places.lookup(CitySlug(VILLAGE)) == places.lookup(CitySlug(VILLAGE))
    assert routes[VILLAGE].call_count == 1


@pytest.mark.parametrize(
    ("status", "answer", "error"),
    [
        pytest.param(404, removed_route(), UnexpectedResponseError, id="removed-route"),
        # The route answers an unknown place with a 200 [P]: a 404, even the service's own
        # JSON one, is no answer of this route.
        pytest.param(404, unknown_entity(), UnexpectedResponseError, id="json-404"),
        pytest.param(500, {"text": "błąd"}, ServiceError, id="server-error"),
    ],
)
def test_a_failed_lookup_is_never_a_place_nor_not_found(
    http: HttpClient,
    service: respx.MockRouter,
    status: int,
    answer: dict[str, object],
    error: type[Exception],
) -> None:
    service.get(path=CITY_LOOKUP_PATH).respond(status, **answer)  # type: ignore[arg-type]

    with pytest.raises(error) as caught:
        CityLookupApi(http).lookup(CitySlug(VILLAGE))

    assert not isinstance(caught.value, NotFoundError)
