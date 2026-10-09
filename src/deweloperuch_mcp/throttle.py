"""Cross-process request limiter for deweloperuch.pl (stdlib only).

Every process on this machine that talks to the service (``recon/`` scripts and
the package's HTTP client) goes through one lock file, so together they keep
the D2 policy:

- one request at a time: an exclusive ``flock`` is held for the whole request;
- a request starts no earlier than ``min_interval`` (default 1 s) after the
  previous one ended, or later if a request asked for a pause with
  ``Slot.defer`` (e.g. ``Retry-After`` on 429/503);
- a pause longer than ``max_wait`` (default 60 s) raises ``WaitTooLongError``
  instead of silently blocking the caller.

The shared state lives in the lock file itself, read and written only under the
lock: ``{"in_flight_since": t}`` while a request runs, then
``{"last_end": t, "next_start": t + gap}``. The OS drops a ``flock`` when its
process dies, so a crash never leaves the lock stuck; the in-flight marker makes
the next process wait ``min_interval`` even if the dead one never reached
``finally`` (default SIGTERM, SIGKILL).

Usage::

    limiter = RequestLimiter()
    with limiter.slot() as slot:
        response = send()
        if response.status_code == 429:
            slot.defer(retry_after_seconds)

Backoff for 5xx is the HTTP client's policy; the limiter only offers ``defer``.
This module must import only the standard library: ``recon/`` scripts load it
without installing the package (``recon/config.py``). POSIX only (``fcntl``).
"""

import json
import math
import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows has no fcntl
    _HAS_FLOCK = False
else:
    _HAS_FLOCK = True

DEFAULT_MIN_INTERVAL = 1.0
"""Minimum pause between requests in seconds (robots.txt ``Crawl-delay: 1``, D2)."""

DEFAULT_MAX_WAIT = 60.0
"""Longest pause ``slot()`` sleeps through before raising ``WaitTooLongError``."""

MAX_DEFER = 3600.0
"""Upper bound for ``Slot.defer``; more is almost surely a ``Retry-After`` parsing bug."""

LOCK_FILENAME = "throttle.lock"
_APP_DIR = "deweloperuch-mcp"

# Marks a thread that is inside a slot: a nested slot would block on its own lock forever.
_thread_state = threading.local()


class WaitTooLongError(RuntimeError):
    """The next request is allowed only after more than ``max_wait`` seconds.

    ``max_wait`` is the effective limit, never below the limiter's ``min_interval``.
    """

    def __init__(self, remaining: float, max_wait: float) -> None:
        self.remaining = remaining
        self.max_wait = max_wait
        seconds = math.ceil(remaining)  # never "0 s", never below the real wait
        super().__init__(
            f"Następne zapytanie do deweloperuch.pl wolno wysłać dopiero za {seconds} s, "
            f"a limit oczekiwania (max_wait) to {max_wait:g} s. Serwis poprosił o przerwę "
            "(Retry-After) albo inny proces właśnie z niego korzystał. Spróbuj ponownie później."
        )


def default_lock_dir() -> Path:
    """``${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp``.

    A relative ``XDG_CACHE_HOME`` is ignored, as the XDG Base Directory spec requires.
    """
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    base = Path(xdg) if xdg and os.path.isabs(xdg) else Path.home() / ".cache"
    return base / _APP_DIR


class Slot:
    """Handle of the request that runs inside ``RequestLimiter.slot()``."""

    def __init__(self) -> None:
        self._deferred = 0.0

    def defer(self, seconds: float) -> None:
        """Pause at least ``seconds`` after this request ends (e.g. from ``Retry-After``).

        Repeated calls keep the longest pause. A pause never shortens ``min_interval``.
        More than ``MAX_DEFER`` (also ``math.inf``) records ``MAX_DEFER`` first and then
        raises ``ValueError``: failing must never shorten the pause the service asked for.
        NaN or a negative value raises without recording anything.
        """
        if math.isnan(seconds) or seconds < 0:
            raise ValueError(f"defer() wymaga liczby sekund >= 0, podano {seconds!r}")
        if seconds > MAX_DEFER:
            self._deferred = max(self._deferred, MAX_DEFER)
            raise ValueError(
                f"defer({seconds!r}) przekracza limit {MAX_DEFER:g} s, więc zapisano pauzę "
                f"{MAX_DEFER:g} s. To może być legalna długa przerwa serwisu (np. 503 w czasie "
                "prac technicznych) albo błąd parsowania Retry-After (to liczba sekund albo "
                "data HTTP, nie znacznik czasu)."
            )
        self._deferred = max(self._deferred, float(seconds))


