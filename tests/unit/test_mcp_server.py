"""Tests of ``deweloperuch_mcp.mcp_server``."""

import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import IO, Any

import anyio
import pytest
import pytest_socket
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult
from mcp.types.version import LATEST_HANDSHAKE_VERSION

import deweloperuch_mcp.mcp_server
from deweloperuch_mcp.consumers.mcp import server as mcp_server
from support.builders.offers import UNKNOWN_CITY_MESSAGE
from support.paths import TESTS
from support.providers.mcp import TOOLS, data, text
from support.providers.rsc import UNKNOWN_CITY

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


# pytest-socket does not reach a subprocess: its child installs the same guard first.
NO_NETWORK = (
    f"import sys; sys.path[:0] = [{str(TESTS)!r}]; import pytest_socket; "
    "from support.checks.sockets import event_loop_sockets_only; event_loop_sockets_only()"
)


GUARD_CHECK = f"""{NO_NETWORK}
import socket
from pathlib import Path

for family in (socket.AF_INET, socket.AF_INET6):
    try:
        socket.socket(family, socket.SOCK_STREAM)
    except pytest_socket.SocketBlockedError:
        print("blocked", family.name)
try:
    socket.getaddrinfo("localhost", 9)
except pytest_socket.SocketBlockedError:
    print("blocked getaddrinfo")

# The package's own client, pointed at a local discard port: without the guard this
# would be a refused local connection, never a request to the service.
from deweloperuch_mcp.usecases.search_locations import SearchLocationsRequest
from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.api.http import transport
from deweloperuch_mcp.throttle import RequestLimiter

transport.BASE_URL = "http://127.0.0.1:9"
limiter = RequestLimiter(
    Path.cwd(), min_interval=0, testing_only_allow_fast_interval=True
)
with Session(limiter=limiter) as session:
    try:
        session.search_locations.execute(SearchLocationsRequest.parse(query="krak"))
    except pytest_socket.SocketBlockedError:
        print("blocked client")
"""


# The real entry point with the network mocked inside the child: the offers list answers
# with the real RSC responses (tests/fixtures/rsc/), everything else is refused by respx.
ON_REAL_PAYLOADS = f"""{NO_NETWORK}
import sys
sys.path[:0] = [{str(TESTS)!r}]
import respx
from support.providers.routes.government_statistics import stats_routes
from support.providers.routes.offers import offers_route, unknown_city_route
with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
    unknown_city_route(router)
    offers_route(router)
    stats_routes(router)
    from deweloperuch_mcp.mcp_server import main
    main()
"""


def test_the_script_module_is_a_shim_of_the_interface() -> None:
    assert deweloperuch_mcp.mcp_server.main is mcp_server.main
    assert deweloperuch_mcp.mcp_server.__all__ == ["main"]


def test_main_runs_the_server_over_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    transports: list[str] = []
    monkeypatch.setattr(
        MCPServer, "run", lambda self, transport="stdio": transports.append(transport)
    )

    mcp_server.main([])

    assert transports == ["stdio"]


