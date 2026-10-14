"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.search_developers_tool``."""

import json
import re
from typing import Any

import anyio
import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer

from deweloperuch_mcp import bootstrap
from support.builders.developer_search import (
    ATAL_ROW,
    INJECTED,
    LEAKS,
    NOTHING_HINT,
    PROFILES,
    TRUNCATED_HINT,
    developers_found,
)
from support.e2e import live
from support.providers.mcp import call, calls, data, text
from support.providers.routes.developer_search import DEVELOPERS, developer_search_route

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


TOOL = "search_developers"


SIZE_BUDGET = 8_000
"""Characters of a result that fit the model's context comfortably (as for the others)."""


BACKEND_NAMES = re.compile(r"sale|invest(?!ment)|amount|_rsc|\brsc\b|/api/|initialData", re.I)


def listed(server: MCPServer[bootstrap.Session]) -> dict[str, Any]:
    async def main() -> dict[str, Any]:
        async with Client(server) as client:
            tools = (await client.list_tools()).tools
        shown = [tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in tools]
        return next(tool for tool in shown if tool["name"] == TOOL)

    return anyio.run(main)


def test_the_tool_is_read_only_and_described_for_the_model(
    server: MCPServer[bootstrap.Session],
) -> None:
    tool = listed(server)

    assert tool["annotations"] == dict(readOnlyHint=True, openWorldHint=True)
    assert tool["title"] == "Szukaj deweloperów"
    description = tool["description"]
    for said in (
        "rynek pierwotny",
        "developer_slug, którego wymaga get_developer",
        "city=polska",
        "offer_count",
        "developer_url",
        "truncated=true znaczy, że pasujących deweloperów jest więcej",
        "najwyżej 20",
        "total jest null",
    ):
        assert said in description
    assert len(description) <= 1_200
    visible = json.dumps([tool["title"], description, tool["inputSchema"]], ensure_ascii=False)
    assert not BACKEND_NAMES.search(visible), BACKEND_NAMES.findall(visible)
    assert not BACKEND_NAMES.search(" ".join(live.keys(tool["outputSchema"])))


def test_the_input_schema(server: MCPServer[bootstrap.Session]) -> None:
    schema = listed(server)["inputSchema"]
    fields = schema["properties"]

    assert schema["required"] == ["name"]
    assert fields["name"]["type"] == "string"
    assert fields["name"]["title"] == "Nazwa dewelopera"
    limit = fields["limit"]
    assert (limit["type"], limit["default"], limit["minimum"], limit["maximum"]) == (
        "integer",
        5,
        1,
        20,
    )
    assert limit["title"] == "Limit wyników"
    assert "domyślnie 5, najwyżej 20" in limit["description"]


def test_the_output_schema_describes_what_names_do_not_say(
    server: MCPServer[bootstrap.Session],
) -> None:
    schema = listed(server)["outputSchema"]
    item = schema["$defs"]["DeveloperItem"]["properties"]

    for name in ("developer_slug", "offer_count", "developer_url"):
        assert item[name]["description"], name
    assert "enum" not in json.dumps(item)
    for name in ("total", "truncated"):
        assert schema["properties"][name]["description"], name
    assert schema["required"] == ["total", "returned", "truncated", "items"]


