"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.get_investment_tool``."""

import pytest
import respx
from mcp.server.mcpserver import MCPServer

from deweloperuch_mcp import bootstrap
from support.builders.investments import investment_with_offers
from support.providers.error_answers import unknown_entity
from support.providers.mcp import call, data, has_null, text
from support.providers.routes.investments import (
    INVESTMENT,
    investment_routes,
    smolna_with_events,
)

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
    investment, history, _ = investment_routes(service, smolna_with_events())

    result = data(
        call(server, "get_investment", investment_slug="smolna", include_history=True, limit=3)
    )

    assert (investment.call_count, history.call_count) == (1, 0)  # the history comes with it
    counts = (result["offers_returned"], result["offers_omitted"], result["truncated"])
    assert counts == (3, 14, True)
    assert [offer["offer_id"] for offer in result["offers"]] == [206523, 206087, 2377]
    assert result["offers"][2]["price_history"] == [
        {"date": "2025-02-25", "kind": "offer", "price": 1620000.0},
        {"date": "2025-02-25", "kind": "archived", "price": 1620000.0},
        {"date": "2026-10-03", "kind": "restored", "price": 1620175.0},
        {"date": "2026-10-03", "kind": "offer", "price": 1620175.0},
        {"date": "2026-10-24", "kind": "offer", "price": 1620768.0},
    ]


def test_get_investment_with_history_off_the_contract_says_what_to_call_instead(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """The answer before 2.0 (the sample) has no price events: the history fails, and the
    message adds what to call instead of ending every attempt (D12, D21)."""
    investment_routes(service)

    result = call(server, "get_investment", investment_slug="smolna", include_history=True)

    assert result.is_error is True
    assert "Nie ponawiaj tego wywołania" in text(result)
    assert "bez include_history" in text(result) and "get_offer" in text(result)
    assert "/api/" not in text(result) and "sale" not in text(result)  # the detail: the log


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
    service.get(INVESTMENT).respond(404, **unknown_entity())

    result = call(server, "get_investment", investment_slug="smolna")

    assert result.is_error is True
    assert "search_offers" in text(result)
