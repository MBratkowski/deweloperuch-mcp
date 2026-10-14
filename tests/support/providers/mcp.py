"""The MCP server in-process, behind the SDK's in-memory client: its session factory,
calls and listing, and the shapes of its results.

Fixtures (registered in tests/conftest.py): ``server`` over the test's fast limiter.
"""

import json
import re
from collections.abc import Awaitable, Callable, Iterator
from typing import Any, TypeVar

import anyio
import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.consumers.mcp import server as mcp_server
from deweloperuch_mcp.throttle import RequestLimiter

T = TypeVar("T")


class Sessions:
    """Session factory of the server: a fast limiter; remembers what it opened."""

    def __init__(self, limiter: RequestLimiter) -> None:
        self.limiter = limiter
        self.opened: list[bootstrap.Session] = []

    def __call__(self) -> bootstrap.Session:
        session = bootstrap.Session(limiter=self.limiter)
        self.opened.append(session)
        return session


def with_client(server: MCPServer[bootstrap.Session], use: Callable[[Client], Awaitable[T]]) -> T:
    async def main() -> T:
        async with Client(server) as client:
            return await use(client)

    return anyio.run(main)


def call(server: MCPServer[bootstrap.Session], tool: str, **arguments: Any) -> CallToolResult:
    return with_client(server, lambda client: client.call_tool(tool, arguments))


def text(result: CallToolResult) -> str:
    assert len(result.content) == 1
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def data(result: CallToolResult) -> dict[str, Any]:
    """The structured result; the text content is the same data as compact JSON."""
    assert result.is_error is False, text(result)
    structured: dict[str, Any] | None = result.structured_content
    assert structured is not None
    assert json.loads(text(result)) == structured
    return structured


def keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in keys(item)}
    return set()


def has_null(value: Any) -> bool:
    if isinstance(value, dict):
        return any(has_null(item) for item in value.values())
    if isinstance(value, list):
        return any(has_null(item) for item in value)
    return value is None


def properties(schema: Any) -> Iterator[tuple[str, dict[str, Any]]]:
    """Every (name, schema) of an object property, anywhere in ``schema``."""
    if isinstance(schema, dict):
        yield from schema.get("properties", {}).items()
        for value in schema.values():
            yield from properties(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from properties(value)


def listing(server: MCPServer[bootstrap.Session]) -> dict[str, Any]:
    """What a client sees before any call: the server and its tools."""

    async def read(client: Client) -> dict[str, Any]:
        tools = await client.list_tools()
        info = client.server_info
        return {
            "server": {
                "name": None if info is None else info.name,
                "instructions": client.instructions,
            },
            "tools": [
                tool.model_dump(mode="json", by_alias=True, exclude_none=True)
                for tool in tools.tools
            ],
        }

    return with_client(server, read)


def tools(server: MCPServer[bootstrap.Session]) -> dict[str, dict[str, Any]]:
    return {tool["name"]: tool for tool in listing(server)["tools"]}


def prompts(server: MCPServer[bootstrap.Session]) -> list[dict[str, Any]]:
    """The prompts as ``prompts/list`` gives them to a client."""

    async def read(client: Client) -> list[dict[str, Any]]:
        listed = await client.list_prompts()
        return [
            prompt.model_dump(mode="json", by_alias=True, exclude_none=True)
            for prompt in listed.prompts
        ]

    return with_client(server, read)


def rendered(
    server: MCPServer[bootstrap.Session], prompt: str, arguments: dict[str, str]
) -> dict[str, Any]:
    """``prompts/get`` of ``prompt``: its description and messages (role and content),
    without the result's ``_meta`` (it carries the server's version)."""

    async def get(client: Client) -> dict[str, Any]:
        result = await client.get_prompt(prompt, arguments)
        return result.model_dump(
            mode="json", by_alias=True, exclude_none=True, include={"description", "messages"}
        )

    return with_client(server, get)


@pytest.fixture
def sessions(limiter: RequestLimiter) -> Sessions:
    """The server's session factory on the test's fast limiter; remembers what it opened."""
    return Sessions(limiter)


@pytest.fixture
def server(sessions: Sessions) -> MCPServer[bootstrap.Session]:
    """The MCP server; each call opens its session through ``sessions``."""
    return mcp_server.build_server(sessions)


def calls(
    server: MCPServer[bootstrap.Session], tool: str, *arguments: dict[str, Any]
) -> list[CallToolResult]:
    """``tool`` called with each of ``arguments`` in turn, by one client."""

    async def main() -> list[CallToolResult]:
        async with Client(server) as client:
            return [await client.call_tool(tool, given) for given in arguments]

    return anyio.run(main)


TOOL_NAME = re.compile(r"\b(?:search|get|rank|estimate)_[a-z_]+\b")
"""How the tools are named: a verb (search, get, rank, estimate) and what it is about."""


def tools_named(text: str) -> list[str]:
    """The tool names in ``text``, in the order it first names them."""
    return list(dict.fromkeys(TOOL_NAME.findall(text)))


TOOLS = (
    "search_locations",
    "search_offers",
    "get_offer",
    "search_investments",
    "get_investment",
    "search_developers",
    "get_developer",
    "get_market_statistics",
    "get_transaction_statistics",
    "rank_locations",
    "get_building",
    "estimate_property_value",
    "get_government_statistics",
)


PROMPTS = ("znajdz_mieszkanie", "ocen_oferte", "przeswietl_dewelopera", "porownaj_miasta")
