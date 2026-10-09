"""Unit tests for the cross-process request limiter (injected clock and sleep)."""

import ast
import fcntl
import json
import math
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from deweloperuch_mcp import throttle
from deweloperuch_mcp.throttle import (
    DEFAULT_MAX_WAIT,
    DEFAULT_MIN_INTERVAL,
    LOCK_FILENAME,
    MAX_DEFER,
    RequestLimiter,
    WaitTooLongError,
    default_lock_dir,
)

THROTTLE_SOURCE = Path(throttle.__file__)
REPO = Path(__file__).resolve().parent.parent


class FakeTime:
    """Wall clock that only moves when the code sleeps or the test advances it."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def fake() -> FakeTime:
    return FakeTime()


def make_limiter(lock_dir: Path, fake: FakeTime, **kwargs: Any) -> RequestLimiter:
    return RequestLimiter(lock_dir, clock=fake.clock, sleep=fake.sleep, **kwargs)


@contextmanager
def other_descriptor(path: Path) -> Iterator[int]:
    """A separate open file description, as another process would have."""
    fd = os.open(path, os.O_RDWR)
    try:
        yield fd
    finally:
        os.close(fd)


def lock_is_free(path: Path) -> bool:
    with other_descriptor(path) as fd:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True


# --- spacing between requests ------------------------------------------------


def test_first_slot_starts_immediately(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot():
        pass

    assert fake.sleeps == []


def test_next_slot_starts_min_interval_after_previous_end(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot():
        fake.advance(0.3)  # the request itself takes 0.3 s
    first_end = fake.now
    with limiter.slot():
        second_start = fake.now

    assert second_start - first_end == pytest.approx(DEFAULT_MIN_INTERVAL)
    assert fake.sleeps == [pytest.approx(DEFAULT_MIN_INTERVAL)]


def test_waits_only_for_the_rest_of_the_interval(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot():
        pass
    fake.advance(0.4)
    with limiter.slot():
        pass

    assert fake.sleeps == [pytest.approx(0.6)]


def test_no_wait_when_interval_already_elapsed(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot():
        pass
    fake.advance(5.0)
    with limiter.slot():
        pass

    assert fake.sleeps == []


def test_slower_min_interval_is_respected(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake, min_interval=2.5)

    with limiter.slot():
        pass
    with limiter.slot():
        pass

    assert fake.sleeps == [pytest.approx(2.5)]


def test_state_is_shared_through_the_lock_file(tmp_path: Path, fake: FakeTime) -> None:
    """Two instances (as in two processes) on one directory share the spacing."""
    first = make_limiter(tmp_path, fake)
    second = make_limiter(tmp_path, fake)

    with first.slot():
        pass
    with second.slot():
        pass

    assert fake.sleeps == [pytest.approx(DEFAULT_MIN_INTERVAL)]


def test_slower_reader_keeps_its_own_interval(tmp_path: Path, fake: FakeTime) -> None:
    """A process configured slower waits its own interval after a faster one's request."""
    fast = make_limiter(tmp_path, fake)
    slow = make_limiter(tmp_path, fake, min_interval=3.0)

    with fast.slot():
        pass
    with slow.slot():
        pass

    assert fake.sleeps == [pytest.approx(3.0)]


# --- Retry-After via defer ---------------------------------------------------


