"""Helpers of the live suite: the MCP server over stdio, the CLI, probe, the request budget.

Nothing here runs at import time. Every live call goes through ``McpLive.call``,
``run_cli`` or ``run_probe``, which count the requests it sent (``Budget``) and never
retry. The whole session ends at once:

- on a STOP (``stop_exit``, exit code 3): stop and report (CONTRIBUTING.md);
- when the service is unavailable (``unavailable_exit``, exit code 4): a 5xx or a
  network error, so no further request goes out;
- past the budget, or when the request counter turns out not to work (exit code 1).

Counting requests:

- the MCP server logs every request httpx sends (``HTTP Request: ...``) on stderr; the
  suite reads that pipe in a thread (``ServerLog``) and notes when each line came. The
  log level comes from the MCP SDK, so ``McpLive.call_network`` ends the session when a
  call that must reach the network logged nothing;
- the CLI logs nothing, so it runs as its entry point (``deweloperuch_mcp.cli:main``,
  what the ``deweloperuch`` script calls) with httpx's log written to a file (``CLI``);
- probe sends at most one request per run, none for exit codes 2 and 5.
"""

import itertools
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

import anyio
import pytest
import pytest_socket
from anyio.from_thread import BlockingPortal, start_blocking_portal
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.types import CallToolResult, InitializeResult, TextContent, Tool

from deweloperuch_mcp.identity import BASE_URL
from support.paths import REPO
from support.providers.service import PAGES

LIVE_ENV = "DEWELOPERUCH_LIVE"
SKIP_REASON = (
    "e2e na żywym serwisie: seria żywych zapytań, tylko za zgodą użytkownika (D9). "
    f"Uruchomienie: {LIVE_ENV}=1 uv run pytest -m live tests/e2e"
)

PROBE = REPO / "recon" / "probe.py"
BIN = Path(sys.executable).parent  # the scripts of the environment running the tests

# Assembled in code: the repo does not carry ready-to-paste service addresses.
HOST = "deweloperuch" + ".pl"

MAX_REQUESTS = 115
"""Live requests one full run may send: the plan is 84, the worst case 110
(tests/e2e/README.md), about two minutes at 1 per second."""

REQUEST_LINE = "HTTP Request:"
"""How httpx logs each request it sends (INFO)."""

CALL_TIMEOUT = 120.0
"""Seconds for one tool call or command: the shared limiter may make it wait."""

EXIT_STOP = 3
"""Exit code of a STOP for the CLI and probe, and of a session ended by a STOP."""

EXIT_UNAVAILABLE = 4
"""Exit code of a service error (5xx, network) for the CLI and probe, and of a session
ended by one."""

UNAVAILABLE = "spróbuj później"
"""What every message of a service error tells the model (``errors.ServiceError``)."""

SERVICE_CHANGED = "Serwis mógł się zmienić"
"""Start of ``errors.SERVICE_CHANGED``: data that does not match the contract."""

# D3, D12: what a model must never read. Anywhere in a result or a tool listing: paths,
# props, Next.js internals, the service's addresses, HTML, Python and its libraries.
TEXT_LEAKS = re.compile(
    r"/api/|initialData|_rsc|invest_|sale_id|/ceny-|/statystyki|tocItems|sortedLocations|"
    r"currentSlug|NEXT_HTTP|digest|Next-Action|buildId|"
    r'Traceback|File "|httpx|pydantic\.dev|<html|<!doctype|<script|'
    + rf"{re.escape(HOST)}/|://(?:www\.)?{re.escape(HOST)}",
    re.IGNORECASE,
)
# Backend names (D3) in field names only: values are the service's data, and real
# developers are called e.g. "Invest Komfort" (tests/safeguards/test_e2e_gate.py).
KEY_LEAKS = re.compile(r"sale|invest(?!ment)|rcn|amount|rsc", re.IGNORECASE)
# The one exception (D12, 2026-10-11): a full address of a public page of the service,
# as the whole value of a field named ``*_url``; never with ``_rsc`` or ``/api/``, never
# in another field nor in an error message. Only the routes links.py builds [P]: the list
# of offers (with a query), a developer's profile, an investment, the government
# statistics of a location (with the id of a section as its fragment), the transaction
# statistics of flats in a city (2026-10-13, the user's decision: a link for people
# only; the client never requests that page, a D5 dump), the ranking of cities (one
# fixed page) and a building of the price register. A segment has no ``/``, ``?``,
# ``#``, is not ``.`` or ``..`` and holds no ``%2e`` (a browser would read it as a dot);
# a section id is lowercase letters, digits, hyphens.
_SEGMENT = r"(?!\.\.?(?:[/?#]|$))(?:(?!%2[eE])[^/?#\s])+"
_SECTION = r"[a-z0-9][a-z0-9-]*"
PAGE_LINK = re.compile(
    rf"{re.escape(BASE_URL)}/(?:ceny-ofertowe/{_SEGMENT}/"
    rf"(?:mieszkania(?:\?[^\s#]*)?|deweloperzy/{_SEGMENT}(?:/{_SEGMENT})?)"
    rf"|statystyki/statystyki-rzadowe/{_SEGMENT}(?:#{_SECTION})?"
    rf"|statystyki/ceny-transakcyjne/mieszkania/{_SEGMENT}"
    r"|ceny-transakcyjne/polska/miasta"
    rf"|ceny-transakcyjne/{_SEGMENT}/adresy/{_SEGMENT})"
)
LINK = "<link>"

