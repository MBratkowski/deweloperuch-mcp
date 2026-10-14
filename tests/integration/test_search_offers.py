"""``search_offers`` through the session: the real use case and adapters, the service mocked
(respx), no network."""

from typing import Any

import pytest
import respx

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.errors import SERVICE_CHANGED, InvalidInputError, NotFoundError
from deweloperuch_mcp.flight import rsc_token
from support.providers import operations
from support.providers.routes.government_statistics import stats_routes
from support.providers.routes.offers import sample_offers_route
from support.providers.rsc import OFFERS_UNKNOWN_CITY, UNKNOWN_CITY, offers_payload, raw
from support.providers.samples import request_target
from support.providers.service import BASE

OFFERS_PAGE = "/ceny-ofertowe/warszawa/mieszkania"


def sent_query(route: respx.Route) -> str:
    """The query the service got, without the ``_rsc`` token."""
    url = route.calls.last.request.url
    query = url.query.decode()
    assert query.endswith(f"_rsc={url.params['_rsc']}")
    return query.rsplit("_rsc=", 1)[0].rstrip("&")


UNKNOWN_CITY_MESSAGE = (
    f"Serwis nie zna miasta {UNKNOWN_CITY!r}. Podaj city_slug z search_locations albo polska "
    "(cały kraj)."
)


@pytest.mark.parametrize(
    "arguments",
    [
        {"city": "warszawa"},
        {"city": "polska", "page": 3, "per_page": 50},
        {
            "city": "krakow",
            "price_min": 400_000,
            "price_max": 700_000,
            "area_min": 40,
            "sort": "price_desc",
            "page": 2,
            "per_page": 100,
        },
    ],
)
def test_the_list_link_is_the_request_without_its_token(
    session: bootstrap.Session, arguments: dict[str, object]
) -> None:
    with respx.mock(assert_all_mocked=True) as router:
        route = router.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
            200, content=offers_payload(), headers={"Content-Type": "text/x-component"}
        )

        result = operations.search_offers(session, **arguments)

    sent = route.calls.last.request.url
    query = sent.query.decode()
    assert query.endswith(f"&_rsc={sent.params['_rsc']}")
    assert (
        result.list_url
        == f"{BASE}{sent.raw_path.decode().split('?')[0]}?{query.rsplit('&_rsc=', 1)[0]}"
    )


def test_the_statistics_link_is_the_request_without_its_token(session: bootstrap.Session) -> None:
    """The page the service read, at the section of the dataset (D12)."""
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        route = stats_routes(router)["warszawa"]

        result = operations.get_government_statistics(session, "warszawa", "unemployment")

    sent = route.calls.last.request.url
    assert sent.query.decode() == f"_rsc={sent.params['_rsc']}"
    assert result.stats_url == f"{BASE}{sent.raw_path.decode().split('?')[0]}#gus-bezrobocie"
    assert "_rsc" not in result.stats_url


def test_search_offers_sends_the_filters_of_the_filtered_sample(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    route = sample_offers_route(service, "page.offers_list.filtered")

    result = operations.search_offers(
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


def test_search_offers_defaults(session: bootstrap.Session, service: respx.MockRouter) -> None:
    route = sample_offers_route(service)

    result = operations.search_offers(session, "warszawa")

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
    session: bootstrap.Session, service: respx.MockRouter, filters: dict[str, Any], query: str
) -> None:
    """Open ranges: 0 below, the UI sentinels above ([P z kodu], pages-rsc.md)."""
    route = sample_offers_route(service)

    operations.search_offers(session, "warszawa", **filters)

    assert sent_query(route) == f"{query}&page=1&perPage=10"


@pytest.mark.parametrize("per_page", [10, 50, 100])
def test_search_offers_accepts_the_page_sizes_of_the_service(
    session: bootstrap.Session, service: respx.MockRouter, per_page: int
) -> None:
    route = sample_offers_route(service)

    operations.search_offers(session, "warszawa", page=20, per_page=per_page)

    assert sent_query(route) == f"page=20&perPage={per_page}"


def test_search_offers_trims_the_city_slug(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """Spaces around a slug are trimmed, nothing else is guessed (capitals, names)."""
    route = sample_offers_route(service)

    operations.search_offers(session, " warszawa ")

    assert route.calls.last.request.url.path == OFFERS_PAGE


def test_search_offers_accepts_the_whole_country(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    route = sample_offers_route(service)

    operations.search_offers(session, "polska")

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
        ({"sort": "rooms_asc"}, "sort"),
        ({"sort": "amount"}, "sort"),
        ({"sort": ["price_asc"]}, "sort"),
        ({"city": "Kraków"}, "city"),
        ({"city": "Warszawa"}, "city"),
        ({"city": "KRAKOW"}, "city"),
        ({"city": ""}, "city"),
        ({"city": "warszawa/../x"}, "city"),
        ({"city": None}, "city"),
    ],
)
def test_search_offers_rejects_bad_input_without_requests(
    session: bootstrap.Session, service: respx.MockRouter, arguments: dict[str, Any], message: str
) -> None:
    arguments = {"city": "warszawa", **arguments}

    with pytest.raises(InvalidInputError, match=message):
        operations.search_offers(session, **arguments)

    assert service.calls.call_count == 0


def test_search_offers_unknown_city_points_to_search_locations(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    service.route(method="GET").respond(404)

    with pytest.raises(NotFoundError, match="search_locations"):
        operations.search_offers(session, "atlantyda")


def test_search_offers_of_an_unknown_city_says_so(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """What the service really answers (HTTP 200, the 404 marker), not a 404."""
    service.route(method="GET").respond(
        200, content=raw(OFFERS_UNKNOWN_CITY), headers={"Content-Type": "text/x-component"}
    )

    with pytest.raises(NotFoundError) as caught:
        operations.search_offers(session, UNKNOWN_CITY)

    assert str(caught.value) == UNKNOWN_CITY_MESSAGE
    assert SERVICE_CHANGED not in str(caught.value)
    assert caught.value.detail is not None
    assert "NEXT_HTTP_ERROR_FALLBACK;404" in caught.value.detail


def test_search_offers_on_the_real_page(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    service.route(method="GET").respond(
        200, content=offers_payload(), headers={"Content-Type": "text/x-component"}
    )

    result = operations.search_offers(session, "warszawa")

    assert (result.total, result.returned, result.page, result.per_page) == (13324, 10, 1, 10)
    assert (result.truncated, result.pages_available) == (True, 20)
    assert all(item.offer_id > 0 and item.investment_slug for item in result.items)
    assert len({item.offer_id for item in result.items}) == 10
