"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.search_locations_tool``."""

import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.models.government_statistics import Dataset
from support.checks.leaks import BACKEND_NAMES
from support.providers.mcp import Sessions, call, data, has_null, keys, tools, with_client
from support.providers.routes.government_statistics import stats_routes
from support.providers.routes.investments import investment_routes
from support.providers.routes.locations import location_routes
from support.providers.routes.offers import offers_route
from support.providers.samples import body

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_search_locations(server: MCPServer[bootstrap.Session], service: respx.MockRouter) -> None:
    location_routes(service)

    result = data(call(server, "search_locations", query="krak"))

    assert (result["total"], result["returned"], result["truncated"]) == (5, 5, False)
    assert result["items"][0] == {
        "kind": "city",
        "name": "Kraków",
        "city": "Kraków",
        "city_slug": "krakow",
        "offer_count": 8082,
    }
    assert not has_null(result)


def test_search_locations_without_a_total_has_total_null(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter, sessions: Sessions
) -> None:
    """D4: total is always there, null when unknown (the only null of the results); the
    schema requires it and allows null."""
    service.get(path="/api/cities").respond(200, json=dict(body("api.cities_q"), hasMore=True))
    service.get(path="/api/location-search").respond(200, json=body("api.location_search"))

    result = data(call(server, "search_locations", query="krak"))

    assert result["total"] is None
    assert list(result)[:3] == ["total", "returned", "truncated"]
    assert (result["returned"], result["truncated"]) == (5, True)
    assert not has_null(dict(result, total=0))
    schema = tools(server)["search_locations"]["outputSchema"]
    assert "total" in schema["required"]
    assert {"type": "null"} in schema["properties"]["total"]["anyOf"]


def test_results_have_no_backend_names(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    location_routes(service)
    offers_route(service)
    investment_routes(service)
    stats_routes(service)

    async def every_tool(client: Client) -> list[CallToolResult]:
        return [
            await client.call_tool("search_locations", {"query": "krak"}),
            await client.call_tool("search_offers", {"city": "polska"}),
            await client.call_tool("get_offer", {"offer_id": 2377, "investment_slug": "smolna"}),
            await client.call_tool(
                "get_investment", {"investment_slug": "smolna", "include_history": True}
            ),
            *[
                await client.call_tool(
                    "get_government_statistics", {"location": "warszawa", "dataset": dataset}
                )
                for dataset in Dataset
            ],
        ]

    for result in with_client(server, every_tool):
        found = [key for key in keys(data(result)) if BACKEND_NAMES.search(key)]
        assert found == []