STOP_ADVICE = (
    "Zestaw e2e przerwany bez dalszych zapytań. Niczego nie ponawiaj i zgłoś to "
    "użytkownikowi: STOP zdejmuje tylko on, po sprawdzeniu przyczyny."
)
COUNTER_BROKEN = (
    "Licznik zapytań nie działa: zmienił się format logów SDK? Wywołanie, które musiało "
    "trafić do sieci, nie zalogowało żadnej linii 'HTTP Request:', a bez licznika budżet "
    "nic nie widzi. Zestaw przerwany."
)


# --- the gate --------------------------------------------------------------------------------


def live_enabled(config: pytest.Config) -> bool:
    """``DEWELOPERUCH_LIVE=1`` and a ``-m`` expression that names ``live``: both, so
    neither a stray variable nor a stray ``-m`` starts a series of live requests."""
    words = re.findall(r"[\w-]+", str(config.option.markexpr or ""))
    return os.environ.get(LIVE_ENV) == "1" and "live" in words


def skip_live(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Unless ``live_enabled``: every item marked ``live`` is skipped with ``SKIP_REASON``
    (before any fixture runs, so nothing is started)."""
    if live_enabled(config):
        return
    skip = pytest.mark.skip(reason=SKIP_REASON)
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(skip)


# --- ending the session ----------------------------------------------------------------------


def stop_exit(reason: str) -> NoReturn:
    """End the whole session at once: no further test, no further request."""
    pytest.exit(f"STOP: {reason}\n{STOP_ADVICE}", returncode=EXIT_STOP)


def stop_on(text: str, where: str) -> None:
    """A result that says ``STOP:`` ends the session (CONTRIBUTING.md: stop and report)."""
    if "STOP:" in text:
        stop_exit(f"{where}: {text.strip()}")


def unavailable_exit(reason: str) -> NoReturn:
    """The service is not answering (5xx, network): end the session, send nothing more."""
    pytest.exit(
        f"Serwis niedostępny: {reason}\nZestaw e2e przerwany bez dalszych zapytań; "
        "nic nie ponawiaj, spróbuj później.",
        returncode=EXIT_UNAVAILABLE,
    )


# --- the budget ----------------------------------------------------------------------------


@dataclass
class Budget:
    """Live requests of the session, by what sent them."""

    limit: int = MAX_REQUESTS
    spent: list[tuple[str, int]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(count for _, count in self.spent)

    def spend(self, count: int, what: str) -> None:
        """Record ``count`` requests; past ``limit`` the session ends at once."""
        if count:
            self.spent.append((what, count))
        if self.total > self.limit:
            pytest.exit(
                f"Budżet żywych zapytań przekroczony: {self.total} > {self.limit} "
                f"(ostatnio: {what}). Zestaw przerwany.",
                returncode=1,
            )

    def summary(self) -> str:
        lines = [f"Żywe zapytania: {self.total} (limit {self.limit})."]
        lines += [f"  {count} × {what}" for what, count in self.spent]
        return "\n".join(lines)


# --- leaks -----------------------------------------------------------------------------------


def keys(value: Any) -> set[str]:
    """Every key of every dict in ``value``."""
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in keys(item)}
    return set()


def is_link_field(key: object) -> bool:
    return isinstance(key, str) and key.endswith("_url")


def page_link(value: str) -> bool:
    """A full address of a public page of the service (D12), as links.py builds them."""
    return bool(PAGE_LINK.fullmatch(value)) and "_rsc" not in value and "/api/" not in value


def leaks(text: str, value: Any = None) -> list[str]:
    """Backend details in ``text`` and ``value`` (anywhere) and in the keys of ``value``.

    Page links are let through only as the values of link fields (``is_link_field``);
    a link field with anything else is a leak itself. ``text`` may repeat ``value`` as
    JSON (a tool result): the links of ``value``'s link fields are taken out of it too.
    """
    links: list[str] = []
    bad: list[str] = []

    def without_links(node: Any) -> Any:
        if isinstance(node, list):
            return [without_links(item) for item in node]
        if not isinstance(node, dict):
            return node
        kept: dict[Any, Any] = {}
        for key, item in node.items():
            if is_link_field(key) and isinstance(item, str):
                (links if page_link(item) else bad).append(item)
                kept[key] = LINK
            else:
                kept[key] = without_links(item)
        return kept

    clean = without_links(value)
    for link in sorted(set(links), key=len, reverse=True):
        text = text.replace(link, LINK)
    shown = text + json.dumps(clean, ensure_ascii=False)
    found = [f"zły link: {link!r}" for link in bad] + TEXT_LEAKS.findall(shown)
    return found + sorted(k for k in keys(value) if KEY_LEAKS.search(k))


# --- the MCP server ------------------------------------------------------------------------


class ServerLog:
    """stderr of the server: a pipe read by a thread.

    Every line is copied to ``path``; ``requests`` holds when each ``REQUEST_LINE`` came
    (``time.monotonic``). The server writes its log before it answers the call, so a
    short quiet spell after the answer means every line of the call is here.
    """

    def __init__(self, path: Path) -> None:
        read_fd, write_fd = os.pipe()
        self.writer = os.fdopen(write_fd, "w", encoding="utf-8")
        self._reader = os.fdopen(read_fd, "r", encoding="utf-8", errors="replace")
        self.path = path
        self._copy = path.open("w", encoding="utf-8")
        self._changed = threading.Condition()
        self._lines = 0
        self.requests: list[float] = []
        self._thread = threading.Thread(target=self._read, name="server-stderr", daemon=True)
        self._thread.start()

    def _read(self) -> None:
        for line in self._reader:
            now = time.monotonic()
            self._copy.write(line)
            self._copy.flush()
            with self._changed:
                self._lines += 1
                if REQUEST_LINE in line:
                    self.requests.append(now)
                self._changed.notify_all()

    def text(self) -> str:
        """Every line copied so far (the details of errors are only here, D12)."""
        self.settle()
        self._copy.flush()
        return self.path.read_text(encoding="utf-8")

    def settle(self, quiet: float = 0.25) -> int:
        """Requests logged so far, once no line has come for ``quiet`` seconds."""
        with self._changed:
            while True:
                seen = self._lines
                self._changed.wait(quiet)
                if self._lines == seen:
                    return len(self.requests)

    def close(self) -> None:
        self.writer.close()
        self._thread.join(timeout=10)
        self._reader.close()
        self._copy.close()


@dataclass(frozen=True)
class Call:
    """One tool call: its result and the live requests it sent."""

    tool: str
    arguments: dict[str, Any]
    result: CallToolResult
    sent: int

    @property
    def error(self) -> bool:
        return self.result.is_error is True

    @property
    def text(self) -> str:
        return "".join(
            block.text for block in self.result.content if isinstance(block, TextContent)
        )

    @property
    def data(self) -> dict[str, Any]:
        """The structured result of a successful call; its text is the same JSON."""
        assert not self.error, f"{self.tool} {self.arguments}: {self.text}"
        structured: dict[str, Any] | None = self.result.structured_content
        assert structured is not None, f"{self.tool}: brak structuredContent"
        assert json.loads(self.text) == structured, f"{self.tool}: tekst ≠ structuredContent"
        return structured


def assert_no_leaks(call: Call) -> None:
    """D3, D12 for one result, errors of the SDK's argument validation included."""
    found = leaks(call.text, call.result.structured_content)
    assert not found, f"{call.tool} {call.arguments}: szczegóły backendu w wyniku: {found}"


def assert_listing_clean(tools: list[dict[str, Any]]) -> None:
    """D3 for ``tools/list``: descriptions and schemas, field names included."""
    found = leaks("", tools)
    assert not found, f"tools/list: szczegóły backendu: {found}"


class McpLive:
    """The real ``deweloperuch-mcp`` over stdio, through the SDK's ``ClientSession``.

    The session lives in an event loop of its own thread (``BlockingPortal``), so one
    server serves a whole test module: repeated requests come from its cache.
    """

    def __init__(
        self,
        portal: BlockingPortal,
        session: ClientSession,
        log: ServerLog,
        budget: Budget,
        init: InitializeResult,
    ) -> None:
        self.portal = portal
        self.session = session
        self.log = log
        self.budget = budget
        self.init = init
        self._counted = log.settle()

    def _sent(self, what: str) -> int:
        now = self.log.settle()
        sent, self._counted = now - self._counted, now
        self.budget.spend(sent, what)
        return sent

    def list_tools(self) -> tuple[list[Tool], int]:
        listed = self.portal.call(self.session.list_tools)
        return listed.tools, self._sent("MCP tools/list")

    def call(self, tool: str, **arguments: Any) -> Call:
        """One tool call. Ends the session on a STOP or a service error; fails on
        backend details in the result."""
        result = self.portal.call(self._call, tool, arguments)
        call = Call(tool, arguments, result, self._sent(f"MCP {tool} {arguments}"))
        self._check(call)
        return call

    def call_network(self, tool: str, **arguments: Any) -> Call:
        """A call nothing cached can answer: it must log at least one request."""
        call = self.call(tool, **arguments)
        if call.sent == 0:
            pytest.exit(f"{COUNTER_BROKEN} ({tool} {arguments})", returncode=1)
        return call

    def parallel(self, *calls: tuple[str, dict[str, Any]]) -> tuple[list[Call], list[float]]:
        """``calls`` sent at once; also when each of their requests was logged."""
        first = len(self.log.requests)

        async def together() -> list[CallToolResult]:
            results: dict[int, CallToolResult] = {}

            async def one(index: int, tool: str, arguments: dict[str, Any]) -> None:
                results[index] = await self._call(tool, arguments)

            async with anyio.create_task_group() as group:
                for index, (tool, arguments) in enumerate(calls):
                    group.start_soon(one, index, tool, arguments)
            return [results[index] for index in range(len(calls))]

        results = self.portal.call(together)
        sent = self._sent(f"MCP równolegle {[tool for tool, _ in calls]}")
        done = [
            Call(tool, arguments, result, sent)
            for (tool, arguments), result in zip(calls, results, strict=True)
        ]
        for call in done:
            self._check(call)
        return done, self.log.requests[first:]

    def _check(self, call: Call) -> None:
        where = f"MCP {call.tool} {call.arguments}"
        stop_on(call.text, where)
        if call.error and UNAVAILABLE in call.text:
            unavailable_exit(f"{where}: {call.text}")
        assert_no_leaks(call)

    async def _call(self, tool: str, arguments: dict[str, Any]) -> CallToolResult:
        return await self.session.call_tool(tool, arguments, read_timeout_seconds=CALL_TIMEOUT)


def unix_sockets_only() -> None:
    """Allow Unix sockets (an event loop's socket pair), keep the network blocked.

    ``disable_socket`` subclasses whatever ``socket.socket`` is, so on top of an earlier
    guard that refuses Unix sockets it would refuse them too: lift the guard first.
    """
    pytest_socket.enable_socket()
    pytest_socket.disable_socket(allow_unix_socket=True)


def server_script() -> Path:
    script = BIN / "deweloperuch-mcp"
    if not script.exists():
        pytest.fail(f"Brak skryptu {script}: zainstaluj pakiet (uv sync).")
    return script


@contextmanager
def mcp_server(log_path: Path, budget: Budget) -> Iterator[McpLive]:
    """The installed ``deweloperuch-mcp`` with the user's environment (shared limiter and
    STOP record), initialized and with its tools listed (the SDK then checks every
    result against the tool's output schema)."""
    params = StdioServerParameters(command=str(server_script()), env=dict(os.environ))
    unix_sockets_only()
    log = ServerLog(log_path)
    try:
        with (
            start_blocking_portal() as portal,
            portal.wrap_async_context_manager(stdio_client(params, errlog=log.writer)) as streams,
            portal.wrap_async_context_manager(
                ClientSession(*streams, read_timeout_seconds=CALL_TIMEOUT)
            ) as session,
        ):
            init = portal.call(session.initialize)
            portal.call(session.list_tools)
            yield McpLive(portal, session, log, budget, init)
    finally:
        log.close()


# --- the CLI and probe ---------------------------------------------------------------------

# The CLI's entry point with httpx's request log in a file (the first argument).
CLI = """\
import logging, sys
log = logging.getLogger("httpx")
log.setLevel(logging.INFO)
log.propagate = False
log.addHandler(logging.FileHandler(sys.argv.pop(1), encoding="utf-8"))
sys.argv[0] = "deweloperuch"
from deweloperuch_mcp.cli import main
main()
"""

_runs = itertools.count(1)


@dataclass(frozen=True)
class Run:
    """One run of the CLI or probe."""

    args: tuple[str, ...]
    code: int
    stdout: str
    stderr: str
    sent: int

    def readable(self) -> None:
        """Text for people: no traceback, no control characters but line breaks."""
        for name, text in (("stdout", self.stdout), ("stderr", self.stderr)):
            assert "Traceback" not in text, f"{self.args}: traceback na {name}:\n{text}"
            odd = {char for char in text if not (char.isprintable() or char == "\n")}
            assert not odd, f"{self.args}: znaki sterujące na {name}: {odd!r}"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=CALL_TIMEOUT,
        env=dict(os.environ),
        check=False,
    )


