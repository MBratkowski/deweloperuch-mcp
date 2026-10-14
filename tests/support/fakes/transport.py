"""Seams of the transport: a cache that records lookups, a limiter that lets a test order
two threads, bodies that fail or arrive in chunks.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx

from deweloperuch_mcp.api.http.transport import (
    Reply,
    ResponseCache,
)
from deweloperuch_mcp.throttle import (
    DEFAULT_MAX_WAIT,
    RequestLimiter,
    Slot,
)
from support.fakes.clocks import MonotonicClock


class SpyCache(ResponseCache):
    """Records every lookup."""

    def __init__(self) -> None:
        super().__init__()
        self.lookups: list[str] = []

    def get(self, key: str) -> Reply | None:
        self.lookups.append(key)
        return super().get(key)


class RaceLimiter(RequestLimiter):
    """Lets a test hold the order of two threads around the shared slot.

    ``waiting`` is set when the thread named "second" is about to wait for the slot. The
    thread named "first", after releasing the slot, waits for ``second_done``: the second
    thread then gets the slot while the first one has not yet returned from ``_fetch``.
    """

    def __init__(self, lock_dir: Path) -> None:
        super().__init__(
            lock_dir,
            min_interval=0,
            testing_only_allow_fast_interval=True,
            sleep=lambda seconds: None,  # a 429 pause must not slow the test down
        )
        self.waiting = threading.Event()
        self.second_done = threading.Event()

    @contextmanager
    def slot(self, *, max_wait: float = DEFAULT_MAX_WAIT) -> Iterator[Slot]:
        name = threading.current_thread().name
        if name == "second":
            self.waiting.set()
        try:
            with super().slot(max_wait=max_wait) as handle:
                yield handle
        finally:
            if name == "first":
                self.second_done.wait(5)


class InterruptedBody(httpx.SyncByteStream):
    """The first chunk of a body, then Ctrl+C while the rest is being read."""

    def __iter__(self) -> Iterator[bytes]:
        yield b"<html>"
        raise KeyboardInterrupt


class ChunkedBody(httpx.SyncByteStream):
    """A streamed body that records how much of it was read; may fail midway."""

    def __init__(
        self,
        chunks: list[bytes],
        *,
        fail_after: int | None = None,
        clock: MonotonicClock | None = None,
        step: float = 0.0,
    ) -> None:
        self.chunks = chunks
        self.fail_after = fail_after
        self.clock = clock
        self.step = step
        self.read = 0

    def __iter__(self) -> Iterator[bytes]:
        for index, chunk in enumerate(self.chunks):
            if self.fail_after is not None and index >= self.fail_after:
                raise httpx.ReadError("connection reset")
            if self.clock is not None:
                self.clock.advance(self.step)
            self.read += 1
            yield chunk