def test_main_help_works_offline(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        mcp_server.main(["--help"])

    assert exit_info.value.code == 0
    assert "deweloperuch-mcp" in capsys.readouterr().out


def test_main_rejects_unknown_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        mcp_server.main(["--port", "8000"])

    assert exit_info.value.code == 2
    assert "--port" in capsys.readouterr().err


def test_the_guard_of_the_subprocess_blocks_the_network(tmp_path: Path) -> None:
    """Should a call of the smoke test below ever get past the services, the guard of the
    child stops it before any connection."""
    done = subprocess.run(
        [sys.executable, "-c", GUARD_CHECK],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "XDG_CACHE_HOME": str(tmp_path)},
        timeout=60,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == [
        "blocked AF_INET",
        "blocked AF_INET6",
        "blocked getaddrinfo",
        "blocked client",
    ]


def test_the_entry_point_speaks_only_json_rpc_on_stdout(tmp_path: Path) -> None:
    """``main()`` in a real process over stdio, behind the network guard: initialize,
    tools/list, a call the services reject before sending (price_min > price_max) and one
    the input schema rejects. Neither depends on tunable limits. EOF ends it with 0."""
    stderr = (tmp_path / "stderr.txt").open("w")
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"{NO_NETWORK}; from deweloperuch_mcp.mcp_server import main; main()",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr,
        text=True,
        env={**os.environ, "XDG_CACHE_HOME": str(tmp_path)},
    )
    watchdog = threading.Timer(60, process.kill)
    watchdog.start()
    lines: list[str] = []
    try:
        assert process.stdin is not None and process.stdout is not None
        stdin: IO[str] = process.stdin
        stdout: IO[str] = process.stdout

        def send(message: dict[str, Any]) -> None:
            stdin.write(json.dumps(message) + "\n")
            stdin.flush()

        def answer(request_id: int) -> dict[str, Any]:
            while line := stdout.readline():
                lines.append(line)
                message: dict[str, Any] = json.loads(line)
                if message.get("id") == request_id:
                    return message
            raise AssertionError(f"no answer to {request_id}; stderr: {stderr.name}")

        def call_tool(request_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {"name": "search_offers", "arguments": arguments},
                }
            )
            return answer(request_id)

        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": LATEST_HANDSHAKE_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            }
        )
        initialized = answer(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listed = answer(2)
        in_services = call_tool(3, {"city": "warszawa", "price_min": 7, "price_max": 5})
        in_schema = call_tool(4, {"city": "warszawa", "sort": "rooms_asc"})
        stdin.close()
        lines += stdout.readlines()
        returncode = process.wait(timeout=30)
    finally:
        watchdog.cancel()
        process.kill()
        stderr.close()

    assert returncode == 0
    assert all(json.loads(line)["jsonrpc"] == "2.0" for line in lines)
    assert initialized["result"]["serverInfo"]["name"] == "deweloperuch"
    assert [tool["name"] for tool in listed["result"]["tools"]] == list(TOOLS)
    assert in_services["result"]["isError"] is True
    assert in_services["result"]["content"][0]["text"] == (
        "price_min (7) jest większe niż price_max (5); zamień je miejscami."
    )
    assert in_schema["result"]["isError"] is True
    assert "sort" in in_schema["result"]["content"][0]["text"]
    assert "pydantic" not in in_schema["result"]["content"][0]["text"]


def test_the_entry_point_over_stdio_on_the_real_payloads(tmp_path: Path) -> None:
    """What failed on the live service on 2026-10-10, offline: ``main()`` in a real process,
    the SDK's stdio client, the real RSC responses for a known and an unknown city."""
    params = StdioServerParameters(
        command=sys.executable, args=["-c", ON_REAL_PAYLOADS], env=dict(os.environ)
    )

    async def session() -> tuple[list[str], CallToolResult, CallToolResult, CallToolResult]:
        with anyio.fail_after(60), (tmp_path / "stderr.txt").open("w") as errlog:
            async with (
                stdio_client(params, errlog=errlog) as (read, write),
                ClientSession(read, write) as client,
            ):
                await client.initialize()
                listed = await client.list_tools()
                found = await client.call_tool("search_offers", {"city": "warszawa"})
                unknown = await client.call_tool("search_offers", {"city": UNKNOWN_CITY})
                stats = await client.call_tool(
                    "get_government_statistics",
                    {"location": "polska", "dataset": "average_area", "periods": 3},
                )
        return [tool.name for tool in listed.tools], found, unknown, stats

    names, found, unknown, stats = anyio.run(session)

    assert names == list(TOOLS)
    result = data(found)
    assert (result["total"], result["returned"], result["per_page"]) == (13324, 10, 10)
    assert all({"offer_id", "investment_slug", "price"} <= set(item) for item in result["items"])
    assert unknown.is_error is True
    assert text(unknown) == UNKNOWN_CITY_MESSAGE
    area = data(stats)
    assert (area["periods"], area["series"][0]["values"]) == (
        ["2024", "2025", "2026"],
        [61.6, 62.3, 62.5],
    )


# The warning is the expected effect here; elsewhere it still flags a real attempt.
@pytest.mark.filterwarnings("ignore:A test tried to use socket")
def test_network_stays_blocked() -> None:
    """Only Unix sockets are allowed in this module: no IPv4, IPv6 or name lookups."""
    with pytest.raises(pytest_socket.SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(pytest_socket.SocketBlockedError):
        socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    with pytest.raises(pytest_socket.SocketBlockedError):
        socket.getaddrinfo("localhost", 443)