def _end_on(run: Run, what: str) -> None:
    """STOP (exit code 3) or a service error (exit code 4) ends the session."""
    if run.code == EXIT_STOP or "Błąd: STOP:" in run.stderr:
        stop_exit(f"{what} (kod {run.code}): {(run.stderr or run.stdout).strip()}")
    if run.code == EXIT_UNAVAILABLE:
        unavailable_exit(f"{what} (kod {run.code}): {run.stderr.strip()}")


def run_cli(budget: Budget, logs: Path, *args: str) -> Run:
    """``deweloperuch ARGS`` (its entry point), counting the requests it sent."""
    log = logs / f"cli-{next(_runs)}.log"
    done = _run([sys.executable, "-c", CLI, str(log), *args])
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    sent = sum(REQUEST_LINE in line for line in lines)
    run = Run(args, done.returncode, done.stdout, done.stderr, sent)
    budget.spend(run.sent, "CLI " + " ".join(args))
    _end_on(run, "CLI " + " ".join(args))
    return run


def run_script(name: str, *args: str) -> Run:
    """An installed script of the package (only for commands that send nothing)."""
    script = BIN / name
    if not script.exists():
        pytest.fail(f"Brak skryptu {script}: zainstaluj pakiet (uv sync).")
    done = _run([str(script), *args])
    run = Run(args, done.returncode, done.stdout, done.stderr, 0)
    _end_on(run, f"{name} {' '.join(args)}")
    return run


# probe's exit codes that mean "nothing was sent": usage (2), limiter (5).
PROBE_NOT_SENT = (2, 5)


def run_probe(budget: Budget, *args: str) -> Run:
    """``python3 recon/probe.py ARGS``: at most one request per run, counted unless the
    exit code says nothing was sent."""
    done = _run([sys.executable, str(PROBE), *args])
    sent = 0 if done.returncode in PROBE_NOT_SENT else 1
    run = Run(args, done.returncode, done.stdout, done.stderr, sent)
    budget.spend(run.sent, "probe " + " ".join(args))
    _end_on(run, "probe " + " ".join(args))
    return run


def page_url(*slugs: str) -> str:
    """A page address as links.py builds it: each slug one encoded segment."""
    return "/".join([PAGES, *(urllib.parse.quote(slug, safe="") for slug in slugs)])
