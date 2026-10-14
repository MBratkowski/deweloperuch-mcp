"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.get_investment_tool``."""

import pytest
import respx
from mcp.server.mcpserver import MCPServer

from deweloperuch_mcp import bootstrap
from support.builders.investments import investment_with_offers
from support.providers.mcp import call, data, has_null, text
from support.providers.routes.investments import INVESTMENT, investment_routes

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_get_investment_defaults_to_20_offers_without_history(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    _, history, _ = investment_routes(service, investment_with_offers(60))

    result = data(call(server, "get_investment", investment_slug="smolna"))

    assert len(result["offers"]) == 20
    assert (result["offers_returned"], result["offers_omitted"], result["truncated"]) == (
        20,
        40,
        True,
    )
    assert result["offers_total"] == 16  # as the service counts them
    assert all("price_history" not in offer for offer in result["offers"])
    assert history.call_count == 0
    assert not has_null(result)


def test_get_investment_with_history(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    _, history, _ = investment_routes(service)

    result = data(
        call(server, "get_investment", investment_slug="smolna", include_history=True, limit=1)
    )

    assert history.call_count == 1
    counts = (result["offers_returned"], result["offers_omitted"], result["truncated"])
    assert counts == (1, 2, True)
    assert result["offers"][0]["price_history"] == [
        {"date": "2026-10-03", "kind": "offer", "price": 1679796.0}
    ]


def test_get_investment_limit_0_is_the_summary(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    investment_routes(service)

    result = data(call(server, "get_investment", investment_slug="smolna", limit=0))

    assert (result["offers"], result["offers_returned"], result["offers_omitted"]) == ([], 0, 3)
    assert result["truncated"] is True


def test_get_investment_with_every_offer_is_not_truncated(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    investment_routes(service)

    result = data(call(server, "get_investment", investment_slug="smolna"))

    assert (result["offers_returned"], result["offers_omitted"], result["truncated"]) == (
        3,
        0,
        False,
    )


def test_not_found_points_to_the_tool_with_the_slugs(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    service.get(INVESTMENT).respond(404)

    result = call(server, "get_investment", investment_slug="smolna")

    assert result.is_error is True
    assert "search_offers" in text(result)
