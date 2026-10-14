"""Subprocess worker for tests/integration/test_throttle_across_processes.py (not a test module).

    python throttle_worker.py LOCK_DIR GO_AT REQUESTS --min-interval S
        [--work S] [--defer S] [--stop STATUS] [--die-in-slot TERM|KILL]

Waits until wall-clock GO_AT so that workers compete for the lock, then runs
REQUESTS fake requests (sleep instead of network) through the limiter and prints
a JSON list of ``[asked, start, end]`` wall-clock times per request: ``asked``
just before entering the slot, ``start``/``end`` inside it. ``--defer`` passes a
simulated Retry-After to ``Slot.defer``. ``--stop`` records a STOP with that HTTP
status (``Slot.stop``) after the work, still inside the slot. A STOP recorded
earlier refuses the slot: the worker then prints ``{"stopped": asked, "message":
...}`` and exits with 3. ``--die-in-slot`` prints the record of the first request
(``end`` = moment of death) and kills the process with the given signal inside the
slot, so no ``finally`` runs.

The network guard of the test suite (pytest-socket) is installed before anything
else runs: the worker never needs a socket, and a mistake must not reach one.
"""

import argparse
import json
import os
import signal
import sys
import time

import pytest_socket

from deweloperuch_mcp.throttle import RequestLimiter, StoppedError


def main() -> None:
    pytest_socket.disable_socket(allow_unix_socket=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("lock_dir")
    parser.add_argument("go_at", type=float)
    parser.add_argument("requests", type=int)
    parser.add_argument("--min-interval", type=float, required=True)
    parser.add_argument("--work", type=float, default=0.05)
    parser.add_argument("--defer", type=float)
    parser.add_argument("--stop", type=int)
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
        try:
            with limiter.slot() as slot:
                start = time.time()
                time.sleep(args.work)
                if args.defer is not None:
                    slot.defer(args.defer)
                if args.stop is not None:
                    slot.stop(args.stop, "odmowa dostępu", source="probe")
                if args.die_in_slot:
                    print(json.dumps([[asked, start, time.time()]]), flush=True)
                    os.kill(os.getpid(), getattr(signal, f"SIG{args.die_in_slot}"))
                    time.sleep(10)  # never reached: the default action of both signals is to die
                    sys.exit("still alive after the signal")
                records.append([asked, start, time.time()])
        except StoppedError as err:
            print(json.dumps({"stopped": asked, "message": str(err)}), flush=True)
            sys.exit(3)
    print(json.dumps(records))


if __name__ == "__main__":
    main()
