"""``search_offers`` through the session: the real use case and adapters, the service mocked
(respx), no network."""

from typing import Any

import pytest
import respx

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.errors import (
    SERVICE_CHANGED,
    InvalidInputError,
    NotFoundError,
    UnexpectedResponseError,
)
from support.builders.offers import (
    UNKNOWN_CITY_MESSAGE,
    UNKNOWN_DISTRICT,
    WHOLE_COUNTRY_MESSAGE,
    offers_page,
    unknown_district_message,
)
from support.providers import operations
from support.providers.error_answers import removed_route
from support.providers.routes.government_statistics import stats_routes
from support.providers.routes.offers import offers_route
from support.providers.rsc import (
    OFFERS_UNKNOWN_CITY_20261031,
    OFFERS_UNKNOWN_DISTRICT_20261031,
    OFFERS_WARSZAWA_20261031,
    OFFERS_WARSZAWA_MOKOTOW_20261031,
    UNKNOWN_CITY,
    raw,
)
from support.providers.service import BASE

OFFERS_PAGE = "/ceny-ofertowe/warszawa/mieszkania"
RSC = {"Content-Type": "text/x-component"}


def sent_query(route: respx.Route) -> str:
    """The query the service got, without the ``_rsc`` token."""
    url = route.calls.last.request.url
    query = url.query.decode()
    assert query.endswith(f"_rsc={url.params['_rsc']}")
    return query.rsplit("_rsc=", 1)[0].rstrip("&")


@pytest.mark.parametrize(
    "arguments",
    [
        {"city": "warszawa"},
        {"city": "krakow", "page": 3, "per_page": 50},
        {
            "city": "krakow",
            "price_min": 400_000,
            "price_max": 700_000,
            "area_min": 40,
            "sort": "price_desc",
            "page": 2,
            "per_page": 100,
        },
        {"city": "warszawa", "district": "Praga-Południe", "status": "archived", "page": 2},
    ],
)
def test_the_list_link_is_the_request_without_its_token(
    session: bootstrap.Session, arguments: dict[str, object]
) -> None:
    with respx.mock(assert_all_mocked=True) as router:
        route = offers_route(router)

        result = operations.search_offers(session, **arguments)

    sent = route.calls.last.request.url
    query = sent.query.decode()
    assert query.endswith(f"&_rsc={sent.params['_rsc']}")
    assert (
        result.list_url
        == f"{BASE}{sent.raw_path.decode().split('?')[0]}?{query.rsplit('&_rsc=', 1)[0]}"
    )


def test_the_statistics_link_is_the_moved_page_at_the_section(session: bootstrap.Session) -> None:
    """The page of the location, at the section of the dataset (D12), where the 2.0 service
    moved it (``/statystyki/{location}/dane-rzadowe``, [P 2026-10-29]): without ``_rsc``,
    which only the request carries (an empty one)."""
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        route = stats_routes(router)["warszawa"]

        result = operations.get_government_statistics(session, "warszawa", "unemployment")

    assert route.calls.last.request.url.query.decode() == "_rsc="
    assert result.stats_url == f"{BASE}/statystyki/warszawa/dane-rzadowe#gus-bezrobocie"
    assert "_rsc" not in result.stats_url