class RequestLimiter:
    """Shared limit for requests to deweloperuch.pl across threads and processes.

    ``lock_dir`` defaults to ``default_lock_dir()``; tests pass a temporary directory.
    ``min_interval`` may only be raised above 1 s (D2). ``testing_only_allow_fast_interval``
    exists solely so that tests can run fast and must never be set in production code.
    ``clock`` must be a wall clock shared by all processes (``time.time``); ``clock`` and
    ``sleep`` are injectable for unit tests.
    """

    def __init__(
        self,
        lock_dir: str | os.PathLike[str] | None = None,
        *,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        testing_only_allow_fast_interval: bool = False,
    ) -> None:
        if not math.isfinite(min_interval) or min_interval < 0:
            raise ValueError(
                f"min_interval musi być skończoną liczbą sekund >= 0, podano {min_interval!r}"
            )
        if min_interval < DEFAULT_MIN_INTERVAL and not testing_only_allow_fast_interval:
            raise ValueError(
                f"min_interval={min_interval} s jest krótszy niż {DEFAULT_MIN_INTERVAL} s. "
                "Limit zapytań wolno zmieniać tylko w stronę wolniej (D2)."
            )
        self._lock_dir = Path(lock_dir) if lock_dir is not None else default_lock_dir()
        self._min_interval = float(min_interval)
        self._clock = clock
        self._sleep = sleep

    @property
    def lock_path(self) -> Path:
        return self._lock_dir / LOCK_FILENAME

    @property
    def min_interval(self) -> float:
        return self._min_interval

    @contextmanager
    def slot(self, *, max_wait: float = DEFAULT_MAX_WAIT) -> Iterator[Slot]:
        """Wait for our turn, then hold the lock for the duration of one request.

        Raises ``WaitTooLongError`` (lock released, state untouched) when the required
        pause exceeds ``max_wait``; ``math.inf`` disables the check. A ``max_wait`` below
        ``min_interval`` counts as ``min_interval``, so the regular spacing of a slower
        limiter is never an error. ``max_wait`` covers
        the pause imposed by the limiter, not the time spent waiting for the lock while
        another process's request runs: that is bounded by the request's own timeout.

        On exit, also after an exception, the next start is set to
        ``end + max(min_interval, deferred)`` and the lock is released.

        Enter and exit the slot in the same thread (the nested-slot guard is per thread).
        An async wrapper must run the whole ``with`` block in one worker thread rather
        than ``__enter__`` and ``__exit__`` in separate ``asyncio.to_thread`` calls.
        """
        if not _HAS_FLOCK:
            raise RuntimeError(
                "Limiter zapytań wymaga fcntl.flock (Linux, macOS). Windows nie jest wspierany."
            )
        if math.isnan(max_wait) or max_wait < 0:
            raise ValueError(f"max_wait musi być liczbą sekund >= 0, podano {max_wait!r}")
        if getattr(_thread_state, "in_slot", False):
            raise RuntimeError(
                "Zagnieżdżony slot limitera w tym samym wątku zablokowałby się na zawsze. "
                "Zakończ bieżące zapytanie przed rozpoczęciem następnego."
            )
        self._lock_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        _thread_state.in_slot = True
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                wait = self._seconds_to_wait(_read_all(fd), self._clock())
                limit = max(max_wait, self._min_interval)
                if wait > limit:
                    raise WaitTooLongError(wait, limit)
                if wait > 0:
                    self._sleep(wait)
                # Written before the request: a process killed mid-request skips `finally`,
                # and this marker then makes the next one wait min_interval.
                _write_json(fd, {"in_flight_since": self._clock()})
                slot = Slot()
                try:
                    yield slot
                finally:
                    end = self._clock()
                    gap = max(self._min_interval, slot._deferred)
                    _write_json(fd, {"last_end": end, "next_start": end + gap})
            finally:
                # Explicit unlock: a forked child holding a copy of fd must not keep the lock.
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            _thread_state.in_slot = False
            os.close(fd)

    def _seconds_to_wait(self, raw: bytes, now: float) -> float:
        if not raw.strip():
            return 0.0  # fresh lock file: no request has been made yet
        try:
            state = json.loads(raw)
            last_end = float(state["last_end"])
            next_start = float(state["next_start"])
        except (ValueError, KeyError, TypeError):
            # Unreadable state, or the in-flight marker of a process that died mid-request
            # (it has no "last_end"): assume a request has just ended.
            return self._min_interval
        if not (math.isfinite(last_end) and math.isfinite(next_start)) or next_start < last_end:
            return self._min_interval
        # Each process also enforces its own interval, in case the writer was configured faster.
        next_start = max(next_start, last_end + self._min_interval)
        # If the wall clock went backwards (now < last_end), wait the planned gap, not more.
        return max(0.0, min(next_start - now, next_start - last_end))


def _read_all(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while chunk := os.read(fd, 4096):
        chunks.append(chunk)
    return b"".join(chunks)


def _write_json(fd: int, state: dict[str, float]) -> None:
    data = json.dumps(state).encode()
    os.lseek(fd, 0, os.SEEK_SET)
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]
    # Truncate after writing: a crash in between leaves unreadable state, which is read
    # conservatively, never an empty file that would allow an immediate request.
    os.ftruncate(fd, len(data))
