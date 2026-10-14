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
import time
from itertools import pairwise
from pathlib import Path

import pytest

from support.paths import SRC, THROTTLE_WORKER

WORKER = THROTTLE_WORKER


MIN_INTERVAL = 0.2  # fast on purpose; allowed only via the testing flag


# Clock reads and sleeps are not perfectly precise; real violations are >= tens of ms.
TOLERANCE = 0.02


STARTUP_S = 1.0  # time for interpreters to start before the workers hit the lock


Record = tuple[float, float, float]  # asked, start, end


def spawn(lock_dir: Path, go_at: float, requests: int, *options: str) -> subprocess.Popen[str]:
    cmd = [sys.executable, str(WORKER), str(lock_dir), str(go_at), str(requests)]
    cmd += ["--min-interval", str(MIN_INTERVAL), *options]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
    )


def collect(proc: subprocess.Popen[str], returncode: int = 0) -> list[Record]:
    out, err = proc.communicate(timeout=60)
    assert proc.returncode == returncode, err
    return [(asked, start, end) for asked, start, end in json.loads(out)]


def test_processes_never_overlap_and_keep_min_interval(tmp_path: Path) -> None:
    workers, requests = 3, 3
    go_at = time.time() + STARTUP_S
    procs = [spawn(tmp_path, go_at, requests) for _ in range(workers)]
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
    go_at = time.time() + STARTUP_S
    first = spawn(tmp_path, go_at, 1, "--work", "0.3", "--defer", str(deferred))
    second = spawn(tmp_path, go_at + 0.1, 1)
    [(_, _, first_end)] = collect(first)
    [(asked, start, _)] = collect(second)

    assert asked < first_end, "second process was not queued behind the first"
    assert start - first_end >= deferred - TOLERANCE


@pytest.mark.parametrize("sig", ["TERM", "KILL"])
def test_process_killed_mid_request_still_keeps_min_interval(tmp_path: Path, sig: str) -> None:
    """Default SIGTERM/SIGKILL skip ``finally``; the next process must still wait."""
    go_at = time.time() + STARTUP_S
    dying = spawn(tmp_path, go_at, 1, "--work", "0.3", "--die-in-slot", sig)
    waiting = spawn(tmp_path, go_at + 0.1, 1)
    [(_, _, died_at)] = collect(dying, returncode=-getattr(signal, f"SIG{sig}"))
    [(asked, start, _)] = collect(waiting)

    assert asked < died_at, "second process was not queued behind the dying one"
    assert start - died_at >= MIN_INTERVAL - TOLERANCE


def test_a_stop_recorded_by_one_process_keeps_the_next_one_out(tmp_path: Path) -> None:
    """Process B queues behind A; A records a 403 STOP before releasing the lock, so B
    sees it as soon as it holds the lock and never enters its slot."""
    go_at = time.time() + STARTUP_S
    first = spawn(tmp_path, go_at, 1, "--work", "0.3", "--stop", "403")
    second = spawn(tmp_path, go_at + 0.1, 1)
    [(_, _, first_end)] = collect(first)
    out, err = second.communicate(timeout=60)

    assert second.returncode == 3, err
    refused = json.loads(out)
    assert refused["stopped"] < first_end, "second process was not queued behind the first"
    assert "(HTTP 403, odmowa dostępu)" in refused["message"]
    assert "źródło" not in refused["message"]
    # B left the timing state as A wrote it: no in-flight marker, A's end and spacing.
    state = json.loads((tmp_path / "throttle.lock").read_text())
    assert set(state) == {"last_end", "next_start"}
    assert state["next_start"] - state["last_end"] == pytest.approx(MIN_INTERVAL)
    assert state["last_end"] >= first_end