def test_search_offers_sends_every_filter_and_reads_the_page(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """The 2.0 parameters [P 2026-10-31] (a start above 0 [W], the live suite) and the page
    as the service paged it."""
    route = offers_route(service, offers_page(total=1192, page=2, per_page=50))

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

    target = (
        f"{OFFERS_PAGE}?filterPrice=500000-700000&filterSize=40-60&sortBy=amount"
        "&sortOrder=asc&page=2&perPage=50"
    )
    assert str(route.calls.last.request.url) == f"{BASE}{target}&_rsc="
    assert route.calls.last.request.headers["rsc"] == "1"
    assert (result.total, result.returned, result.page, result.per_page) == (1192, 50, 2, 50)
    assert (result.truncated, result.pages_available) == (True, 20)
    assert result.hint is not None
    assert result.items[0].offer_id == 900_050
    assert result.items[0].investment_slug == "apartamenty-beethovena"


def test_search_offers_defaults(session: bootstrap.Session, service: respx.MockRouter) -> None:
    route = offers_route(service)

    result = operations.search_offers(session, "warszawa")

    assert route.calls.last.request.url.path == OFFERS_PAGE
    # No sortBy: the service's default order [P 2026-10-31]; page 1 (no `page`,
    # [P 2026-10-29]) and the search's own 10 (the service's default is 25 on 2.0).
    assert sent_query(route) == "perPage=10"
    assert (result.total, result.returned) == (11_672, 10)


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
    route = offers_route(service)

    operations.search_offers(session, "warszawa", **filters)

    assert sent_query(route) == f"{query}&perPage=10"


@pytest.mark.parametrize("per_page", [10, 50, 100])
def test_search_offers_accepts_the_page_sizes_of_the_service(
    session: bootstrap.Session, service: respx.MockRouter, per_page: int
) -> None:
    route = offers_route(service)

    operations.search_offers(session, "warszawa", page=20, per_page=per_page)

    assert sent_query(route) == f"page=20&perPage={per_page}"


def test_search_offers_trims_the_city_slug(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """Spaces around a slug are trimmed, nothing else is guessed (capitals, names)."""
    route = offers_route(service)

    operations.search_offers(session, " warszawa ")

    assert route.calls.last.request.url.path == OFFERS_PAGE


@pytest.mark.parametrize(
    "arguments", [{"city": "polska"}, {"city": "polska", "district": "Mokotów", "page": 2}]
)
def test_search_offers_refuses_the_whole_country_without_requests(
    session: bootstrap.Session, service: respx.MockRouter, arguments: dict[str, Any]
) -> None:
    """[P 2026-10-29] the list of Poland is a list of cities (308 to
    ``/ceny-ofertowe/polska/miasta``): refused before anything is sent."""
    with pytest.raises(InvalidInputError) as caught:
        operations.search_offers(session, **arguments)

    assert str(caught.value) == WHOLE_COUNTRY_MESSAGE
    assert service.calls.call_count == 0


def test_search_offers_of_a_district_reads_the_district_list(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """[P 2026-10-31] the district's own list (the real page of Mokotów, 959 offers), at the
    slug of the district's name; the link is that list."""
    route = service.get(path="/ceny-ofertowe/warszawa/mokotow/mieszkania").respond(
        200, content=raw(OFFERS_WARSZAWA_MOKOTOW_20261031), headers=RSC
    )

    result = operations.search_offers(session, "warszawa", district=" Mokotów ")

    assert sent_query(route) == "perPage=10"
    assert (result.total, result.returned) == (959, 25)
    assert result.list_url == f"{BASE}/ceny-ofertowe/warszawa/mokotow/mieszkania?perPage=10"


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
        ({"district": " M "}, "district"),
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


@pytest.mark.parametrize("district", [None, "Mokotów"])
def test_search_offers_of_a_removed_page_is_a_changed_service(
    session: bootstrap.Session, service: respx.MockRouter, district: str | None
) -> None:
    """D21: an HTML 404, the Next.js not-found page of a removed route ([P 2026-10-30] on
    the /api routes; on a page route never seen, [W]), is a changed service, never an
    unknown city or district: both lists answer those with a 200 and the 404 marker
    [P 2026-10-31] (below)."""
    service.route(method="GET").respond(404, **removed_route())

    with pytest.raises(UnexpectedResponseError) as caught:
        operations.search_offers(session, "atlantyda", district=district)

    assert str(caught.value).endswith(SERVICE_CHANGED)
    assert "search_locations" not in str(caught.value)


def test_search_offers_of_an_unknown_city_says_so(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """What the service answers for an unknown city on the offers list: HTTP 200 with
    Next.js's 404 marker (``NEXT_HTTP_ERROR_FALLBACK;404``), not a 404 [P 2026-10-31,
    endpoints.md section 9, "Pages"]."""
    service.route(method="GET").respond(200, content=raw(OFFERS_UNKNOWN_CITY_20261031), headers=RSC)

    with pytest.raises(NotFoundError) as caught:
        operations.search_offers(session, UNKNOWN_CITY)

    assert str(caught.value) == UNKNOWN_CITY_MESSAGE
    assert SERVICE_CHANGED not in str(caught.value)
    assert caught.value.detail is not None
    assert "NEXT_HTTP_ERROR_FALLBACK;404" in caught.value.detail


def test_search_offers_of_an_unknown_district_says_so(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """The district's list of a district the city does not have: 200 with the 404 marker
    [P 2026-10-31]. The message sends the model to the districts of search_locations."""
    route = service.get(path="/ceny-ofertowe/warszawa/nieistniejaca-dzielnica/mieszkania").respond(
        200, content=raw(OFFERS_UNKNOWN_DISTRICT_20261031), headers=RSC
    )

    with pytest.raises(NotFoundError) as caught:
        operations.search_offers(session, "warszawa", district=UNKNOWN_DISTRICT)

    assert route.call_count == 1
    assert str(caught.value) == unknown_district_message()
    assert SERVICE_CHANGED not in str(caught.value)


def test_search_offers_of_a_district_without_a_slug_says_so_without_a_request(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    with pytest.raises(NotFoundError) as caught:
        operations.search_offers(session, "warszawa", district="Ωμέγα")

    assert str(caught.value) == unknown_district_message("Ωμέγα")
    assert service.calls.call_count == 0


def test_search_offers_on_the_real_page(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """The real page as sent: captured without ``perPage``, so with the service's own 25."""
    service.route(method="GET").respond(200, content=raw(OFFERS_WARSZAWA_20261031), headers=RSC)

    result = operations.search_offers(session, "warszawa")

    assert (result.total, result.returned, result.page, result.per_page) == (11_672, 25, 1, 25)
    assert (result.truncated, result.pages_available) == (True, 20)
    assert all(item.offer_id > 0 and item.investment_slug for item in result.items)
    assert len({item.offer_id for item in result.items}) == 25
