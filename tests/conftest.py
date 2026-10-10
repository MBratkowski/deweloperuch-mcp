"""Shared test setup."""

from collections.abc import Iterator

import pytest

from deweloperuch_mcp.client import transport


@pytest.fixture(autouse=True)
def fresh_stop_latch() -> Iterator[None]:
    """Every test starts as a new process would: no STOP latched by an earlier test.

    The latch is per process on purpose (CLAUDE.md: after a STOP the process sends
    nothing more), and pytest runs every test in one process.
    """
    transport.testing_only_reset_stop()
    yield
    transport.testing_only_reset_stop()
