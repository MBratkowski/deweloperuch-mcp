"""The four services of the first slice over a mocked service (respx, bodies from samples).

Input is checked before anything is sent; only parameters marked [P] in the discovery
docs reach the service; results follow D4 (total, returned, truncated) and D3 (names).
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from deweloperuch_mcp import identity, services
from deweloperuch_mcp.client import transport
from deweloperuch_mcp.errors import (
    InvalidInputError,
    LimiterWaitError,
    NotFoundError,
    RateLimitedError,
    ServiceBlockedError,
    SessionClosedError,
)
from deweloperuch_mcp.flight import rsc_token
from deweloperuch_mcp.throttle import LOCK_FILENAME, RequestLimiter
from discovery_samples import body, request_target, rsc_payload

BASE = identity.BASE_URL
OFFERS_PAGE = "/ceny-ofertowe/warszawa/mieszkania"


@pytest.fixture
def limiter(tmp_path: Path) -> RequestLimiter:
    return RequestLimiter(tmp_path, min_interval=0, testing_only_allow_fast_interval=True)


@pytest.fixture
def session(limiter: RequestLimiter) -> Iterator[services.Session]:
    with services.Session(limiter=limiter) as opened:
        yield opened


@pytest.fixture
def service() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


def offers_route(service: respx.MockRouter, sample: str = "page.offers_list") -> respx.Route:
    return service.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
        200,
        content=rsc_payload({"initialData": body(sample)}),
        headers={"Content-Type": "text/x-component"},
    )


def sent_query(route: respx.Route) -> str:
    """The query the service got, without the ``_rsc`` token."""
    url = route.calls.last.request.url
    query = url.query.decode()
    assert query.endswith(f"_rsc={url.params['_rsc']}")
    return query.rsplit("_rsc=", 1)[0].rstrip("&")


# --- search_locations --------------------------------------------------------------------


def location_routes(
    service: respx.MockRouter, cities: dict[str, Any] | None = None
) -> tuple[respx.Route, respx.Route]:
    return (
        service.get(path="/api/cities").respond(200, json=cities or body("api.cities_q")),
        service.get(path="/api/location-search").respond(200, json=body("api.location_search")),
    )


def test_search_locations_combines_cities_districts_and_streets(
    session: services.Session, service: respx.MockRouter
) -> None:
    cities, suggestions = location_routes(service)

    result = services.search_locations(session, "krak")

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
    session: services.Session, service: respx.MockRouter
) -> None:
    """Only the [P] `limit` values the UI sends: 8 for cities, 6 for locations."""
    _, suggestions = location_routes(service)

    services.search_locations(session, "mokot")

    assert str(suggestions.calls.last.request.url) == BASE + request_target("api.location_search")


def test_search_locations_is_truncated_when_cities_have_more(
    session: services.Session, service: respx.MockRouter
) -> None:
    location_routes(service, cities=dict(body("api.cities_q"), hasMore=True))

    result = services.search_locations(session, "krak")

    assert (result.total, result.returned, result.truncated) == (None, 5, True)
    assert result.hint is not None and "doprecyzuj" in result.hint


def test_search_locations_is_truncated_when_suggestions_fill_the_limit(
    session: services.Session, service: respx.MockRouter
) -> None:
    """[W]: location-search has no `hasMore`; a full page means there may be more."""
    service.get(path="/api/cities").respond(200, json=body("api.cities_q"))
    suggestion = body("api.location_search")["suggestions"][1]
    service.get(path="/api/location-search").respond(
        200, json={"suggestions": [suggestion] * services.SUGGESTIONS_LIMIT}
    )

    assert services.search_locations(session, "krak").truncated is True


def test_search_locations_without_matches_explains_what_to_try(
    session: services.Session, service: respx.MockRouter
) -> None:
    empty_cities = {"cities": [], "cityMappings": [], "hasMore": False, "total": 0, "page": 1}
    service.get(path="/api/cities").respond(200, json=empty_cities)
    service.get(path="/api/location-search").respond(200, json={"suggestions": []})

    result = services.search_locations(session, "xyzzy")

    assert (result.total, result.returned, result.truncated) == (0, 0, False)
    assert result.hint is not None and "xyzzy" in result.hint


def test_search_locations_encodes_the_query(
    session: services.Session, service: respx.MockRouter
) -> None:
    cities, _ = location_routes(service)

    services.search_locations(session, "  Kraków ")

    assert cities.calls.last.request.url.raw_path == b"/api/cities?q=Krak%C3%B3w&limit=8"


@pytest.mark.parametrize("query", ["", " ", "k", "x" * 101, 42])
def test_search_locations_rejects_bad_queries_without_requests(
    session: services.Session, service: respx.MockRouter, query: Any
) -> None:
    with pytest.raises(InvalidInputError, match="query"):
        services.search_locations(session, query)

    assert service.calls.call_count == 0


# --- search_offers -----------------------------------------------------------------------


def test_search_offers_sends_the_filters_of_the_filtered_sample(
    session: services.Session, service: respx.MockRouter
) -> None:
    route = offers_route(service, "page.offers_list.filtered")

    result = services.search_offers(
        session,
        "warszawa",
        price_min=500_000,
        price_max=700_000,
        area_min=40,
        area_max=60,
        sort="price_asc",
        page=2,
        per_page=50,
    )

    target = request_target("page.offers_list.filtered")
    assert str(route.calls.last.request.url) == f"{BASE}{target}&_rsc={rsc_token(target)}"
    assert route.calls.last.request.headers["rsc"] == "1"
    assert (result.total, result.returned, result.page, result.per_page) == (1192, 3, 2, 50)
    assert (result.truncated, result.pages_available) == (True, 20)
    assert result.hint is not None
    assert result.items[0].offer_id == 120306
    assert result.items[0].investment_slug == "werandowa"


def test_search_offers_defaults(session: services.Session, service: respx.MockRouter) -> None:
    route = offers_route(service)

    result = services.search_offers(session, "warszawa")

    assert route.calls.last.request.url.path == OFFERS_PAGE
    # No sortBy: the service's default order [P]; page 1 and the service's default 10.
    assert sent_query(route) == "page=1&perPage=10"
    assert result.total == 13324


@pytest.mark.parametrize(
    ("filters", "query"),
    [
        ({"price_max": 500_000}, "filterPrice=0-500000"),
        ({"price_min": 500_000}, "filterPrice=500000-99999999"),
        ({"price_min": 0, "price_max": 0}, "filterPrice=0-0"),
        ({"area_min": 40}, "filterSize=40-9999"),
        ({"area_max": 60}, "filterSize=0-60"),
        ({"price_max": 900_000, "area_min": 35}, "filterPrice=0-900000&filterSize=35-9999"),
        ({"sort": "price_asc"}, "sortBy=amount&sortOrder=asc"),
        ({"sort": "price_desc"}, "sortBy=amount&sortOrder=desc"),
    ],
)
def test_search_offers_builds_ranges_and_sort(
    session: services.Session, service: respx.MockRouter, filters: dict[str, Any], query: str
) -> None:
    """Open ranges: 0 below, the UI sentinels above ([P z kodu], pages-rsc.md)."""
    route = offers_route(service)

    services.search_offers(session, "warszawa", **filters)

    assert sent_query(route) == f"{query}&page=1&perPage=10"


@pytest.mark.parametrize("per_page", [10, 50, 100])
def test_search_offers_accepts_the_page_sizes_of_the_service(
    session: services.Session, service: respx.MockRouter, per_page: int
) -> None:
    route = offers_route(service)

    services.search_offers(session, "warszawa", page=20, per_page=per_page)

    assert sent_query(route) == f"page=20&perPage={per_page}"


def test_search_offers_accepts_the_whole_country(
    session: services.Session, service: respx.MockRouter
) -> None:
    route = offers_route(service)

    services.search_offers(session, "polska")

    assert route.calls.last.request.url.path == "/ceny-ofertowe/polska/mieszkania"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"per_page": 20}, "per_page"),
        ({"per_page": 25}, "per_page"),
        ({"per_page": 500}, "per_page"),
        ({"page": 0}, "page"),
        ({"page": 21}, "page"),
        ({"page": True}, "page"),
        ({"price_min": 700_000, "price_max": 500_000}, "price_min"),
        ({"area_min": 60, "area_max": 40}, "area_min"),
        ({"price_min": -1}, "price_min"),
        ({"price_max": 100_000_000}, "price_max"),
        ({"area_max": 10_000}, "area_max"),
        ({"area_min": 40.5}, "area_min"),
        ({"price_max": "500000"}, "price_max"),
        ({"sort": "area_asc"}, "sort"),
        ({"sort": "amount"}, "sort"),
        ({"sort": ["price_asc"]}, "sort"),
        ({"city": "Kraków"}, "city"),
        ({"city": ""}, "city"),
        ({"city": "warszawa/../x"}, "city"),
        ({"city": None}, "city"),
    ],
)
def test_search_offers_rejects_bad_input_without_requests(
    session: services.Session, service: respx.MockRouter, arguments: dict[str, Any], message: str
) -> None:
    arguments = {"city": "warszawa", **arguments}

    with pytest.raises(InvalidInputError, match=message):
        services.search_offers(session, **arguments)

    assert service.calls.call_count == 0


def test_search_offers_unknown_city_points_to_search_locations(
    session: services.Session, service: respx.MockRouter
) -> None:
    service.route(method="GET").respond(404)

    with pytest.raises(NotFoundError, match="search_locations"):
        services.search_offers(session, "atlantyda")


# --- get_investment ----------------------------------------------------------------------

INVESTMENT = BASE + request_target("api.map_inv_visible")
INVESTMENT_EVENTS = BASE + request_target("api.inv_sale_events")
SALE_EVENTS = BASE + request_target("api.sale_events")


def investment_routes(service: respx.MockRouter) -> tuple[respx.Route, respx.Route, respx.Route]:
    return (
        service.get(INVESTMENT).respond(200, json=body("api.map_inv_visible")),
        service.get(INVESTMENT_EVENTS).respond(200, json=body("api.inv_sale_events")),
        service.get(SALE_EVENTS).respond(200, json=body("api.sale_events")),
    )


def test_get_investment_is_one_request_without_history(
    session: services.Session, service: respx.MockRouter
) -> None:
    investment, history, _ = investment_routes(service)

    result = services.get_investment(session, "smolna")

    assert (investment.call_count, history.call_count) == (1, 0)
    assert (result.investment_slug, result.offers_total, len(result.offers)) == ("smolna", 16, 3)
    assert all(offer.price_history is None for offer in result.offers)


def test_get_investment_with_history_and_limit(
    session: services.Session, service: respx.MockRouter
) -> None:
    investment, history, _ = investment_routes(service)

    result = services.get_investment(session, "smolna", include_history=True, limit=1)

    assert (investment.call_count, history.call_count) == (1, 1)
    assert [offer.offer_id for offer in result.offers] == [206087]
    assert result.offers_omitted == 2
    assert result.offers[0].price_history is not None
    assert [event.price for event in result.offers[0].price_history] == [1679796.0]


def test_get_investment_unknown_slug_says_where_slugs_come_from(
    session: services.Session, service: respx.MockRouter
) -> None:
    service.get(BASE + "/api/map/investments/visible/nie-ma").respond(404)

    with pytest.raises(NotFoundError, match="search_offers"):
        services.get_investment(session, "nie-ma")


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"investment_slug": "Smolna"}, "investment_slug"),
        ({"investment_slug": "smolna/../x"}, "investment_slug"),
        ({"investment_slug": ""}, "investment_slug"),
        ({"limit": -1}, "limit"),
        ({"limit": 1.5}, "limit"),
        ({"include_history": "yes"}, "include_history"),
    ],
)
def test_get_investment_rejects_bad_input_without_requests(
    session: services.Session, service: respx.MockRouter, arguments: dict[str, Any], message: str
) -> None:
    arguments = {"investment_slug": "smolna", **arguments}

    with pytest.raises(InvalidInputError, match=message):
        services.get_investment(session, **arguments)

    assert service.calls.call_count == 0


# --- get_offer ---------------------------------------------------------------------------


def test_get_offer_returns_the_offer_with_its_price_history(
    session: services.Session, service: respx.MockRouter
) -> None:
    investment, history, events = investment_routes(service)

    result = services.get_offer(session, 2377, "smolna")

    assert (investment.call_count, events.call_count, history.call_count) == (1, 1, 0)
    assert (result.offer_id, result.name, result.investment_slug) == (2377, "C224", "smolna")
    assert (result.price, result.area_m2, result.status) == (1620175.0, 69.5, "active")
    assert [(e.kind, e.price) for e in result.price_history] == [
        ("offer", 1620000.0),
        ("archived", 1620000.0),
        ("restored", 1620175.0),
    ]


def test_get_offer_missing_from_the_investment_is_not_found(
    session: services.Session, service: respx.MockRouter
) -> None:
    _, _, events = investment_routes(service)

    with pytest.raises(NotFoundError, match="999") as caught:
        services.get_offer(session, 999, "smolna")

    assert "get_investment" in str(caught.value)
    assert events.call_count == 0


def test_get_offer_after_get_investment_reuses_the_cached_investment(
    session: services.Session, service: respx.MockRouter
) -> None:
    investment, _, _ = investment_routes(service)

    services.get_investment(session, "smolna")
    services.get_offer(session, 2377, "smolna")

    assert investment.call_count == 1


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"offer_id": 0}, "offer_id"),
        ({"offer_id": -5}, "offer_id"),
        ({"offer_id": "2377"}, "offer_id"),
        ({"offer_id": True}, "offer_id"),
        ({"investment_slug": "SMOLNA"}, "investment_slug"),
    ],
)
def test_get_offer_rejects_bad_input_without_requests(
    session: services.Session, service: respx.MockRouter, arguments: dict[str, Any], message: str
) -> None:
    arguments = {"offer_id": 2377, "investment_slug": "smolna", **arguments}

    with pytest.raises(InvalidInputError, match=message):
        services.get_offer(session, **arguments)

    assert service.calls.call_count == 0


# --- every request ---------------------------------------------------------------------


def test_every_request_of_every_service_sends_the_shared_user_agent(
    session: services.Session, service: respx.MockRouter
) -> None:
    location_routes(service)
    offers_route(service)
    investment_routes(service)

    services.search_locations(session, "krak")
    services.search_offers(session, "warszawa")
    services.get_investment(session, "smolna", include_history=True)
    services.get_offer(session, 2377, "smolna")

    requests: list[httpx.Request] = [call.request for call in service.calls]
    assert len(requests) == 6  # the investment of get_offer comes from the cache
    assert all(r.headers.get_list("user-agent") == [identity.USER_AGENT] for r in requests)
    assert all(r.method == "GET" for r in requests)


# --- the session -------------------------------------------------------------------------


def test_session_closes_its_connections(limiter: RequestLimiter) -> None:
    with services.Session(limiter=limiter) as opened:
        assert opened.closed is False

    assert opened.closed is True


def test_a_stop_in_one_service_stops_every_service_of_the_session(
    session: services.Session, service: respx.MockRouter
) -> None:
    """CLAUDE.md: after 401/403/429/challenge stop the series and report; no retries."""
    blocked = service.route(method="GET", path__startswith="/ceny-ofertowe/").respond(403)
    investment_routes(service)
    location_routes(service)

    with pytest.raises(ServiceBlockedError):
        services.search_offers(session, "warszawa")
    with pytest.raises(ServiceBlockedError, match="restartu procesu"):
        services.get_investment(session, "smolna")
    with pytest.raises(ServiceBlockedError, match="restartu procesu"):
        services.search_locations(session, "krak")

    assert blocked.call_count == 1
    assert service.calls.call_count == 1


def test_a_429_keeps_its_pause_in_the_repeated_error(
    session: services.Session, service: respx.MockRouter
) -> None:
    service.get(INVESTMENT).respond(429, headers={"Retry-After": "300"})

    with pytest.raises(RateLimitedError):
        services.get_investment(session, "smolna")
    with pytest.raises(RateLimitedError) as again:
        services.get_offer(session, 2377, "smolna")

    assert again.value.pause_seconds == 300
    assert service.calls.call_count == 1


def test_a_new_session_waits_for_the_pause_of_the_old_one(
    session: services.Session, limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    """The pause after a 429 is in the shared limiter, so a new process waits for it."""
    service.get(INVESTMENT).respond(429, headers={"Retry-After": "300"})
    with pytest.raises(RateLimitedError):
        services.get_investment(session, "smolna")
    transport.testing_only_reset_stop()  # what a new process starts with

    with services.Session(limiter=limiter) as fresh, pytest.raises(LimiterWaitError):
        services.get_investment(fresh, "smolna")

    assert service.calls.call_count == 1


def test_a_stop_in_one_session_stops_every_session_of_the_process(
    session: services.Session, limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    """The latch is per process: "przerwana do restartu procesu" holds for a new session."""
    service.get(INVESTMENT).respond(403)
    cities, suggestions = location_routes(service)
    with pytest.raises(ServiceBlockedError):
        services.get_investment(session, "smolna")

    with (
        services.Session(limiter=limiter) as second,
        pytest.raises(ServiceBlockedError, match="restartu procesu"),
    ):
        services.search_locations(second, "krak")

    assert (cities.call_count, suggestions.call_count) == (0, 0)


def test_a_closed_session_sends_nothing(
    limiter: RequestLimiter, service: respx.MockRouter, tmp_path: Path
) -> None:
    investment_routes(service)
    opened = services.Session(limiter=limiter)
    opened.close()

    with pytest.raises(SessionClosedError, match="Session"):
        services.get_investment(opened, "smolna")

    assert service.calls.call_count == 0
    assert not (tmp_path / LOCK_FILENAME).exists()  # no limiter slot was taken
