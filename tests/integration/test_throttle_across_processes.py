"""Integration tests: several real processes share one lock directory.

No network: the "request" is a sleep. Subprocesses talk to the test through
pipes only, so ``--disable-socket`` stays in force without ``--allow-unix-socket``.
Every scenario also asserts that the processes really overlapped in time, so a
slow interpreter start cannot turn it into a sequential (and vacuous) run.
"""

import json
import os
import signal
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from itertools import pairwise
from pathlib import Path

import pytest

from support.paths import SRC, THROTTLE_WORKER

WORKER = THROTTLE_WORKER


MIN_INTERVAL = 0.2  # fast on purpose; allowed only via the testing flag


# Clock reads and sleeps are not perfectly precise; real violations are >= tens of ms.
TOLERANCE = 0.02


Record = tuple[float, float, float]  # asked, start, end


@contextmanager
def spawn(lock_dir: Path, requests: int, *options: str) -> Iterator[subprocess.Popen[str]]:
    cmd = [sys.executable, str(WORKER), str(lock_dir), str(requests)]
    cmd += ["--min-interval", str(MIN_INTERVAL), *options]
    with subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
    ) as proc:
        # Bound handshakes too: killing a stuck worker unblocks readline() on its pipe.
        watchdog = threading.Timer(60, proc.kill)
        watchdog.start()
        try:
            yield proc
        finally:
            watchdog.cancel()
            watchdog.join()
            if proc.poll() is None:
                proc.kill()


def expect_event(proc: subprocess.Popen[str], event: str) -> None:
    assert proc.stderr is not None
    received = proc.stderr.readline().strip()
    assert received == event, f"expected worker event {event!r}, received {received!r}"


def command(proc: subprocess.Popen[str], message: str) -> None:
    assert proc.stdin is not None
    proc.stdin.write(message + "\n")
    proc.stdin.flush()


@contextmanager
def competing_workers(
    lock_dir: Path,
    *,
    workers: int = 2,
    requests: int = 1,
    first_options: tuple[str, ...] = (),
) -> Iterator[list[subprocess.Popen[str]]]:
    """The first owns the slot until every other worker is about to request it."""
    with ExitStack() as stack:
        first = stack.enter_context(spawn(lock_dir, requests, "--hold-in-slot", *first_options))
        others = [stack.enter_context(spawn(lock_dir, requests)) for _ in range(workers - 1)]
        procs = [first, *others]
        for proc in procs:
            expect_event(proc, "ready")
        command(first, "start")
        expect_event(first, "asking")
        expect_event(first, "entered")
        for proc in others:
            command(proc, "start")
            expect_event(proc, "asking")
        command(first, "finish")
        yield procs


def collect(proc: subprocess.Popen[str], returncode: int = 0) -> list[Record]:
    out, err = proc.communicate(timeout=60)
    assert proc.returncode == returncode, err
    return [(asked, start, end) for asked, start, end in json.loads(out)]


def test_processes_never_overlap_and_keep_min_interval(tmp_path: Path) -> None:
    workers, requests = 3, 3
    with competing_workers(tmp_path, workers=workers, requests=requests) as procs:
        runs = [collect(proc) for proc in procs]
    slots = sorted((start, end) for run in runs for _, start, end in run)

    assert len(slots) == workers * requests
    for (_, prev_end), (next_start, _) in pairwise(slots):
        assert next_start >= prev_end, "two requests ran at the same time"
        assert next_start - prev_end >= MIN_INTERVAL - TOLERANCE
    # A process's first request can only wait because of another process.
    first_waits = [start - asked for (asked, start, _), *_ in runs]
    assert max(first_waits) >= MIN_INTERVAL - TOLERANCE, "processes did not compete"


def test_defer_in_one_process_delays_the_next_process(tmp_path: Path) -> None:
    deferred = 1.0
    with competing_workers(tmp_path, first_options=("--work", "0.3", "--defer", str(deferred))) as (
        first,
        second,
    ):
        [(_, first_start, first_end)] = collect(first)
        [(asked, start, _)] = collect(second)

    assert first_start <= asked < first_end, "second process was not queued behind the first"
    assert start - first_end >= deferred - TOLERANCE


@pytest.mark.parametrize(
    "termination",
    [
        "EXIT",
        pytest.param("TERM", marks=pytest.mark.skipif(os.name == "nt", reason="POSIX signal")),
        pytest.param("KILL", marks=pytest.mark.skipif(os.name == "nt", reason="POSIX signal")),
    ],
)
def test_process_terminated_mid_request_still_keeps_min_interval(
    tmp_path: Path, termination: str
) -> None:
    """A crash or default POSIX signal skips ``finally``; the next process still waits."""
    returncode = 23 if termination == "EXIT" else -getattr(signal, f"SIG{termination}")
    with competing_workers(
        tmp_path, first_options=("--work", "0.3", "--die-in-slot", termination)
    ) as (dying, waiting):
        [(_, dying_start, died_at)] = collect(dying, returncode=returncode)
        [(asked, start, _)] = collect(waiting)

    assert dying_start <= asked < died_at, "second process was not queued behind the dying one"
    assert start - died_at >= MIN_INTERVAL - TOLERANCE


def test_a_stop_recorded_by_one_process_keeps_the_next_one_out(tmp_path: Path) -> None:
    """Process B queues behind A; A records a 403 STOP before releasing the lock, so B
    sees it as soon as it holds the lock and never enters its slot."""
    with competing_workers(tmp_path, first_options=("--work", "0.3", "--stop", "403")) as (
        first,
        second,
    ):
        [(_, first_start, first_end)] = collect(first)
        out, err = second.communicate(timeout=60)

    assert second.returncode == 3, err
    refused = json.loads(out)
    assert first_start <= refused["stopped"] < first_end, (
        "second process was not queued behind the first"
    )
    assert "(HTTP 403, odmowa dostępu)" in refused["message"]
    assert "źródło" not in refused["message"]
    # B left the timing state as A wrote it: no in-flight marker, A's end and spacing.
    state = json.loads((tmp_path / "throttle.lock").read_text())
    assert set(state) == {"last_end", "next_start"}
    assert state["next_start"] - state["last_end"] == pytest.approx(MIN_INTERVAL)
    assert state["last_end"] >= first_end
