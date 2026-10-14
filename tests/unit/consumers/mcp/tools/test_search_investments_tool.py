"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.search_investments_tool``."""

import json
import logging
import re
from typing import Any, get_args

import httpx
import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.consumers.mcp.support import calls
from deweloperuch_mcp.consumers.mcp.tools import search_investments_tool as tool
from deweloperuch_mcp.consumers.shared.choices import InvestmentSortChoice
from support.builders.investment_search import (
    INJECTED,
    KOMFORT,
    city_with_investments,
    long_city_investments,
)
from support.e2e import live
from support.providers.mcp import call, data, keys, text, with_client
from support.providers.routes.investment_search import CITY_INVESTMENTS, investment_search_routes
from support.providers.routes.investments import investment_routes
from support.providers.service import PAGES

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


TOOL = "search_investments"


# D3: backend names never reach the model (as tests/unit/consumers/mcp/ checks them).
BACKEND_NAMES = re.compile(r"sale|invest(?!ment)|amount|_rsc|\brsc\b|/api/|initialData", re.I)


LEAKS = re.compile(r"/api|/ceny-|invest(?!ment)|sale|Ignore previous|<html", re.I)


SIZE_BUDGET = 8_000
"""Characters of a result that fit the model's context comfortably (as for the others)."""


def listed(server: MCPServer[bootstrap.Session]) -> dict[str, Any]:
    async def read(client: Client) -> dict[str, Any]:
        tools = await client.list_tools()
        found = [tool for tool in tools.tools if tool.name == TOOL]
        assert len(found) == 1
        dumped: dict[str, Any] = found[0].model_dump(mode="json", by_alias=True, exclude_none=True)
        return dumped

    return with_client(server, read)


ERRORS: dict[str, httpx.Response] = {
    "500 with a body": httpx.Response(500, text=INJECTED),
    "404 with a body": httpx.Response(404, text=INJECTED),
    "redirect": httpx.Response(301, headers={"Location": "/api/elsewhere"}),
    "html": httpx.Response(
        200, text=f"<html>{INJECTED}</html>", headers={"Content-Type": "text/html"}
    ),
    "another shape": httpx.Response(200, json={INJECTED: True}),
}


def test_the_tool_is_read_only_and_described_in_polish(
    server: MCPServer[bootstrap.Session],
) -> None:
    listing = listed(server)

    assert listing["title"] == "Szukaj inwestycji"
    assert listing["annotations"] == {"readOnlyHint": True, "openWorldHint": True}
    description = listing["description"]
    assert len(description) <= 1_200
    assert description.startswith(
        "Wyszukuje inwestycje (projekty deweloperskie, rynek pierwotny). Dwa tryby: city "
        "(pełne dane) albo samo name"
    )
    assert "tylko aktywne oferty, wg serwisu" in description
    assert "pozycje bez średniej są na końcu" in description
    assert "na mapie miasta (z aktywnymi ofertami" in description
    assert "get_investment" in description
    assert "Nie filtruje po cenie ani metrażu" in description
    assert "city=polska nie działa" in description
    visible = json.dumps([listing["title"], description, listing["inputSchema"]])
    assert not BACKEND_NAMES.search(visible), BACKEND_NAMES.findall(visible)
    assert not BACKEND_NAMES.search(" ".join(keys(listing["outputSchema"])))


def test_the_input_schema(server: MCPServer[bootstrap.Session]) -> None:
    schema = listed(server)["inputSchema"]
    fields = schema["properties"]

    assert "required" not in schema  # city or name: checked by the application
    assert list(fields) == ["city", "name", "developer_slug", "sort", "limit"]
    for name in ("city", "name", "developer_slug", "sort"):
        assert fields[name]["default"] is None
    assert fields["sort"]["anyOf"][0] == {
        "enum": list(get_args(InvestmentSortChoice)),
        "type": "string",
    }
    limit = fields["limit"]
    assert (limit["default"], limit["minimum"], limit["maximum"]) == (10, 1, 30)
    for name, field in fields.items():
        assert field["description"], name
        assert field["title"] != name.replace("_", " ").title(), name


