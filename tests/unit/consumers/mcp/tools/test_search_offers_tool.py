"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.search_offers_tool``."""

from typing import Any, get_args

import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.consumers.mcp.support import inputs
from deweloperuch_mcp.consumers.shared.choices import PageSizeChoice, SortChoice, StatusChoice
from deweloperuch_mcp.models.values import (
    BROWSABLE_PAGES,
    DEFAULT_PAGE_SIZE,
    PAGE_SIZES,
    AmountPln,
    AreaM2,
    OfferSort,
    OfferStatus,
    PricePerM2Pln,
)
from support.builders.offers import (
    COMPACT_OFFER,
    UNKNOWN_CITY_MESSAGE,
    UNKNOWN_DISTRICT,
    WHOLE_COUNTRY_MESSAGE,
    offers_page,
    unknown_district_message,
)
from support.checks.leaks import LEAKS
from support.providers.error_answers import CHANGED_SERVICE, removed_route
from support.providers.mcp import call, data, has_null, text, tools, with_client
from support.providers.routes.offers import offers_route, unknown_city_route
from support.providers.rsc import OFFERS_UNKNOWN_DISTRICT_20261031, UNKNOWN_CITY, raw
from support.providers.service import PAGES

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_search_offers_input_schema(server: MCPServer[bootstrap.Session]) -> None:
    schema = tools(server)["search_offers"]["inputSchema"]
    fields = schema["properties"]

    assert schema["required"] == ["city"]
    assert fields["city"]["type"] == "string"
    assert fields["sort"]["anyOf"][0] == {"enum": list(get_args(SortChoice)), "type": "string"}
    assert get_args(SortChoice) == tuple(sort.value for sort in OfferSort)
    assert fields["status"]["anyOf"][0] == {"enum": ["active", "archived", "all"], "type": "string"}
    assert get_args(StatusChoice) == tuple(status.value for status in OfferStatus)
    assert fields["status"]["default"] == "active"
    assert (fields["price_dropped"]["type"], fields["price_dropped"]["default"]) == (
        "boolean",
        False,
    )
    assert "nie polska" in fields["city"]["description"]
    assert "search_locations (kind=district" in fields["district"]["description"]
    assert "polska" not in fields["district"]["description"]
    assert schema["additionalProperties"] is False
    assert fields["sort"]["default"] is None
    assert "nie jest gwarantowana" in fields["sort"]["description"]
    assert "więc do przeglądu miasta podaj sort" in fields["sort"]["description"]
    # T72: the total of `all` is not the sum of the other two [P 2026-10-31]
    assert (
        "total przy all może być większy niż suma active i archived"
        in (fields["status"]["description"])
    )
    assert "dalej serwis nie udostępnia: zawęź filtry" in fields["page"]["description"]
    assert fields["per_page"]["default"] == 10  # the values: test_mcp_page_sizes_...
    assert (fields["page"]["minimum"], fields["page"]["maximum"]) == (1, BROWSABLE_PAGES)
    assert fields["page"]["default"] == 1
    for name, limit in (
        ("price_min", AmountPln.MAX),
        ("price_max", AmountPln.MAX),
        ("area_min", AreaM2.MAX),
        ("area_max", AreaM2.MAX),
        ("price_per_m2_min", PricePerM2Pln.MAX),
        ("price_per_m2_max", PricePerM2Pln.MAX),
    ):
        assert fields[name]["anyOf"][0] == {"maximum": limit, "minimum": 0, "type": "integer"}
        assert fields[name]["default"] is None


