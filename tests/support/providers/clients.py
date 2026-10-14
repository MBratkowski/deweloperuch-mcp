"""Limiters, HTTP clients and sessions of the tests: fast (no pause between requests) and
on the test's own lock directory.

Fixtures (registered in tests/conftest.py): ``limiter``, ``http``, ``session``.
"""

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.throttle import (
    RequestLimiter,
)
from support.fakes.clocks import FakeTime


def shared_limiter(clock: Callable[[], float] = time.time) -> RequestLimiter:
    """A limiter on the lock directory ``stop status|clear`` use: ``default_lock_dir()``,
    under the test's own ``XDG_CACHE_HOME`` (tests/conftest.py)."""
    return RequestLimiter(min_interval=0, testing_only_allow_fast_interval=True, clock=clock)


@pytest.fixture
def limiter(tmp_path: Path) -> RequestLimiter:
    """A fast limiter (no pause between requests) on the test's own lock directory."""
    return RequestLimiter(tmp_path, min_interval=0, testing_only_allow_fast_interval=True)


@pytest.fixture
def http(tmp_path: Path) -> Iterator[HttpClient]:
    """The real HTTP client over its own fast limiter on the test's lock directory."""
    limiter = RequestLimiter(tmp_path, min_interval=0, testing_only_allow_fast_interval=True)
    with HttpClient(limiter=limiter) as client:
        yield client


@pytest.fixture
def session(limiter: RequestLimiter) -> Iterator[bootstrap.Session]:
    """The session the consumers open (real adapters and use cases) over ``limiter``."""
    with bootstrap.Session(limiter=limiter) as opened:
        yield opened


def make_limiter(lock_dir: Path, fake: FakeTime, **kwargs: Any) -> RequestLimiter:
    return RequestLimiter(lock_dir, clock=fake.clock, sleep=fake.sleep, **kwargs)


def record_stop(
    limiter: RequestLimiter,
    status: int | str = 403,
    reason: str = "odmowa dostępu",
    *,
    defer: float | None = None,
) -> None:
    with limiter.slot() as slot:
        if defer is not None:
            slot.defer(defer)
        slot.stop(status, reason, source="probe")
