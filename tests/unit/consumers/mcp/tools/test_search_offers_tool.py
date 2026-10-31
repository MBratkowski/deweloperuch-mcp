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
from support.builders.offers import COMPACT_OFFER, UNKNOWN_CITY_MESSAGE, offers_page
from support.checks.leaks import LEAKS
from support.providers.mcp import call, data, has_null, text, tools, with_client
from support.providers.routes.offers import offers_route, unknown_city_route
from support.providers.rsc import UNKNOWN_CITY
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
    assert "search_locations" in fields["district"]["description"]
    assert schema["additionalProperties"] is False
    assert fields["sort"]["default"] is None
    assert "nie jest gwarantowana" in fields["sort"]["description"]
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
    """In MCP only 10 and 50: [P] values (D4) that keep a page readable. The one test of
    the page sizes: the others (and the subprocess smoke test) do not depend on them."""
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
    route = offers_route(service)  # the real Warsaw page: 10 offers

    result = data(call(server, "search_offers", city="warszawa"))

    params = route.calls.last.request.url.params
    # page 1 is the canonical URL without ``page`` (the service redirects ``page=1``)
    assert (params["perPage"], "page" in params, "sortBy" in params) == ("10", False, False)
    assert (result["total"], result["returned"], result["truncated"]) == (13324, 10, True)
    assert result["items"][0] == {
        "offer_id": 4397,
        "investment_slug": "nowy-targowek-vi",
        "name": "D1.1.1.4",
        "price": 994012.0,
        "area_m2": 55.25,
        "price_per_m2": 17991.17,
        "status": "active",
        "investment_name": "Nowy Targówek VI",
        "investment_url": PAGES + "/warszawa/deweloperzy/atal/nowy-targowek-vi",
        "developer_name": "ATAL S.A.",
        "developer_slug": "atal",
        "last_price_change_kind": "increase",
        "last_price_change_pct": 5.89,
        "price_change_since_start_pct": -0.6,
    }
    assert result["list_url"] == PAGES + "/warszawa/mieszkania?perPage=10"
    assert all(set(item) <= COMPACT_OFFER for item in result["items"])
    assert not has_null(result)


def test_search_offers_in_the_whole_country_keeps_the_city(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    offers_route(service)

    result = data(call(server, "search_offers", city="polska"))

    assert (result["items"][0]["city"], result["items"][0]["city_slug"]) == ("Warszawa", "warszawa")


def test_search_offers_passes_every_argument(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    route = offers_route(service, offers_page("page.offers_list.filtered"))

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


@pytest.mark.parametrize("per_page", [10, 50])
def test_truncated_hint_says_to_narrow_the_filters(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter, per_page: int
) -> None:
    """A bigger page would not narrow 13 324 offers down; the hint does not suggest it."""
    offers_route(service, offers_page(count=per_page))

    result = data(call(server, "search_offers", city="warszawa", per_page=per_page))

    shown = 20 * per_page
    assert result["hint"] == (
        f"Pasujących ofert jest 13324, a można przejrzeć najwyżej 20 stron po {per_page} "
        f"({shown}). Zawęź filtry (cena, metraż)."
    )


@pytest.mark.parametrize("city", ["Kraków", "Warszawa", "KRAKOW", ""])
def test_search_offers_city_that_is_not_a_slug_points_to_search_locations(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter, city: str
) -> None:
    """Mistakes a model makes with `city`: a name, capitals, nothing. No request."""
    result = call(server, "search_offers", city=city)

    assert result.is_error is True
    assert text(result) == (
        "city: oczekiwano slug miasta (np. warszawa) albo polska; slug podaje "
        f"search_locations; podano {city!r}."
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
    assert sent.params.multi_items()[:-1] == [
        ("filterPricePerM2", "12000-999999"),
        ("filterDistrict", "Mokotów"),
        ("filterPriceChange", "decrease"),
        ("filterStatus", "archived"),
        ("sortBy", "size"),
        ("sortOrder", "desc"),
        ("perPage", "10"),
    ]
    assert result["list_url"] == (
        f"{PAGES}/warszawa/mieszkania?filterPricePerM2=12000-999999&filterDistrict="
        "Mokot%C3%B3w&filterPriceChange=decrease&filterStatus=archived&sortBy=size"
        "&sortOrder=desc&perPage=10"
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            {"city": "polska", "district": "Mokotów"},
            "district działa tylko z jednym miastem",
        ),
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
        assert route.calls.last.request.url.params.multi_items()[:-1] == [
            ("perPage", "10"),
        ]
    else:
        assert result.is_error is True and text(result).startswith(message)
        assert service.calls.call_count == 0
