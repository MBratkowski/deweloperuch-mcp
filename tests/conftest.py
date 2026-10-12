"""Shared test setup."""

from collections.abc import Iterator

import pytest

from deweloperuch_mcp.infrastructure.deweloperuch import transport


@pytest.fixture(autouse=True)
def fresh_stop_latch() -> Iterator[None]:
    """Every test starts as a new process would: no STOP latched by an earlier test.

    The latch is per process on purpose (CLAUDE.md: after a STOP the process sends
    nothing more), and pytest runs every test in one process.
    """
    transport.testing_only_reset_stop()
    yield
    transport.testing_only_reset_stop()


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
