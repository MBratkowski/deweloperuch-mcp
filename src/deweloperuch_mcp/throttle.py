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

STOP for every process (CONTRIBUTING.md: after 401, 403, 429, captcha or WAF stop and report).
Code that sees such an answer records it with ``Slot.stop`` before leaving the slot::

    with limiter.slot() as slot:
        response = send()
        if response.status_code == 429:
            slot.defer(retry_after_seconds)
            slot.stop(429, "limit zapytań", source="probe")

The record (``stop.json`` next to the lock file, ``STOP_FILENAME``) is written and removed
only under the lock, and replaced atomically. ``slot()`` reads it under the lock;
``stop_status()`` reads it without (the atomic replace makes that safe). While it is
active, ``slot()`` raises ``StoppedError`` before computing any wait: nothing is sent,
the timing state stays as it was. A 429 recorded after ``defer`` expires when that pause
ends; any other STOP (401, 403, a challenge) lasts until a person removes it
(``clear_stop``, CLI ``deweloperuch stop clear``). An unreadable record, or one with
anything but what this package writes (``STOP_SOURCES``, the policy's texts), counts as
a STOP without an end (fail-closed). The first record wins: a later STOP may only extend
its end or make it permanent, never shorten it.

This module must import only the standard library: ``recon/`` scripts load it
without installing the package (``recon/config.py``). File locks use ``fcntl`` on
POSIX and ``msvcrt`` on Windows.
"""

import contextlib
import dataclasses
import json
import math
import os
import stat
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeAlias

from deweloperuch_mcp.file_lock import lock_file
from deweloperuch_mcp.file_lock import unlock_file as unlock_file

# Stdlib only as well (recon loads both without the package's dependencies): the texts a
# STOP record may carry are the response policy's.
from deweloperuch_mcp.http_policy import CHALLENGE, CHALLENGE_REASON, STOP_STATUSES

DEFAULT_MIN_INTERVAL = 1.0
"""Minimum pause between requests in seconds (robots.txt ``Crawl-delay: 1``, D2)."""

DEFAULT_MAX_WAIT = 60.0
"""Longest pause ``slot()`` sleeps through before raising ``WaitTooLongError``."""

MAX_DEFER = 3600.0
"""Upper bound for ``Slot.defer``; more is almost surely a ``Retry-After`` parsing bug."""

LOCK_FILENAME = "throttle.lock"
STOP_FILENAME = "stop.json"
"""The STOP record, next to the lock file (format: ``StopRecord``)."""

STOP_FORMAT = 1
"""``format`` of the STOP record; any other value makes the record unreadable (a STOP)."""

STOP_SOURCES = frozenset({"pakiet", "probe", "scan_bundles"})
"""Programs that record a STOP; a record naming any other is unreadable (a STOP)."""

CLEAR_WAIT_LIMIT = 300.0
"""Longest wait of ``clear_stop`` for the lock before it gives up (``LockWaitTimeoutError``)."""

CLEAR_NOTICE_AFTER = 2.0
"""Wait of ``clear_stop`` for the lock after which it calls ``on_wait`` once."""

_APP_DIR = "deweloperuch-mcp"
_STOP_MAX_BYTES = 64 * 1024
_PROBLEM_MAX = 200
_TEMP_PREFIX, _TEMP_SUFFIX = ".stop-", ".tmp"
_POLL = 0.1

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


@dataclass(frozen=True)
class StopRecord:
    """A STOP that holds every process back, as ``stop.json`` stores it.

    ``since`` and ``until`` are wall-clock seconds (``time.time``); the file keeps them as
    ISO 8601 in UTC. ``status`` is the HTTP status (401, 403, 429) or ``"challenge"``
    (Cloudflare, whatever the status); ``reason`` is the policy's text for it
    (``http_policy.STOP_STATUSES``, ``CHALLENGE_REASON``); ``source`` names the program
    that recorded it (``STOP_SOURCES``). Never the target, the headers or the body of the
    answer. Only a 429 may end (``until``); for anything else ``until`` is ``None``: a
    person removes the record.
    """

    since: float
    status: int | str
    reason: str
    source: str
    until: float | None = None
    pid: int | None = None

    def active(self, now: float) -> bool:
        return self.until is None or now < self.until

    @property
    def label(self) -> str:
        """``HTTP 403 (odmowa dostępu)``; for a challenge just its reason. For people."""
        canonical = _canonical_reason(self.status) or self.reason
        if isinstance(self.status, int):
            return f"HTTP {self.status} ({canonical})"
        return canonical

    def summary(self) -> str:
        """``HTTP 403 (odmowa dostępu), 2026-10-10 14:34:56+02:00, źródło: probe``.

        For people (``stop status``, ``stop clear``, details); a model gets ``StoppedError``.
        """
        return f"{self.label}, {format_time(self.since)}, źródło: {self.source}"

    def to_json(self) -> dict[str, Any]:
        """The record as ``stop.json`` stores it (``format`` aside)."""
        return {
            "since": _iso_utc(self.since),
            "status": self.status,
            "reason": self.reason,
            "until": None if self.until is None else _iso_utc(self.until),
            "source": self.source,
            "pid": self.pid,
        }


@dataclass(frozen=True)
class UnreadableStop:
    """A ``stop.json`` that cannot be read: a STOP without an end (fail-closed).

    ``problem`` says what is wrong with it, at most ``_PROBLEM_MAX`` characters and never
    the file's content (it may name the file); a person removes it.
    """

    problem: str
    until: None = None

    def active(self, _now: float) -> bool:
        """Always: an unreadable record has no end to compare ``_now`` with."""
        return True


Stop: TypeAlias = StopRecord | UnreadableStop


@dataclass(frozen=True)
class StopStatus:
    """What ``stop.json`` holds at ``checked_at``: no record, a record, or an unreadable one."""

    path: Path
    stop: Stop | None
    checked_at: float

    @property
    def active(self) -> bool:
        return self.stop is not None and self.stop.active(self.checked_at)

    @property
    def seconds_left(self) -> float | None:
        """Until an active STOP ends; ``None`` without one or for a STOP without an end."""
        if not self.active or self.stop is None or self.stop.until is None:
            return None
        return self.stop.until - self.checked_at

    def to_json(self) -> dict[str, Any]:
        record = self.stop.to_json() if isinstance(self.stop, StopRecord) else None
        unreadable = self.stop.problem if isinstance(self.stop, UnreadableStop) else None
        return {
            "active": self.active,
            "seconds_left": self.seconds_left,
            "path": str(self.path),
            "record": record,
            "unreadable": unreadable,
        }


class StoppedError(RuntimeError):
    """An active STOP record: ``slot()`` refused to start, nothing was sent.

    ``stop`` is the record; ``seconds_left`` how long a 429 still holds (``None`` for a
    STOP without an end). The message is for a model as much as for a person: it says
    what stopped the series (from ``status`` alone, never from text in the file) and
    that the series must end. No times, no source, no file, nothing about removing the
    STOP or restarting anything: those are for people (``stop status``, details).
    """

    def __init__(self, stop: Stop, now: float) -> None:
        self.stop = stop
        self.seconds_left = None if stop.until is None else max(0.0, stop.until - now)
        not_sent = "Zapytanie nie zostało wysłane."
        if isinstance(stop, UnreadableStop):
            super().__init__(
                "STOP: seria zapytań do deweloperuch.pl jest wstrzymana bezterminowo, bo zapis "
                f"o wcześniejszym STOP jest nieczytelny. {not_sent} {STOP_INSTRUCTION}"
            )
            return
        message = (
            "STOP: seria zapytań do deweloperuch.pl jest wstrzymana po wcześniejszym STOP "
            f"({_model_label(stop.status)})"
        )
        if self.seconds_left is not None:
            seconds = max(1, math.ceil(self.seconds_left))
            super().__init__(
                f"{message}; wstrzymanie trwa jeszcze ok. {seconds} s. {not_sent} Nie ponawiaj "
                "w tej sesji; przerwij i zgłoś to użytkownikowi."
            )
            return
        super().__init__(f"{message}. {not_sent} {STOP_INSTRUCTION}")


STOP_INSTRUCTION = "Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi."
"""The last sentence of a STOP a model reads."""


def _canonical_reason(status: object) -> str | None:
    """The policy's text for a STOP ``status``; ``None`` for anything else."""
    if status == CHALLENGE:
        return CHALLENGE_REASON
    if isinstance(status, int) and not isinstance(status, bool):
        return STOP_STATUSES.get(status)
    return None


def _model_label(status: int | str) -> str:
    """``HTTP 403, odmowa dostępu``: built from ``status`` only, never from the file."""
    if status == CHALLENGE:
        return "challenge Cloudflare, captcha/WAF"
    return f"HTTP {status}, {_canonical_reason(status) or 'blokada'}"


def format_time(seconds: float) -> str:
    """Wall-clock seconds as local time with its UTC offset: ``2026-10-10 14:34:56+02:00``."""
    try:
        return datetime.fromtimestamp(seconds).astimezone().isoformat(" ", "seconds")
    except (OverflowError, OSError, ValueError):
        return _iso_utc(seconds)


def _iso_utc(seconds: float) -> str:
    try:
        return datetime.fromtimestamp(seconds, UTC).isoformat()
    except (OverflowError, OSError, ValueError):
        return f"{seconds!r} s (epoch)"


class LockWaitTimeoutError(TimeoutError):
    """``clear_stop`` did not get the limiter's lock within its limit; nothing was removed."""

    def __init__(self, waited: float) -> None:
        super().__init__(
            f"Nie udało się uzyskać zamka limitera w ciągu {waited:g} s: inny proces wysyła "
            "zapytanie albo czeka na swoją kolej. Nic nie zostało zdjęte."
        )


def default_lock_dir() -> Path:
    """``${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp``.

    A relative ``XDG_CACHE_HOME`` is ignored, as the XDG Base Directory spec requires.
    """
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    base = Path(xdg) if xdg and os.path.isabs(xdg) else Path.home() / ".cache"
    return base / _APP_DIR


_RecordStop = Callable[[int | str, str, str, float], Stop]


class Slot:
    """Handle of the request that runs inside ``RequestLimiter.slot()``."""

    def __init__(self, record_stop: _RecordStop) -> None:
        self._deferred = 0.0
        self._record_stop = record_stop
        self._open = True

    def stop(self, status: int | str, reason: str, *, source: str) -> Stop:
        """Record a STOP for every process, now, while this slot still holds the lock.

        ``status``: 401, 403, 429 or ``"challenge"``; ``reason``: the reason in words;
        ``source``: who records it (``pakiet``, ``probe``, ``scan_bundles``). Call
        ``defer`` first: a 429 ends when the pause recorded with ``defer`` ends; a 429
        without one, and any other STOP, lasts until a person removes it. An active
        record is kept (the first one wins); a later STOP may only extend its end or make
        it permanent. Returns the record in force. Raises ``OSError`` when the record
        cannot be written, ``ValueError`` (nothing written) for a record that readers would
        refuse (a status without a STOP text, a ``reason`` other than its policy text, a
        ``source`` outside ``STOP_SOURCES``), ``RuntimeError`` after the slot has ended.
        """
        if not self._open:
            raise RuntimeError(
                "Slot.stop() po zakończeniu slotu: STOP trzeba zapisać, zanim slot zwolni zamek."
            )
        return self._record_stop(status, reason, source, self._deferred)

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

    def finish(self) -> float:
        """End the slot (``stop`` refuses from now on); the pause asked with ``defer``.

        Called by ``RequestLimiter.slot`` as the request leaves it.
        """
        self._open = False
        return self._deferred


class RequestLimiter:
    """Shared limit for requests to deweloperuch.pl across threads and processes.

    ``lock_dir`` defaults to ``default_lock_dir()``; tests pass a temporary directory.
    ``min_interval`` may only be raised above 1 s (D2). ``testing_only_allow_fast_interval``
    exists solely so that tests can run fast and must never be set in production code.
    ``clock`` must be a wall clock shared by all processes (``time.time``); ``monotonic``
    (``time.monotonic``) times only this process's own wait for the lock in
    ``clear_stop``, so a wall clock set back or forward neither stretches nor cuts it.
    ``clock``, ``monotonic`` and ``sleep`` are injectable for unit tests.
    """

    def __init__(  # noqa: PLR0913 - keyword-only clocks and sleep, injected by tests
        self,
        lock_dir: str | os.PathLike[str] | None = None,
        *,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
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
        self._monotonic = monotonic

    @property
    def lock_path(self) -> Path:
        return self._lock_dir / LOCK_FILENAME

    @property
    def stop_path(self) -> Path:
        return self._lock_dir / STOP_FILENAME

    @property
    def min_interval(self) -> float:
        return self._min_interval

    @contextmanager
    def slot(self, *, max_wait: float = DEFAULT_MAX_WAIT) -> Iterator[Slot]:
        """Wait for our turn, then hold the lock for the duration of one request.

        Raises ``StoppedError`` (lock released, state untouched) while a STOP record is
        active, before any wait: an earlier STOP of any process ends the series.
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
        if math.isnan(max_wait) or max_wait < 0:
            raise ValueError(f"max_wait musi być liczbą sekund >= 0, podano {max_wait!r}")
        with self._locked() as fd:
            # The STOP record first, before any wait is computed: an active one ends the
            # series here, with the timing state untouched and nothing sent.
            now = self._clock()
            stop = _read_stop(self.stop_path)
            if stop is not None and stop.active(now):
                raise StoppedError(stop, now)
            wait = self._seconds_to_wait(_read_all(fd), now)
            limit = max(max_wait, self._min_interval)
            if wait > limit:
                raise WaitTooLongError(wait, limit)
            if wait > 0:
                self._sleep(wait)
            # Written before the request: a process killed mid-request skips `finally`,
            # and this marker then makes the next one wait min_interval.
            _write_json(fd, {"in_flight_since": self._clock()})
            slot = Slot(self._record_stop)
            try:
                yield slot
            finally:
                deferred = slot.finish()
                end = self._clock()
                gap = max(self._min_interval, deferred)
                _write_json(fd, {"last_end": end, "next_start": end + gap})

    def stop_status(self) -> StopStatus:
        """The STOP record as it is now; creates nothing, never waits.

        Read without the lock, on purpose (an exception to "only under the lock", for this
        read alone): the record is only ever replaced atomically (``os.replace``), so a
        reader sees the old record or the new one, never a part, and a person asking for
        the status does not hang behind a request or a pause of another process.
        ``slot()`` still reads it under the lock, where it matters.
        """
        return StopStatus(self.stop_path, _read_stop(self.stop_path), self._clock())

    def clear_stop(
        self,
        *,
        wait_limit: float = CLEAR_WAIT_LIMIT,
        notice_after: float = CLEAR_NOTICE_AFTER,
        on_wait: Callable[[], None] | None = None,
    ) -> StopStatus:
        """Remove the STOP record under the lock; returns what it held before.

        For people only (CLI ``deweloperuch stop clear``), never for a program that just
        hit a STOP. The pause a 429 recorded in the timing state stays. Leftover temporary
        files of an interrupted write go too.

        The lock is polled: ``on_wait`` is called once after ``notice_after`` seconds
        (another process sends a request or waits for its turn); after ``wait_limit``
        seconds ``LockWaitTimeoutError`` is raised and nothing is removed. Raises ``OSError``
        when the record exists but cannot be removed. Creates nothing without the lock
        directory.
        """
        if not self._lock_dir.is_dir():
            return StopStatus(self.stop_path, None, self._clock())
        wait = _LockWait(wait_limit, notice_after, on_wait)
        with self._locked(wait):
            before = StopStatus(self.stop_path, _read_stop(self.stop_path), self._clock())
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self.stop_path)
            for leftover in self._lock_dir.glob(f"{_TEMP_PREFIX}*{_TEMP_SUFFIX}"):
                with contextlib.suppress(FileNotFoundError):
                    leftover.unlink()
            return before

    @contextmanager
    def _locked(self, wait: "_LockWait | None" = None) -> Iterator[int]:
        """The lock file's descriptor, held exclusively; released and closed on exit.

        Without ``wait`` it blocks until the lock is free (``slot()``); with it, it polls.
        """
        if getattr(_thread_state, "in_slot", False):
            raise RuntimeError(
                "Zagnieżdżony slot limitera w tym samym wątku zablokowałby się na zawsze. "
                "Zakończ bieżące zapytanie przed rozpoczęciem następnego."
            )
        self._lock_dir.mkdir(parents=True, exist_ok=True)
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
        fd = os.open(self.lock_path, flags, 0o600)
        _thread_state.in_slot = True
        try:
            if wait is None:
                lock_file(fd)
            else:
                self._poll_lock(fd, wait)
            try:
                yield fd
            finally:
                # Explicit unlock: a forked child holding a copy of fd must not keep the lock.
                unlock_file(fd)
        finally:
            _thread_state.in_slot = False
            os.close(fd)

    def _poll_lock(self, fd: int, wait: "_LockWait") -> None:
        start = self._monotonic()
        noticed = False
        while True:
            try:
                lock_file(fd, blocking=False)
                return
            except BlockingIOError:
                pass
            waited = self._monotonic() - start
            if waited >= wait.limit:
                raise LockWaitTimeoutError(wait.limit)
            if not noticed and waited >= wait.notice_after and wait.on_wait is not None:
                noticed = True
                wait.on_wait()
            self._sleep(_POLL)

    def _record_stop(self, status: int | str, reason: str, source: str, deferred: float) -> Stop:
        """``Slot.stop``: merge with the record in force and write it; the lock is held.

        Raises ``ValueError`` (nothing written) for a record that readers would refuse:
        a status without a STOP text, a reason other than it, a source outside
        ``STOP_SOURCES``.
        """
        _check_fields(status, reason, source)
        now = self._clock()
        # Only a 429 ends, when the pause recorded with defer() ends; capped like defer().
        until = now + min(deferred, MAX_DEFER) if status == 429 and deferred > 0 else None
        new = StopRecord(now, status, reason, source, until, os.getpid())
        old = _read_stop(self.stop_path)
        kept = _merge_stop(old, new, now)
        if kept is not old and isinstance(kept, StopRecord):
            _write_stop(self.stop_path, kept)
        return kept

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


# --- the STOP record ----------------------------------------------------------------------


def _merge_stop(old: Stop | None, new: StopRecord, now: float) -> Stop:
    """The record to keep: the first active one wins; ``new`` may only extend its end."""
    if old is None or not old.active(now):
        return new
    if isinstance(old, UnreadableStop) or old.until is None:
        return old  # already without an end
    if new.until is None:
        return dataclasses.replace(old, until=None)
    if new.until > old.until:
        return dataclasses.replace(old, until=new.until)
    return old


def _write_stop(path: Path, record: StopRecord) -> None:
    """Replace ``path`` atomically: readers see the old record or the new one, never a part.

    The directory is synced too (best effort), so the record survives a power loss.
    """
    data = json.dumps({"format": STOP_FORMAT, **record.to_json()}, ensure_ascii=False).encode()
    fd, temporary = tempfile.mkstemp(prefix=_TEMP_PREFIX, suffix=_TEMP_SUFFIX, dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    with contextlib.suppress(OSError):
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


class _LockWait:
    """How ``clear_stop`` waits for the lock (see there)."""

    def __init__(
        self, limit: float, notice_after: float, on_wait: Callable[[], None] | None
    ) -> None:
        self.limit = limit
        self.notice_after = notice_after
        self.on_wait = on_wait


def _read_stop(path: Path) -> Stop | None:
    """The record at ``path``; ``None`` without a file. Anything unreadable is a STOP.

    Opened without following a symlink and without blocking (a FIFO would block), and
    only a regular file counts. Never waits, never creates anything.
    """
    try:
        fd = _open_stop(path)
    except FileNotFoundError:
        return None
    except OSError as err:
        return _unreadable(f"nie można otworzyć pliku: {err.strerror or err}")
    if isinstance(fd, UnreadableStop):
        return fd
    try:
        content = _stop_content(fd)
    finally:
        os.close(fd)
    if isinstance(content, UnreadableStop):
        return content
    try:
        return _parse_stop(content)
    except (ValueError, TypeError, KeyError, RecursionError) as err:
        return _unreadable(f"niepoprawna treść: {err}")


def _open_stop(path: Path) -> int | UnreadableStop:
    """Check the record's identity before reading, also without POSIX open flags."""
    before = path.lstat()
    if stat.S_ISLNK(before.st_mode):
        return _unreadable("nie można otworzyć pliku: dowiązanie symboliczne")
    if not stat.S_ISREG(before.st_mode):
        return _unreadable("to nie jest zwykły plik")
    fd = _open_stop_descriptor(path)
    try:
        opened = os.fstat(fd)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise OSError("plik zmienił się podczas otwierania")
        if getattr(opened, "st_file_attributes", 0) & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
            raise OSError("plik jest punktem ponownej analizy")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _open_stop_descriptor(path: Path) -> int:
    if sys.platform == "win32":
        return _open_windows_stop(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    return os.open(path, flags)


def _open_windows_stop(path: Path) -> int:
    """Read without following reparse points or blocking atomic replace/clear.

    CRT ``os.open`` omits FILE_SHARE_DELETE. A status reader lives outside the limiter
    lock, so it must share READ|WRITE|DELETE with the STOP writer. The descriptor owns
    the handle after ``open_osfhandle``; on a failed conversion we close it ourselves.
    """
    if sys.platform == "win32":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create.restype = wintypes.HANDLE
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        # GENERIC_READ; FILE_SHARE_READ|WRITE|DELETE; OPEN_EXISTING;
        # FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_BACKUP_SEMANTICS.
        handle = create(str(path), 0x80000000, 0x7, None, 3, 0x00200000 | 0x02000000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            close(handle)
            raise
    raise RuntimeError("Ten sposób otwierania pliku jest dostępny tylko na Windows.")


def _stop_content(fd: int) -> bytes | UnreadableStop:
    """The bytes of the open record ``fd``; a STOP without an end when it is no regular
    file, cannot be read or is larger than ``_STOP_MAX_BYTES``."""
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return _unreadable("to nie jest zwykły plik")
        chunks: list[bytes] = []
        size = 0
        while size <= _STOP_MAX_BYTES and (chunk := os.read(fd, 16 * 1024)):
            chunks.append(chunk)
            size += len(chunk)
    except OSError as err:
        return _unreadable(f"nie można odczytać pliku: {err.strerror or err}")
    if size > _STOP_MAX_BYTES:
        return _unreadable(f"plik większy niż {_STOP_MAX_BYTES} B")
    return b"".join(chunks)


def _unreadable(problem: str) -> UnreadableStop:
    if len(problem) > _PROBLEM_MAX:
        problem = problem[: _PROBLEM_MAX - 1] + "…"
    return UnreadableStop(problem)


def _parse_stop(raw: bytes) -> StopRecord:
    """A valid record, or an exception whose message never repeats the file's content."""
    try:
        data = json.loads(raw)
    except ValueError:
        raise ValueError("to nie jest poprawny JSON (UTF-8)") from None
    if not isinstance(data, dict):
        raise ValueError("oczekiwano obiektu JSON")
    if type(data.get("format")) is not int or data["format"] != STOP_FORMAT:
        raise ValueError(f"nieznany format, oczekiwano {STOP_FORMAT}")
    status, reason, source = data["status"], data["reason"], data["source"]
    _check_fields(status, reason, source)
    pid = data.get("pid")
    if pid is not None and (type(pid) is not int or pid <= 0):
        raise ValueError("niepoprawny pid")
    until = None if data["until"] is None else _parse_time(data["until"], "until")
    # Only a 429 ends; an end on anything else is ignored (the stricter reading).
    return StopRecord(
        since=_parse_time(data["since"], "since"),
        status=status,
        reason=reason,
        source=source,
        until=until if status == 429 else None,
        pid=pid,
    )


def _check_fields(status: object, reason: object, source: object) -> None:
    """Only what this package writes: a STOP status, its policy text, a known program.

    Anything else in the file (also text meant for a model) makes the record unreadable.
    """
    canonical = _canonical_reason(status)
    if canonical is None:
        raise ValueError("niepoprawny status")
    if reason != canonical:
        raise ValueError("reason nie odpowiada statusowi")
    if source not in STOP_SOURCES:
        raise ValueError("nieznane source")


def _parse_time(value: object, field: str) -> float:
    if not isinstance(value, str):
        raise TypeError(f"{field}: oczekiwano czasu ISO 8601")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field}: niepoprawny czas ISO 8601") from None
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{field}: czas bez strefy")
    seconds = moment.timestamp()
    if not math.isfinite(seconds):
        raise ValueError(f"{field}: niepoprawny czas")
    return seconds