def test_mcp_page_sizes_are_confirmed_ones(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """In MCP only 10 and 50: values that keep a page readable (D4); 10 [P 2026-10-31], 50
    [W] on 2.0 (tests/e2e/test_live_mcp.py). The one test of the page sizes: the others (and
    the subprocess smoke test) do not depend on them."""
    assert get_args(inputs.McpPerPage) == (10, 50)
    assert set(get_args(inputs.McpPerPage)) <= set(PAGE_SIZES)
    assert get_args(PageSizeChoice) == PAGE_SIZES
    assert DEFAULT_PAGE_SIZE == 10
    assert tools(server)["search_offers"]["inputSchema"]["properties"]["per_page"]["enum"] == [
        10,
        50,
    ]

    async def too_big(client: Client) -> list[CallToolResult]:
        return [
            await client.call_tool("search_offers", {"city": "warszawa", "per_page": value})
            for value in (100, "100")
        ]

    for result in with_client(server, too_big):
        assert result.is_error is True and "per_page" in text(result)
    assert service.calls.call_count == 0


def test_search_offers_with_defaults_lists_compact_offers(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    route = offers_route(service)  # the real Warsaw page, its first 10 offers

    result = data(call(server, "search_offers", city="warszawa"))

    params = route.calls.last.request.url.params
    # [P 2026-10-29] the first page goes without `page` (the service redirects `page=1`).
    assert (params["perPage"], "page" in params, "sortBy" in params) == ("10", False, False)
    assert (result["total"], result["returned"], result["truncated"]) == (11672, 10, True)
    assert result["items"][0] == {
        "offer_id": 4487,
        "investment_slug": "apartamenty-beethovena",
        "name": "A2",
        "price": 810660.0,
        "area_m2": 35.4,
        "price_per_m2": 22900.0,
        "status": "active",
        "investment_name": "Apartamenty Beethovena",
        "district": "Mokotów",
        "investment_url": PAGES + "/warszawa/deweloperzy/dom-development/apartamenty-beethovena",
        "developer_name": "Dom Development S.A.",
        "developer_slug": "dom-development",
        "last_price_change_kind": "increase",
        "last_price_change_pct": 6.51,
        "price_change_since_start_pct": 0.08,
    }
    assert result["list_url"] == PAGES + "/warszawa/mieszkania?perPage=10"
    assert all(set(item) <= COMPACT_OFFER for item in result["items"])
    assert not has_null(result)


@pytest.mark.parametrize("district", [None, "Mokotów"])
def test_search_offers_of_the_whole_country_is_refused_without_a_request(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter, district: str | None
) -> None:
    """[P 2026-10-29] the service's list of Poland is a list of cities: the model learns to
    search one city at a time."""
    result = call(server, "search_offers", city="polska", district=district)

    assert result.is_error is True
    assert text(result) == WHOLE_COUNTRY_MESSAGE
    assert service.calls.call_count == 0


def test_search_offers_passes_every_argument(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    route = offers_route(service, offers_page(total=1192, page=2, per_page=50))

    data(
        call(
            server,
            "search_offers",
            city="warszawa",
            price_min=500_000,
            price_max=700_000,
            area_min=40,
            area_max=60,
            sort="price_asc",
            page=2,
            per_page=50,
        )
    )

    params = route.calls.last.request.url.params
    assert dict(params.multi_items()) == {
        "filterPrice": "500000-700000",
        "filterSize": "40-60",
        "sortBy": "amount",
        "sortOrder": "asc",
        "page": "2",
        "perPage": "50",
        "_rsc": params["_rsc"],
    }


@pytest.mark.parametrize(
    ("per_page", "district", "filters"),
    [
        (10, None, "dzielnica, cena, metraż"),
        (50, None, "dzielnica, cena, metraż"),
        (10, "Mokotów", "cena, metraż"),
    ],
)
def test_truncated_hint_says_to_narrow_the_filters(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    per_page: int,
    district: str | None,
    filters: str,
) -> None:
    """A bigger page would not narrow 11 672 offers down; the hint does not suggest it. A
    city's list is narrowed by a district first."""
    offers_route(service, offers_page(per_page=per_page))

    result = data(
        call(server, "search_offers", city="warszawa", district=district, per_page=per_page)
    )

    shown = 20 * per_page
    assert result["hint"] == (
        f"Pasujących ofert jest 11672, a można przejrzeć najwyżej 20 stron po {per_page} "
        f"({shown}). Zawęź filtry ({filters})."
    )


@pytest.mark.parametrize("city", ["Kraków", "Warszawa", "KRAKOW", "Polska", ""])
def test_search_offers_city_that_is_not_a_slug_points_to_search_locations(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter, city: str
) -> None:
    """Mistakes a model makes with `city`: a name, capitals, nothing. No request, and no
    hint at the whole country, which the search refuses."""
    result = call(server, "search_offers", city=city)

    assert result.is_error is True
    assert text(result) == (
        "city: oczekiwano city_slug jednego miasta (małe litery bez polskich znaków, np. "
        f"warszawa, krakow), nie polska; slug podaje search_locations; podano {city!r}."
    )
    assert service.calls.call_count == 0


def test_search_offers_trims_spaces_around_the_city(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    route = offers_route(service)

    result = data(call(server, "search_offers", city=" warszawa "))

    assert route.calls.last.request.url.path == "/ceny-ofertowe/warszawa/mieszkania"
    # The link is built from the slug as normalized, like the request: no %20.
    assert result["list_url"] == PAGES + "/warszawa/mieszkania?perPage=10"


def test_search_offers_of_an_unknown_city_is_an_error_that_says_so(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """The real answer (HTTP 200, Next.js's 404 marker) is "no such city", not "the
    service may have changed": the model can fix the argument."""
    unknown_city_route(service)

    result = call(server, "search_offers", city=UNKNOWN_CITY)

    assert result.is_error is True
    assert text(result) == UNKNOWN_CITY_MESSAGE
    assert not LEAKS.search(text(result))


def test_search_offers_in_an_unknown_district_is_an_error_that_says_so(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """The district's list of a district the city does not have (the real 200 with the 404
    marker, [P 2026-10-31]): the model is sent to the districts of search_locations."""
    service.get(path="/ceny-ofertowe/warszawa/nieistniejaca-dzielnica/mieszkania").respond(
        200,
        content=raw(OFFERS_UNKNOWN_DISTRICT_20261031),
        headers={"Content-Type": "text/x-component"},
    )

    result = call(server, "search_offers", city="warszawa", district=UNKNOWN_DISTRICT)

    assert result.is_error is True
    assert text(result) == unknown_district_message()
    assert not LEAKS.search(text(result))


@pytest.mark.parametrize(
    "answer",
    [
        # [P 2026-10-29] what an RSC request with another `_rsc` got from the 2.0 service
        {"status_code": 307, "headers": {"Location": "/ceny-ofertowe/warszawa/mieszkania?_rsc="}},
        {"status_code": 404, **removed_route()},
        {"status_code": 410, **removed_route()},
    ],
)
def test_a_moved_or_removed_list_is_a_changed_service_not_a_wrong_city(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter, answer: dict[str, Any]
) -> None:
    """D21: one text for a redirect, a removed route and a 410. It names the operation and
    casts no doubt on the city: the model reports the change instead of trying other slugs."""
    service.route(method="GET", path__startswith="/ceny-ofertowe/").respond(**answer)

    result = call(server, "search_offers", city="warszawa")

    assert result.is_error is True
    assert text(result) == f"Wyszukiwanie ofert w 'warszawa': {CHANGED_SERVICE}"


def test_invalid_input_is_a_tool_error_that_says_what_to_fix(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    result = call(server, "search_offers", city="warszawa", price_min=700_000, price_max=500_000)

    assert result.is_error is True
    assert text(result) == (
        "price_min (700000) jest większe niż price_max (500000); zamień je miejscami."
    )
    assert service.calls.call_count == 0


def test_search_offers_sends_the_new_filters(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    route = offers_route(service)

    result = data(
        call(
            server,
            "search_offers",
            city="warszawa",
            price_per_m2_min="12000",
            district=" Mokotów ",
            price_dropped=True,
            status="archived",
            sort="area_desc",
        )
    )

    sent = route.calls.last.request.url
    # [P 2026-10-31] the district is its own list, at its slug; the parameters as on the
    # city's list ([W] on that route, T73).
    assert sent.path == "/ceny-ofertowe/warszawa/mokotow/mieszkania"
    assert sent.params.multi_items()[:-1] == [
        ("filterPricePerM2", "12000-999999"),
        ("filterPriceChange", "decrease"),
        ("filterStatus", "archived"),
        ("sortBy", "size"),
        ("sortOrder", "desc"),
        ("perPage", "10"),
    ]
    assert result["list_url"] == (
        f"{PAGES}/warszawa/mokotow/mieszkania?filterPricePerM2=12000-999999"
        "&filterPriceChange=decrease&filterStatus=archived&sortBy=size&sortOrder=desc"
        "&perPage=10"
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"city": "polska", "district": "Mokotów"}, "city=polska nie działa"),
        ({"city": "warszawa", "district": None, "status": ""}, None),
        ({"city": "warszawa", "price_dropped": None}, None),
    ],
)
def test_search_offers_new_arguments_as_models_send_them(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    arguments: dict[str, Any],
    message: str | None,
) -> None:
    route = offers_route(service)

    result = call(server, "search_offers", **arguments)

    if message is None:
        assert result.is_error is False
        assert route.calls.last.request.url.params.multi_items()[:-1] == [("perPage", "10")]
    else:
        assert result.is_error is True and text(result).startswith(message)
        assert service.calls.call_count == 0


def test_search_offers_description_and_output_schema(server: MCPServer[bootstrap.Session]) -> None:
    """What the model reads about a search: one city or its district, no rooms nor floor
    filter (the list does not give them), the items' district, the kinds of the last
    change (``NEW_OFFER`` [P 2026-10-31]) and what an item's ``name`` is."""
    tool = tools(server)["search_offers"]
    item = tool["outputSchema"]["$defs"]["OfferItem"]["properties"]

    assert "w jednym mieście albo w jego dzielnicy; city=polska nie działa" in tool["description"]
    assert "lista ofert nie filtruje po pokojach ani piętrze" in tool["description"]
    assert "inwestycja z dzielnicą" in tool["description"]
    assert "można ją podać w district" in item["district"]["description"]
    assert (
        "new_offer (oferta bez zmiany ceny od dodania)"
        in (item["last_price_change_kind"]["description"])
    )
    assert item["name"]["description"].startswith("Oznaczenie mieszkania u dewelopera")
