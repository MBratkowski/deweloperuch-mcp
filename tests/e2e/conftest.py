"""The live suite: off unless asked for twice, sharing the user's limiter and STOP record.

- Every test here is marked ``live`` and skipped unless ``DEWELOPERUCH_LIVE=1`` is set
  AND ``-m live`` selects it: a series of live requests needs the user's consent (D9),
  so neither a stray variable nor a stray ``-m`` starts it. Skipped tests open nothing.
- The test process never opens a network socket (pytest-socket stays on): the network
  is used only by the subprocesses (the MCP server, the CLI, probe). The SDK's client
  talks to the server over pipes; its event loop needs a Unix socket pair, nothing more.
- No private ``XDG_CACHE_HOME`` (``private_cache_home`` is overridden): the
  subprocesses get the user's environment, so the limiter (1 request per second) and
  the STOP record are the ones Claude Desktop and every other process use.
- ``budget`` counts live requests; past ``live.MAX_REQUESTS`` the session ends at once,
  and the total is asserted and printed at the end. A STOP (exit code 3) or a service
  error (exit code 4) ends the session too (``live``).
"""

from collections.abc import Iterator

import pytest

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.usecases.get_stop_status import GetStopStatusRequest
from support.e2e.live import (
    MAX_REQUESTS,
    SKIP_REASON,
    Budget,
    live_enabled,
    skip_live,
    stop_exit,
    unix_sockets_only,
)

BUDGET = pytest.StashKey[Budget]()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip_live(config, items)


@pytest.fixture(autouse=True)
def unix_sockets() -> None:
    """The SDK client's event loop needs a Unix socket pair; IPv4, IPv6 and DNS stay
    blocked in this process (pytest-socket restores its own setting after each test)."""
    unix_sockets_only()


@pytest.fixture(autouse=True)
def private_cache_home() -> None:
    """Overrides tests/conftest.py: the live suite keeps the user's ``XDG_CACHE_HOME``
    (or its absence), so its limiter and STOP record are shared with every process."""


@pytest.fixture(scope="session")
def budget(request: pytest.FixtureRequest) -> Iterator[Budget]:
    """Live requests of the session. Refuses to start while a STOP holds (offline check
    of the shared record); at the end asserts the total against ``MAX_REQUESTS``."""
    if not live_enabled(request.config):  # belt and braces: the items are skipped anyway
        pytest.skip(SKIP_REASON)
    # Reads the local record; sends nothing.
    found = bootstrap.StopUseCases().get_stop_status.execute(GetStopStatusRequest.parse())
    if found.state.active:
        stop_exit("blokada STOP jest aktywna przed startem zestawu")
    spent = Budget(MAX_REQUESTS)
    request.config.stash[BUDGET] = spent
    yield spent
    assert spent.total <= MAX_REQUESTS, spent.summary()


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    spent = terminalreporter.config.stash.get(BUDGET, None)
    if spent is not None:
        terminalreporter.write_sep("-", "żywe zapytania (e2e)")
        terminalreporter.write_line(spent.summary())