def test_the_sample_as_a_result(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    route = developer_search_route(service)

    result = data(call(server, TOOL, name="atal"))

    assert result == {"total": 1, "returned": 1, "truncated": False, "items": [ATAL_ROW]}
    assert list(result)[:3] == ["total", "returned", "truncated"]
    assert [str(c.request.url) for c in route.calls] == [DEVELOPERS]
    assert live.leaks(json.dumps(result, ensure_ascii=False), result) == []


@pytest.mark.parametrize(
    ("limit", "sent"),
    [(20, "20"), (1, "1"), ("3", "3"), (" 7 ", "7"), (None, "5")],
)
def test_the_limit_reaches_the_service(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter, limit: object, sent: str
) -> None:
    route = developer_search_route(service)

    data(call(server, TOOL, name="atal", limit=limit))

    assert route.calls[0].request.url.params["limit"] == sent


def test_the_name_is_sent_trimmed_with_its_letters(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    route = developer_search_route(service)

    data(call(server, TOOL, name="  Dom Development "))

    assert route.calls[0].request.url.params["q"] == "Dom Development"


@pytest.mark.parametrize(
    "arguments",
    [
        {"name": "atal", "limit": 0},
        {"name": "atal", "limit": 21},
        {"name": "atal", "limit": True},
        {"name": "atal", "limit": "x"},
        {"name": "atal", "limit": 2.5},
        {"limit": 5},
        {"name": 42},
    ],
)
def test_arguments_off_the_schema_send_nothing(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter, arguments: dict[str, Any]
) -> None:
    developer_search_route(service)

    result = calls(server, TOOL, arguments)[0]

    assert result.is_error is True
    assert "pydantic.dev" not in text(result)
    assert service.calls.call_count == 0


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("a", "name: podaj od 2 do 100 znaków nazwy dewelopera, podano 'a'."),
        (" a ", "name: podaj od 2 do 100 znaków nazwy dewelopera, podano ' a '."),
        ("", "name: podaj od 2 do 100 znaków nazwy dewelopera, podano ''."),
    ],
)
def test_a_name_too_short_says_what_to_fix(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter, name: str, message: str
) -> None:
    developer_search_route(service)

    result = call(server, TOOL, name=name)

    assert (result.is_error, text(result)) == (True, message)
    assert service.calls.call_count == 0


def test_a_truncated_search_keeps_the_services_total_and_says_what_to_do(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    developer_search_route(service, developers_found(5, total=12, more=True))

    result = data(call(server, TOOL, name="atal"))

    assert (result["total"], result["returned"], result["truncated"]) == (12, 5, True)
    assert result["hint"] == TRUNCATED_HINT
    assert [item["developer_url"] for item in result["items"]] == [
        PROFILES + f"atal-{index}" for index in range(5)
    ]


def test_more_than_the_limit_from_the_service_is_cut_and_said_so(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    developer_search_route(service, developers_found(7, total=7, more=False))

    result = data(call(server, TOOL, name="atal", limit=3))

    assert (result["total"], result["returned"], result["truncated"]) == (7, 3, True)
    assert len(result["items"]) == 3


def test_more_without_a_total_that_fits_has_total_null(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    developer_search_route(service, developers_found(5, total=5, more=True))

    result = data(call(server, TOOL, name="atal"))

    assert {k: result[k] for k in ("total", "returned", "truncated")} == {
        "total": None,
        "returned": 5,
        "truncated": True,
    }
    assert result["hint"].startswith("Pokazano 5 pasujących deweloperów, a może ich być więcej.")


def test_nothing_found_says_what_to_try(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    developer_search_route(service, developers_found(0, total=0, more=False))

    result = data(call(server, TOOL, name="xyzzy"))

    assert result == {
        "total": 0,
        "returned": 0,
        "truncated": False,
        "hint": NOTHING_HINT,
        "items": [],
    }


def test_a_service_error_names_the_search_without_its_details(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    service.get(path="/api/developers").respond(500, text=INJECTED)

    result = call(server, TOOL, name="atal")

    assert result.is_error is True
    assert text(result).startswith("Wyszukiwanie deweloperów: ")
    assert not LEAKS.search(text(result))


def test_a_403_is_a_stop(server: MCPServer[bootstrap.Session], service: respx.MockRouter) -> None:
    service.get(path="/api/developers").respond(403)

    result = call(server, TOOL, name="atal")

    assert result.is_error is True
    assert text(result).startswith("STOP: ")


def test_twenty_developers_fit_the_size_budget(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """The limit's description promises about 150 characters a developer."""
    developer_search_route(service, developers_found(20, total=40, more=True))

    size = len(text(call(server, TOOL, name="atal", limit=20)))

    assert size <= 20 * 170 < SIZE_BUDGET
