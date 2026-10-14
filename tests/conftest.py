"""Shared test setup: the suite-wide autouse fixtures and the fixture providers.

The helpers live in ``tests/support`` (no tests there); their asserts are rewritten like
the tests' own, so a failing helper shows the values it compared.
"""

import os
from collections.abc import Iterator

import pytest

from deweloperuch_mcp.api.http import transport

# Typer forces a colour terminal when GITHUB_ACTIONS, FORCE_COLOR or PY_COLORS is set; the
# CLI goldens and assertions compare plain text, as a pipe gets it. Set before the
# providers below import Typer (also inherited by the subprocesses the tests start).
os.environ["_TYPER_FORCE_DISABLE_TERMINAL"] = "1"

pytest.register_assert_rewrite("support")

pytest_plugins = [
    "support.providers.network",
    "support.providers.clients",
    "support.providers.mcp",
    "support.providers.cli",
]


@pytest.fixture(autouse=True)
def fresh_stop_latch() -> Iterator[None]:
    """Every test starts as a new process would: no STOP latched by an earlier test.

    The latch is per process on purpose (CONTRIBUTING.md: after a STOP the process sends
    nothing more), and pytest runs every test in one process.
    """
    transport.HttpClient.testing_only_reset_stop()
    yield
    transport.HttpClient.testing_only_reset_stop()


@pytest.fixture(autouse=True)
def private_cache_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``XDG_CACHE_HOME`` of every test is a fresh temporary directory.

    The default lock directory, its STOP record and the scanner's chunk cache live
    there (``throttle.default_lock_dir``), so no test reads or writes the user's real
    cache, and no test sees a STOP recorded by another. Subprocesses inherit it.
    """
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path_factory.mktemp("cache-home")))
