"""Integration test: threads of one process share the limit (the MCP server path).

Each ``slot()`` opens its own descriptor, so ``flock`` serialises threads exactly
as it serialises processes, with one or several limiter instances.
"""

import threading
import time
from itertools import pairwise
from pathlib import Path

import pytest

from deweloperuch_mcp.throttle import RequestLimiter

MIN_INTERVAL = 0.1  # fast on purpose; allowed only via the testing flag
WORK_S = 0.01
TOLERANCE = 0.02
THREADS = 4
REQUESTS = 2


@pytest.mark.parametrize("instances", [1, 2])
def test_threads_never_overlap_and_keep_min_interval(tmp_path: Path, instances: int) -> None:
    limiters = [
        RequestLimiter(tmp_path, min_interval=MIN_INTERVAL, testing_only_allow_fast_interval=True)
        for _ in range(instances)
    ]
    barrier = threading.Barrier(THREADS)
    guard = threading.Lock()
    records: list[tuple[int, float, float, float]] = []  # thread, asked, start, end
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            limiter = limiters[index % instances]
            barrier.wait(timeout=10)
            for _ in range(REQUESTS):
                asked = time.time()
                with limiter.slot():
                    start = time.time()
                    time.sleep(WORK_S)
                    end = time.time()
                with guard:
                    records.append((index, asked, start, end))
        except BaseException as exc:  # surfaced through the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert len(records) == THREADS * REQUESTS
    slots = sorted((start, end) for _, _, start, end in records)
    for (_, prev_end), (next_start, _) in pairwise(slots):
        assert next_start >= prev_end, "two requests ran at the same time"
        assert next_start - prev_end >= MIN_INTERVAL - TOLERANCE
    # A thread's first request can only wait because of another thread.
    first_wait: dict[int, float] = {}
    for index, asked, start, _ in records:
        first_wait.setdefault(index, start - asked)
    assert max(first_wait.values()) >= MIN_INTERVAL - TOLERANCE, "threads did not compete"
