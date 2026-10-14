"""Starts an MCP server command the way an MCP client does and lists its tools (``make smoke``).

    python packaging/smoke.py -- uvx --from dist/<wheel> deweloperuch-mcp
    python packaging/smoke.py -- uv run --directory build/mcpb-unpacked src/server.py

Sends ``initialize`` and ``tools/list`` over stdin and checks that the server lists the
tools of ``packaging/mcpb/manifest.json``. It calls no tool, so the server sends no
request to deweloperuch.pl; uv may download the dependencies from PyPI on the first run.
"""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import IO, Any

MANIFEST = Path(__file__).resolve().parent / "mcpb" / "manifest.json"
# The first run of a command installs the dependencies.
TIMEOUT_SECONDS = 600
PROTOCOL_VERSION = "2025-06-18"


def main(argv: list[str]) -> int:
    command = argv[1:] if argv[:1] == ["--"] else argv
    if not command:
        print(__doc__, file=sys.stderr)
        return 2
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = [tool["name"] for tool in manifest["tools"]]
    # As a host starts it: outside the virtual environment this script may run in.
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True
    ) as server:
        assert server.stdin is not None and server.stdout is not None
        timer = threading.Timer(TIMEOUT_SECONDS, server.kill)
        timer.start()
        try:
            names, server_info = list_tools(server.stdin, server.stdout)
        finally:
            timer.cancel()
            server.stdin.close()
            server.wait(timeout=30)
    print(f"{server_info['name']} {server_info['version']}: {len(names)} tools")
    if sorted(names) != sorted(expected):
        print(f"expected the tools {expected}, got {names}", file=sys.stderr)
        return 1
    return 0


def list_tools(stdin: IO[str], stdout: IO[str]) -> tuple[list[str], dict[str, Any]]:
    """``initialize``, ``notifications/initialized``, ``tools/list``: names and serverInfo."""
    client = {"name": "deweloperuch-mcp-smoke", "version": "0"}
    initialized = request(
        stdin,
        stdout,
        1,
        "initialize",
        {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": client},
    )
    send(stdin, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    tools = request(stdin, stdout, 2, "tools/list", {})["tools"]
    return [tool["name"] for tool in tools], initialized["serverInfo"]


def request(
    stdin: IO[str], stdout: IO[str], ident: int, method: str, params: dict[str, Any]
) -> dict[str, Any]:
    send(stdin, {"jsonrpc": "2.0", "id": ident, "method": method, "params": params})
    for line in stdout:
        message = json.loads(line)
        if message.get("id") != ident:
            continue  # a notification (e.g. a log message)
        if "error" in message:
            sys.exit(f"{method}: {message['error']}")
        result: dict[str, Any] = message["result"]
        return result
    sys.exit(f"{method}: the server closed stdout without a reply (see its stderr above)")


def send(stdin: IO[str], message: dict[str, Any]) -> None:
    stdin.write(json.dumps(message) + "\n")
    stdin.flush()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
