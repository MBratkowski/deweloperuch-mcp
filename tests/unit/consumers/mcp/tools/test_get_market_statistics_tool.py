"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.get_market_statistics_tool``."""

import pytest
import respx
from mcp.server.mcpserver import MCPServer

from deweloperuch_mcp import bootstrap
from support.checks.leaks import SIZE_BUDGET
from support.providers.mcp import call, data, keys, text
from support.providers.routes.offer_snapshot import offer_snapshot_routes
from support.providers.service import PAGES

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_get_market_statistics_of_a_city(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    routes = offer_snapshot_routes(service)

    result = data(call(server, "get_market_statistics", city="sopot", top_developers=1))

    assert result == {
        "city_slug": "sopot",
        "offers": 6,
        "investments": 2,
        "developers": 1,
        # statistics.quantiles(..., method="inclusive") of the 6 offers, rounded
        "price": {
            "min": 1399205,
            "p25": 1588164,
            "median": 1616463,
            "p75": 1646230,
            "max": 1679796,
        },
        "price_per_m2": result["price_per_m2"],
        "area_m2": {"min": 56.5, "p25": 61.21, "median": 67.0, "p75": 68.7, "max": 69.5},
        "top_developers": [
            {
                "developer_slug": "invest-komfort-spolka-akcyjna",
                "offers": 6,
                "investments": 2,
                "median_price_per_m2": result["top_developers"][0]["median_price_per_m2"],
                "developer_url": f"{PAGES}/sopot/deweloperzy/invest-komfort-spolka-akcyjna",
            }
        ],
        "developers_returned": 1,
        "developers_omitted": 0,
        "truncated": False,
        "list_url": f"{PAGES}/sopot/mieszkania?page=1&perPage=10",
    }
    assert all(isinstance(v, int) for v in result["price_per_m2"].values())
    assert routes["sopot"].call_count == 1


def test_the_market_never_shows_single_offers_and_fits_its_budget(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """D5, D15: 7325 offers of Kraków, only aggregates and 30 developers at most."""
    offer_snapshot_routes(service)

    result = call(
        server, "get_market_statistics", city="krakow", price_max=900_000, top_developers=30
    )

    found = data(result)
    assert found["offers"] < 7325 and found["developers_returned"] == 30
    assert found["list_url"].endswith("/krakow/mieszkania?filterPrice=0-900000&page=1&perPage=10")
    assert not {"offer_id", "items", "offers_list", "sales"} & keys(found)
    assert len(text(result)) < SIZE_BUDGET


@pytest.mark.parametrize(
    ("city", "message", "sent"),
    [
        (
            "polska",
            "city: statystyki rynku są tylko dla jednego miasta; podaj city_slug miasta z "
            "search_locations (np. warszawa), a nie polska; podano 'polska'.",
            0,
        ),
        (
            "nieznane",
            "Serwis nie zna miasta 'nieznane'. Podaj city_slug z search_locations (statystyki "
            "rynku są tylko dla jednego miasta).",
            1,
        ),
    ],
)
def test_the_market_of_the_whole_country_or_an_unknown_city(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    city: str,
    message: str,
    sent: int,
) -> None:
    offer_snapshot_routes(service)

    result = call(server, "get_market_statistics", city=city)

    assert result.is_error is True and text(result) == message
    assert service.calls.call_count == sent