def test_the_output_schema_keeps_total_and_describes_what_names_do_not_say(
    server: MCPServer[bootstrap.Session],
) -> None:
    schema = listed(server)["outputSchema"]
    item = schema["$defs"]["InvestmentSearchItem"]["properties"]

    assert "total" in schema["required"]
    assert {"type": "null"} in schema["properties"]["total"]["anyOf"]
    for name in ("status", "offers_active", "offers_total", "avg_price", "avg_price_per_m2"):
        assert item[name]["description"], name
        assert "enum" not in json.dumps(item[name])


def test_a_city_lists_compact_investments_with_their_links(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    investment_search_routes(service)

    result = data(call(server, TOOL, city="sopot"))

    assert list(result) == ["total", "returned", "truncated", "items"]  # no null hint
    assert (result["total"], result["returned"], result["truncated"]) == (2, 2, False)
    assert result["items"][0] == {
        "investment_slug": "nowe-kolibki-etap-4",
        "name": "Nowe Kolibki etap 4",
        "city_slug": "sopot",
        "status": "active",
        "offers_active": 3,
        "offers_total": 27,
        "avg_price": 1615878.0,
        "avg_area_m2": 65.55,
        "avg_price_per_m2": 24756.49,
        "developer_slug": KOMFORT,
        "developer_name": "Invest Komfort Spółka Akcyjna Sp.K.",
        "investment_url": f"{PAGES}/sopot/deweloperzy/{KOMFORT}/nowe-kolibki-etap-4",
        "developer_url": f"{PAGES}/sopot/deweloperzy/{KOMFORT}",
    }
    assert result["items"][1]["street"] == "Świemirowo"


def test_a_name_lists_what_the_service_matched(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    _, names = investment_search_routes(service)

    result = data(call(server, TOOL, name="nowy targ"))

    assert names.calls.last.request.url.params["limit"] == "10"
    assert result == {
        "total": 2,
        "returned": 2,
        "truncated": False,
        "items": [
            {
                "investment_slug": "nowy-targowek-vi",
                "name": "Nowy Targówek VI",
                "offers_active": 27,
            },
            {
                "investment_slug": "apartamenty-nowy-targ",
                "name": "Apartamenty Nowy Targ",
                "offers_active": 0,
            },
        ],
    }


def test_an_investment_found_goes_to_get_investment(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """The chain the description promises: investment_slug of an item -> get_investment."""
    investment_search_routes(service)
    investment_routes(service)

    async def chain(client: Client) -> tuple[CallToolResult, CallToolResult]:
        found = await client.call_tool(TOOL, {"city": "sopot", "sort": "name"})
        assert found.structured_content is not None
        slug = found.structured_content["items"][1]["investment_slug"]
        return found, await client.call_tool("get_investment", {"investment_slug": slug})

    found, investment = with_client(server, chain)

    assert data(found)["items"][1]["investment_slug"] == "smolna"
    assert data(investment)["investment_url"] == data(found)["items"][1]["investment_url"]


@pytest.mark.parametrize(
    ("arguments", "returned"),
    [
        ({"city": " sopot "}, 2),
        ({"city": "sopot", "limit": "1"}, 1),
        ({"city": "sopot", "limit": " 1 "}, 1),
        ({"city": "sopot", "limit": None}, 2),
        ({"city": "sopot", "name": "", "developer_slug": " ", "sort": ""}, 2),
        ({"city": "sopot", "name": None, "developer_slug": None, "sort": None}, 2),
        ({"city": "sopot", "sort": " name "}, 2),
        ({"city": "", "name": "nowy targ"}, 2),
    ],
)
def test_arguments_as_models_send_them(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    arguments: dict[str, Any],
    returned: int,
) -> None:
    investment_search_routes(service)

    assert data(call(server, TOOL, **arguments))["returned"] == returned


@pytest.mark.parametrize(
    ("arguments", "field"),
    [
        ({"city": "sopot", "limit": 0}, "limit"),
        ({"city": "sopot", "limit": 31}, "limit"),
        ({"city": "sopot", "limit": True}, "limit"),
        ({"city": "sopot", "limit": "5.0"}, "limit"),
        ({"city": "sopot", "sort": "cheap"}, "sort"),
        ({"city": 7}, "city"),
    ],
)
def test_arguments_off_the_schema_are_refused_without_a_request(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    arguments: dict[str, Any],
    field: str,
) -> None:
    result = call(server, TOOL, **arguments)

    assert result.is_error is True
    assert field in text(result) and "pydantic.dev" not in text(result)
    assert service.calls.call_count == 0


@pytest.mark.parametrize(
    ("arguments", "start"),
    [
        ({}, "Podaj city (slug miasta z search_locations"),
        ({"city": "polska"}, "city=polska nie działa przy wyszukiwaniu inwestycji"),
        ({"city": "Sopot"}, "city: oczekiwano slug jednego miasta"),
        ({"name": "k"}, "name: podaj od 2 do 100 znaków nazwy inwestycji"),
        ({"name": "Kolibki", "developer_slug": "atal"}, "developer_slug działa tylko razem z city"),
        ({"name": "Kolibki", "sort": "name"}, "sort działa tylko razem z city"),
    ],
)
def test_invalid_input_says_what_to_fix_without_a_request(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    arguments: dict[str, Any],
    start: str,
) -> None:
    result = call(server, TOOL, **arguments)

    assert result.is_error is True
    assert text(result).startswith(start), text(result)
    assert service.calls.call_count == 0


@pytest.mark.parametrize("case", ERRORS)
def test_errors_carry_no_backend_details(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    caplog: pytest.LogCaptureFixture,
    case: str,
) -> None:
    """D12: no paths, names or text of the service's answer reach the model; the
    details go to the server's log only."""
    caplog.set_level(logging.INFO, logger=calls.LOGGER_NAME)
    service.get(path=CITY_INVESTMENTS).mock(return_value=ERRORS[case])

    result = call(server, TOOL, city="sopot")

    assert result.is_error is True
    assert not LEAKS.search(text(result)), text(result)
    assert text(result).startswith(("Wyszukiwanie inwestycji w 'sopot'", "Serwis nie zna"))
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "Szczegóły: " in logged and "/api/map/investments" in logged


def test_results_have_no_backend_names(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    investment_search_routes(service)

    async def both(client: Client) -> list[CallToolResult]:
        return [
            await client.call_tool(TOOL, {"city": "sopot"}),
            await client.call_tool(TOOL, {"name": "nowy targ"}),
        ]

    for result in with_client(server, both):
        assert [key for key in keys(data(result)) if BACKEND_NAMES.search(key)] == []


@pytest.mark.parametrize(
    ("investments", "per_item"),
    [
        (city_with_investments(60), 560),  # Sopot's rows: no district, short streets
        (long_city_investments(60), 760),  # the longest real values of the samples
    ],
)
def test_result_sizes(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    investments: list[dict[str, Any]],
    per_item: int,
) -> None:
    """The default fits the budget, and so does the maximum on the longest items; the
    per-item size in the description of limit holds ("ok. 550–750 znaków", "30 daje
    najwyżej ok. 23 tys."), so results do not grow unnoticed."""
    investment_search_routes(service, city=investments)
    largest = tool.MAX_INVESTMENTS_LIMIT

    async def sizes(client: Client) -> dict[int, int]:
        return {
            limit: len(text(await client.call_tool(TOOL, {"city": "sopot", "limit": limit})))
            for limit in (10, largest)
        }

    measured = with_client(server, sizes)

    assert measured[10] <= SIZE_BUDGET
    assert measured[largest] <= largest * per_item <= 23_000  # within 25k of 50 offers


def test_results_pass_the_leak_check_of_the_live_suite(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """The live suite's filter (tests/support/e2e/live.py) lets these results through: links only
    in *_url fields, as links.py builds them; no false alarm on "Invest Komfort"."""
    investment_search_routes(service)
    asked: list[dict[str, Any]] = [
        {"city": "sopot"},
        {"name": "nowy targ"},
        {"city": "polska"},
        {"city": "sopot", "limit": 31},
    ]

    async def every_call(client: Client) -> list[CallToolResult]:
        return [await client.call_tool(TOOL, arguments) for arguments in asked]

    results = with_client(server, every_call)

    for arguments, result in zip(asked, results, strict=True):
        live.assert_no_leaks(live.Call(TOOL, arguments, result, 0))
    assert [result.is_error for result in results] == [False, False, True, True]
