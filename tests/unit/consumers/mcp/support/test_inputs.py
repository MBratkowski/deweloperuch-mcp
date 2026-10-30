"""Tests of ``deweloperuch_mcp.consumers.mcp.support.inputs``."""

from typing import Any

import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from deweloperuch_mcp import bootstrap
from support.builders.investments import investment_with_offers
from support.providers.mcp import call, data, text, with_client
from support.providers.routes.investments import investment_routes
from support.providers.routes.offers import offers_route

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


@pytest.mark.parametrize(
    ("arguments", "sent"),
    [
        ({"per_page": "10"}, {"perPage": "10"}),
        ({"per_page": "50"}, {"perPage": "50"}),
        ({"page": "2"}, {"page": "2"}),
        ({"price_min": "500000"}, {"filterPrice": "500000-99999999"}),
        ({"area_max": " 60 "}, {"filterSize": "0-60"}),
        ({"price_min": "", "price_max": "700000"}, {"filterPrice": "0-700000"}),
        ({"price_max": " "}, {}),
        ({"price_min": None}, {}),
        ({"sort": ""}, {}),
        ({"sort": None}, {}),
        ({"sort": " price_asc "}, {"sortBy": "amount", "sortOrder": "asc"}),
        # null for an argument with a default is the default
        ({"page": None, "per_page": None}, {"perPage": "10"}),
    ],
)
def test_numbers_as_text_and_empty_optional_arguments_are_accepted(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    arguments: dict[str, Any],
    sent: dict[str, str],
) -> None:
    route = offers_route(service)

    data(call(server, "search_offers", city="warszawa", **arguments))

    params = dict(route.calls.last.request.url.params.multi_items())
    for name, value in sent.items():
        assert params[name] == value
    for name in ("sortBy", "filterPrice", "filterSize"):
        if name not in sent:
            assert name not in params


def test_limit_and_offer_id_as_text_are_accepted(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    investment_routes(service)

    async def two(client: Client) -> tuple[CallToolResult, CallToolResult]:
        return (
            await client.call_tool("get_investment", {"investment_slug": "smolna", "limit": "1"}),
            await client.call_tool("get_offer", {"offer_id": "2377", "investment_slug": "smolna"}),
        )

    investment, offer = with_client(server, two)

    assert data(investment)["offers_returned"] == 1
    assert data(offer)["offer_id"] == 2377


def test_null_limit_and_history_are_the_defaults(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    _, history, _ = investment_routes(service, investment_with_offers(30))

    result = data(
        call(
            server,
            "get_investment",
            investment_slug="smolna",
            limit=None,
            include_history=None,
        )
    )

    assert (result["offers_returned"], result["offers_omitted"]) == (20, 10)
    assert history.call_count == 0


@pytest.mark.parametrize(
    ("tool", "arguments", "field"),
    [
        ("search_offers", {"city": "warszawa", "price_min": True}, "price_min"),
        ("search_offers", {"city": "warszawa", "area_max": False}, "area_max"),
        ("search_offers", {"city": "warszawa", "page": True}, "page"),
        ("search_offers", {"city": "warszawa", "per_page": True}, "per_page"),
        ("search_offers", {"city": "warszawa", "price_min": "500000.0"}, "price_min"),
        ("search_offers", {"city": "warszawa", "page": "2.0"}, "page"),
        ("search_offers", {"city": "warszawa", "per_page": "10.0"}, "per_page"),
        ("get_investment", {"investment_slug": "smolna", "limit": "5.0"}, "limit"),
        ("get_offer", {"offer_id": "2377.0", "investment_slug": "smolna"}, "offer_id"),
        ("search_offers", {"city": "warszawa", "price_min": "dużo"}, "price_min"),
        ("search_offers", {"city": "warszawa", "page": ""}, "page"),
        ("get_investment", {"investment_slug": "smolna", "limit": False}, "limit"),
        ("get_investment", {"investment_slug": "smolna", "limit": 201}, "limit"),
        ("get_offer", {"offer_id": True, "investment_slug": "smolna"}, "offer_id"),
    ],
)
def test_booleans_and_other_values_off_the_schema_are_rejected(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    tool: str,
    arguments: dict[str, Any],
    field: str,
) -> None:
    result = call(server, tool, **arguments)

    assert result.is_error is True
    assert field in text(result)
    assert service.calls.call_count == 0
