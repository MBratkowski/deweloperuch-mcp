"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.get_developer_tool``."""

import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from deweloperuch_mcp import bootstrap
from support.providers.mcp import call, data, text, with_client
from support.providers.routes.developer_profiles import developer_routes
from support.providers.service import PAGES

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


DEVELOPER_BUDGET = 12_000
"""Characters of ``get_developer`` with the default limit for the whole country."""


def test_get_developer_in_a_city(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    developer_routes(service)

    result = data(call(server, "get_developer", developer_slug="atal", city="warszawa"))

    assert result["developer"] == {"developer_slug": "atal", "name": "ATAL S.A."}
    assert result["developer_url"] == f"{PAGES}/warszawa/deweloperzy/atal"
    assert result["city_slug"] == "warszawa"
    assert result["summary"] == {
        "active_offers": 69,
        "cities": 1,
        "avg_price": 1001962.0,
        "avg_area_m2": 62.7,
        "avg_price_per_m2": 16111.0,
    }
    assert (result["investments_total"], result["investments_returned"]) == (4, 4)
    assert (result["investments_omitted"], result["truncated"]) == (0, False)
    assert [i["investment_slug"] for i in result["investments"]] == [
        "warszawska-58a",
        "nowy-targowek-vi",
        "osiedle-poematu-ii",
        "zakatek-harmonia-ii",
    ]
    first = result["investments"][0]
    assert first == {
        "investment_slug": "warszawska-58a",
        "name": "Warszawska 58A",
        "city": "Warszawa",
        "city_slug": "warszawa",
        "status": "active",
        "active_offers": 36,
        "total_offers": 73,
        "avg_price": first["avg_price"],
        "avg_area_m2": first["avg_area_m2"],
        "avg_price_per_m2": first["avg_price_per_m2"],
        "investment_url": f"{PAGES}/warszawa/deweloperzy/atal/warszawska-58a",
    }
    assert len(result["cities"]) == 14
    assert result["cities"][0] == {
        "city": "Poznań",
        "city_slug": "poznan",
        "investments": 4,
        "active_offers": 736,
        "avg_price": 709389.0,
        "avg_price_per_m2": 11823.0,
    }
    assert "hint" not in result


def test_get_developer_of_the_whole_country_is_cut_and_fits_its_budget(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    developer_routes(service)

    async def both(client: Client) -> list[CallToolResult]:
        return [
            await client.call_tool("get_developer", {"developer_slug": "atal"}),
            await client.call_tool("get_developer", {"developer_slug": "atal", "limit": 100}),
        ]

    default, everything = with_client(server, both)

    result = data(default)
    assert (result["city_slug"], result["investments_total"]) == ("polska", 42)
    assert (result["investments_returned"], result["investments_omitted"]) == (20, 22)
    assert result["truncated"] is True
    assert result["hint"] == (
        "Pokazano 20 z 42 inwestycji (najwięcej aktywnych ofert); pozostałe pokaże większy "
        "limit (najwyżej 100)."
    )
    active = [i["active_offers"] for i in result["investments"]]
    assert active == sorted(active, reverse=True) and active[0] == 338
    assert len(text(default)) < DEVELOPER_BUDGET
    assert data(everything)["investments_returned"] == 42
    assert len(text(everything)) < 42 * 400 + 3_000
    assert len(service.calls) == 1  # the second call came from the cache


def test_an_unknown_developer_says_where_its_slug_comes_from(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    developer_routes(service)

    result = call(
        server, "get_developer", developer_slug="nieistniejacy-deweloper", city="warszawa"
    )

    assert result.is_error is True
    assert text(result) == (
        "Nie znaleziono dewelopera 'nieistniejacy-deweloper' w 'warszawa'. Slug dewelopera "
        "podaje search_developers (po nazwie) albo pole developer_slug w search_offers, "
        "get_investment i get_offer; city to city_slug z search_locations albo polska (cała "
        "Polska)."
    )