def test_defer_pushes_next_slot(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot() as slot:
        fake.advance(0.2)
        slot.defer(30)
    end = fake.now
    with limiter.slot():
        start = fake.now

    assert start - end == pytest.approx(30.0)


def test_defer_shorter_than_min_interval_keeps_min_interval(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot() as slot:
        slot.defer(0.2)
    with limiter.slot():
        pass

    assert fake.sleeps == [pytest.approx(DEFAULT_MIN_INTERVAL)]


def test_repeated_defer_keeps_the_longest(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot() as slot:
        slot.defer(7)
        slot.defer(3)
    with limiter.slot():
        pass

    assert fake.sleeps == [pytest.approx(7.0)]


def test_defer_applies_to_another_instance(tmp_path: Path, fake: FakeTime) -> None:
    first = make_limiter(tmp_path, fake)
    second = make_limiter(tmp_path, fake)

    with first.slot() as slot:
        slot.defer(12)
    with second.slot():
        pass

    assert fake.sleeps == [pytest.approx(12.0)]


@pytest.mark.parametrize("seconds", [-1.0, -math.inf, math.nan])
def test_defer_rejects_invalid_seconds_without_recording(
    tmp_path: Path, fake: FakeTime, seconds: float
) -> None:
    limiter = make_limiter(tmp_path, fake)

    with pytest.raises(ValueError, match="defer"), limiter.slot() as slot:
        slot.defer(seconds)
    with limiter.slot():
        pass

    assert fake.sleeps == [pytest.approx(DEFAULT_MIN_INTERVAL)]


@pytest.mark.parametrize("seconds", [MAX_DEFER + 1, 7200.0, 1.76e9, math.inf])
def test_defer_above_limit_records_limit_then_raises(
    tmp_path: Path, fake: FakeTime, seconds: float
) -> None:
    """A long, possibly legitimate Retry-After must never shrink to min_interval."""
    limiter = make_limiter(tmp_path, fake)

    with pytest.raises(ValueError, match="defer"), limiter.slot() as slot:
        slot.defer(seconds)

    with pytest.raises(WaitTooLongError) as excinfo, limiter.slot():
        pass
    assert excinfo.value.remaining == pytest.approx(MAX_DEFER)


def test_defer_above_limit_keeps_earlier_pause_as_maximum(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with pytest.raises(ValueError, match="defer"), limiter.slot() as slot:
        slot.defer(30)
        slot.defer(7200)
    with limiter.slot(max_wait=math.inf):
        pass

    assert fake.sleeps == [pytest.approx(MAX_DEFER)]


def test_defer_accepts_the_upper_limit(tmp_path: Path, fake: FakeTime) -> None:
    assert MAX_DEFER == 3600.0
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot() as slot:
        slot.defer(MAX_DEFER)
    with limiter.slot(max_wait=MAX_DEFER):
        pass

    assert fake.sleeps == [pytest.approx(MAX_DEFER)]


# --- max_wait ------------------------------------------------------------------


def test_too_long_wait_raises_with_remaining_time(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)
    with limiter.slot() as slot:
        slot.defer(120)
    fake.advance(20)

    with pytest.raises(WaitTooLongError) as excinfo, limiter.slot():
        pytest.fail("the request must not run")

    assert excinfo.value.remaining == pytest.approx(100.0)
    assert excinfo.value.max_wait == DEFAULT_MAX_WAIT == 60.0
    assert "100" in str(excinfo.value)
    assert fake.sleeps == []
    assert lock_is_free(limiter.lock_path)


def test_too_long_wait_leaves_state_untouched(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)
    with limiter.slot() as slot:
        slot.defer(120)
    end = fake.now

    with pytest.raises(WaitTooLongError), limiter.slot():
        pass
    with limiter.slot(max_wait=200):
        start = fake.now

    assert start - end == pytest.approx(120.0)


def test_wait_within_max_wait_sleeps(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)
    with limiter.slot() as slot:
        slot.defer(45)

    with limiter.slot(max_wait=45):
        pass

    assert fake.sleeps == [pytest.approx(45.0)]


@pytest.mark.parametrize("max_wait", [-1.0, math.nan])
def test_invalid_max_wait_rejected(tmp_path: Path, fake: FakeTime, max_wait: float) -> None:
    limiter = make_limiter(tmp_path, fake)

    with pytest.raises(ValueError, match="max_wait"), limiter.slot(max_wait=max_wait):
        pass


def test_min_interval_above_max_wait_is_regular_spacing(tmp_path: Path, fake: FakeTime) -> None:
    """D2 allows slower limits; their regular spacing must not end in an error."""
    limiter = make_limiter(tmp_path, fake, min_interval=90)

    with limiter.slot():
        pass
    with limiter.slot(max_wait=60):
        pass

    assert fake.sleeps == [pytest.approx(90.0)]


def test_min_interval_above_max_wait_still_limits_deferred_pause(
    tmp_path: Path, fake: FakeTime
) -> None:
    limiter = make_limiter(tmp_path, fake, min_interval=90)
    with limiter.slot() as slot:
        slot.defer(120)

    with pytest.raises(WaitTooLongError) as excinfo, limiter.slot(max_wait=60):
        pass

    assert excinfo.value.remaining == pytest.approx(120.0)
    assert excinfo.value.max_wait == 90.0


@pytest.mark.parametrize(
    ("remaining", "max_wait", "shown"), [(60.4, 60, "za 61 s"), (0.3, 0, "za 1 s")]
)
def test_wait_too_long_message_rounds_remaining_up(
    remaining: float, max_wait: float, shown: str
) -> None:
    assert shown in str(WaitTooLongError(remaining, max_wait))


# --- exclusivity and failures ------------------------------------------------


def test_lock_is_held_for_the_whole_slot(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot():
        assert not lock_is_free(limiter.lock_path)
        fake.advance(0.5)
        assert not lock_is_free(limiter.lock_path)

    assert lock_is_free(limiter.lock_path)


def test_exception_in_slot_releases_lock_and_keeps_interval(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with pytest.raises(ConnectionError), limiter.slot():
        fake.advance(0.1)
        raise ConnectionError("request failed")
    failed_end = fake.now

    assert lock_is_free(limiter.lock_path)
    with limiter.slot():
        assert fake.now - failed_end == pytest.approx(DEFAULT_MIN_INTERVAL)


def test_exception_after_defer_keeps_deferred_pause(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with pytest.raises(RuntimeError), limiter.slot() as slot:
        slot.defer(20)
        raise RuntimeError("429 Too Many Requests")
    with limiter.slot():
        pass

    assert fake.sleeps == [pytest.approx(20.0)]


def test_in_flight_marker_covers_a_killed_process(tmp_path: Path, fake: FakeTime) -> None:
    """SIGTERM/SIGKILL skip ``finally``: the file must be conservative during the request."""
    limiter = make_limiter(tmp_path / "alive", fake)
    with limiter.slot():
        pass
    fake.advance(100.0)  # the completed state alone would allow an immediate start

    with limiter.slot(), other_descriptor(limiter.lock_path) as fd:
        started = fake.now
        mid_request = os.read(fd, 4096)

    assert json.loads(mid_request) == {"in_flight_since": started}
    # A process killed at this point leaves exactly these bytes behind.
    dead = tmp_path / "dead"
    dead.mkdir()
    (dead / LOCK_FILENAME).write_bytes(mid_request)
    fake.sleeps.clear()
    with make_limiter(dead, fake).slot():
        pass
    assert fake.sleeps == [pytest.approx(DEFAULT_MIN_INTERVAL)]


def test_failed_state_write_keeps_in_flight_marker(
    tmp_path: Path, fake: FakeTime, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Write first, truncate second: a failed final write never leaves an empty file."""
    limiter = make_limiter(tmp_path, fake)

    def disk_full(fd: int, data: bytes) -> int:
        raise OSError(28, "No space left on device")

    with pytest.raises(OSError, match="No space"), limiter.slot():
        monkeypatch.setattr(os, "write", disk_full)  # only the final state write fails
    monkeypatch.undo()

    assert b"in_flight_since" in limiter.lock_path.read_bytes()
    with limiter.slot():
        pass
    assert fake.sleeps == [pytest.approx(DEFAULT_MIN_INTERVAL)]


def test_state_write_truncates_longer_old_state(tmp_path: Path, fake: FakeTime) -> None:
    # Extra key: the reader ignores it, and its leftover tail would not be valid JSON.
    padded = json.dumps({"last_end": 1.0, "next_start": 2.0, "padding": "x" * 512}).encode()
    (tmp_path / LOCK_FILENAME).write_bytes(padded)
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot():
        pass

    state = json.loads(limiter.lock_path.read_bytes())
    assert state == {"last_end": fake.now, "next_start": fake.now + DEFAULT_MIN_INTERVAL}
    assert limiter.lock_path.stat().st_size < 100


def test_nested_slot_raises_instead_of_deadlocking(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot(), pytest.raises(RuntimeError, match="Zagnieżdżony"), limiter.slot():
        pass

    with limiter.slot():  # the outer slot still released everything
        pass


def test_clock_moved_backwards_waits_at_most_one_interval(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot():
        pass
    fake.now -= 3600.0  # wall clock set back by an hour
    with limiter.slot():
        pass

    assert fake.sleeps == [pytest.approx(DEFAULT_MIN_INTERVAL)]


@pytest.mark.parametrize(
    "content",
    [
        b"garbage",
        b"[1, 2]",
        b'{"last_end": 5}',
        b"{}",
        b'{"last_end": NaN, "next_start": 1}',
        b'{"last_end": 10, "next_start": Infinity}',
        b'{"last_end": 10, "next_start": 5}',
        # a shorter state written over a longer one without truncation
        b'{"last_end": 1.0, "next_start": 2.0}0, "next_start": 9}',
    ],
)
def test_unreadable_state_waits_min_interval(
    tmp_path: Path, fake: FakeTime, content: bytes
) -> None:
    (tmp_path / LOCK_FILENAME).write_bytes(content)
    limiter = make_limiter(tmp_path, fake)

    with limiter.slot():
        pass

    assert fake.sleeps == [pytest.approx(DEFAULT_MIN_INTERVAL)]


def test_creates_missing_lock_directory(tmp_path: Path, fake: FakeTime) -> None:
    lock_dir = tmp_path / "nested" / "cache"
    limiter = make_limiter(lock_dir, fake)

    with limiter.slot():
        pass

    assert limiter.lock_path == lock_dir / LOCK_FILENAME
    assert limiter.lock_path.is_file()


def test_unsupported_platform_fails_with_readable_error(
    tmp_path: Path, fake: FakeTime, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(throttle, "_HAS_FLOCK", False)
    limiter = make_limiter(tmp_path, fake)

    with pytest.raises(RuntimeError, match="Windows"), limiter.slot():
        pass


# --- configuration -----------------------------------------------------------


@pytest.mark.parametrize("min_interval", [0.0, 0.2, 0.5, 0.999])
def test_sub_second_interval_rejected_without_testing_flag(
    tmp_path: Path, min_interval: float
) -> None:
    with pytest.raises(ValueError, match="D2"):
        RequestLimiter(tmp_path, min_interval=min_interval)


def test_sub_second_interval_allowed_with_testing_flag(tmp_path: Path, fake: FakeTime) -> None:
    limiter = make_limiter(tmp_path, fake, min_interval=0.2, testing_only_allow_fast_interval=True)

    with limiter.slot():
        pass
    with limiter.slot():
        pass

    assert limiter.min_interval == 0.2
    assert fake.sleeps == [pytest.approx(0.2)]


@pytest.mark.parametrize("min_interval", [-1.0, math.nan, math.inf])
def test_invalid_interval_rejected_even_with_testing_flag(
    tmp_path: Path, min_interval: float
) -> None:
    with pytest.raises(ValueError, match="min_interval"):
        RequestLimiter(tmp_path, min_interval=min_interval, testing_only_allow_fast_interval=True)


def test_default_interval_is_one_second(tmp_path: Path) -> None:
    assert DEFAULT_MIN_INTERVAL == 1.0
    assert RequestLimiter(tmp_path).min_interval == 1.0


def test_default_lock_dir_follows_xdg_cache_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    assert default_lock_dir() == tmp_path / "deweloperuch-mcp"
    assert RequestLimiter().lock_path == tmp_path / "deweloperuch-mcp" / LOCK_FILENAME


@pytest.mark.parametrize("xdg", [None, "", "relative/cache"])
def test_default_lock_dir_falls_back_to_home_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, xdg: str | None
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    if xdg is None:
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_CACHE_HOME", xdg)

    assert default_lock_dir() == tmp_path / ".cache" / "deweloperuch-mcp"


def test_testing_flag_is_used_only_in_tests() -> None:
    enabled = re.compile(r"testing_only_allow_fast_interval\s*=\s*True")
    offenders = [
        str(path.relative_to(REPO))
        for top in ("src", "recon")
        for path in sorted((REPO / top).rglob("*.py"))
        if enabled.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


# --- stdlib only ---------------------------------------------------------------


def test_throttle_imports_only_stdlib() -> None:
    """recon/ scripts import this module without the package's dependencies."""
    tree = ast.parse(THROTTLE_SOURCE.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative imports pull in the package"
            assert node.module is not None
            imported.append(node.module)

    assert imported, "parser found no imports at all"
    non_stdlib = [m for m in imported if m.split(".")[0] not in sys.stdlib_module_names]
    assert non_stdlib == []
