"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.get_offer_tool``."""

import pytest
import respx
from mcp.server.mcpserver import MCPServer

from deweloperuch_mcp import bootstrap
from support.builders.offers import offer_without_history
from support.providers.mcp import call, data, has_null, text
from support.providers.routes.investments import investment_routes
from support.providers.service import PAGES

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_offer_and_investment_carry_the_links_of_their_pages(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """D12: the investment's page and the developer's profile, from the result's slugs."""
    investment_routes(service)
    smolna = PAGES + "/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna"
    developer = PAGES + "/sopot/deweloperzy/invest-komfort-spolka-akcyjna"

    offer = data(call(server, "get_offer", offer_id=2377, investment_slug="smolna"))
    investment = data(call(server, "get_investment", investment_slug="smolna"))

    assert (offer["investment_url"], offer["developer_url"]) == (smolna, developer)
    assert (investment["investment_url"], investment["developer_url"]) == (smolna, developer)
    assert all(not any(key.endswith("_url") for key in item) for item in investment["offers"])


def test_get_offer(server: MCPServer[bootstrap.Session], service: respx.MockRouter) -> None:
    investment_routes(service)

    result = data(call(server, "get_offer", offer_id=2377, investment_slug="smolna"))

    assert (result["offer_id"], result["investment_slug"]) == (2377, "smolna")
    assert result["price_history"][0] == {"date": "2025-02-25", "kind": "offer", "price": 1620000.0}
    assert result["developer"] == {
        "developer_slug": "invest-komfort-spolka-akcyjna",
        "name": "Invest Komfort Spółka Akcyjna Sp.K.",
    }
    assert not has_null(result)


def test_an_offer_without_history_is_explained_in_domain_terms(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    offer_without_history(service)

    result = call(server, "get_offer", offer_id=2377, investment_slug="smolna")

    assert text(result).startswith("Serwis nie ma historii ceny oferty 2377 z inwestycji 'smolna'.")


def test_get_offer_has_its_price_flags(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    investment_routes(service)

    result = data(call(server, "get_offer", offer_id=2377, investment_slug="smolna"))

    # Withdrawn since 2025-02-25, back at 1 620 175 on 2026-10-03: the same every day since.
    assert result["price_flags"] == {
        "lowest_price_30d": 1620175.0,
        "lowest_price_90d": 1620175.0,
        "price_changes": 1,
        "largest_rise_pct": 0.01,
        "suspicious_reduction": False,
    }
