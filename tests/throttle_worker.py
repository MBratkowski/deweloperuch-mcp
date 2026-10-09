"""Subprocess worker for tests/test_throttle_multiprocess.py (not a test module).

    python throttle_worker.py LOCK_DIR GO_AT REQUESTS --min-interval S
        [--work S] [--defer S] [--die-in-slot TERM|KILL]

Waits until wall-clock GO_AT so that workers compete for the lock, then runs
REQUESTS fake requests (sleep instead of network) through the limiter and prints
a JSON list of ``[asked, start, end]`` wall-clock times per request: ``asked``
just before entering the slot, ``start``/``end`` inside it. ``--defer`` passes a
simulated Retry-After to ``Slot.defer``. ``--die-in-slot`` prints the record of
the first request (``end`` = moment of death) and kills the process with the
given signal inside the slot, so no ``finally`` runs.
"""

import argparse
import json
import os
import signal
import sys
import time

from deweloperuch_mcp.throttle import RequestLimiter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("lock_dir")
    parser.add_argument("go_at", type=float)
    parser.add_argument("requests", type=int)
    parser.add_argument("--min-interval", type=float, required=True)
    parser.add_argument("--work", type=float, default=0.05)
    parser.add_argument("--defer", type=float)
    parser.add_argument("--die-in-slot", choices=["TERM", "KILL"])
    args = parser.parse_args()

    limiter = RequestLimiter(
        args.lock_dir,
        min_interval=args.min_interval,
        testing_only_allow_fast_interval=True,
    )
    time.sleep(max(0.0, args.go_at - time.time()))
    records: list[list[float]] = []
    for _ in range(args.requests):
        asked = time.time()
        with limiter.slot() as slot:
            start = time.time()
            time.sleep(args.work)
            if args.defer is not None:
                slot.defer(args.defer)
            if args.die_in_slot:
                print(json.dumps([[asked, start, time.time()]]), flush=True)
                os.kill(os.getpid(), getattr(signal, f"SIG{args.die_in_slot}"))
                time.sleep(10)  # never reached: the default action of both signals is to die
                sys.exit("still alive after the signal")
            records.append([asked, start, time.time()])
    print(json.dumps(records))


if __name__ == "__main__":
    main()
