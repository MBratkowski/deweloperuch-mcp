"""Subprocess worker for tests/integration/test_throttle_across_processes.py (not a test module).

    python throttle_worker.py LOCK_DIR REQUESTS --min-interval S
        [--work S] [--defer S] [--stop STATUS] [--die-in-slot EXIT|TERM|KILL] [--hold-in-slot]

Reports ``ready`` on stderr and waits for ``start`` on stdin, then runs
REQUESTS fake requests (sleep instead of network) through the limiter and prints
a JSON list of ``[asked, start, end]`` wall-clock times per request: ``asked``
just before entering the slot, ``start``/``end`` inside it. ``--defer`` passes a
simulated Retry-After to ``Slot.defer``. ``--stop`` records a STOP with that HTTP
status (``Slot.stop``) after the work, still inside the slot. A STOP recorded
earlier refuses the slot: the worker then prints ``{"stopped": asked, "message":
...}`` and exits with 3. ``--die-in-slot`` prints the record of the first request
(``end`` = moment of death) and ends the process inside the slot, so no ``finally``
runs. ``EXIT`` uses ``os._exit(23)`` on every platform; ``TERM``/``KILL`` use POSIX signals.

Before its first slot attempt it reports ``asking``. ``--hold-in-slot`` reports
``entered`` from inside that slot and waits for ``finish``, so the parent can start
contenders while the slot is certainly held, regardless of interpreter startup order.

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


def synchronize(event: str, command: str | None = None) -> None:
    print(event, file=sys.stderr, flush=True)
    if command is not None and sys.stdin.readline().strip() != command:
        raise RuntimeError(f"Expected parent command {command!r}")


def main() -> None:
    pytest_socket.disable_socket(allow_unix_socket=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("lock_dir")
    parser.add_argument("requests", type=int)
    parser.add_argument("--min-interval", type=float, required=True)
    parser.add_argument("--work", type=float, default=0.05)
    parser.add_argument("--defer", type=float)
    parser.add_argument("--stop", type=int)
    parser.add_argument("--die-in-slot", choices=["EXIT", "TERM", "KILL"])
    parser.add_argument("--hold-in-slot", action="store_true")
    args = parser.parse_args()

    limiter = RequestLimiter(
        args.lock_dir,
        min_interval=args.min_interval,
        testing_only_allow_fast_interval=True,
    )
    synchronize("ready", "start")
    records: list[list[float]] = []
    for index in range(args.requests):
        asked = time.time()
        if index == 0:
            synchronize("asking")
        try:
            with limiter.slot() as slot:
                start = time.time()
                if index == 0 and args.hold_in_slot:
                    synchronize("entered", "finish")
                time.sleep(args.work)
                if args.defer is not None:
                    slot.defer(args.defer)
                if args.stop is not None:
                    slot.stop(args.stop, "odmowa dostępu", source="probe")
                if args.die_in_slot:
                    print(json.dumps([[asked, start, time.time()]]), flush=True)
                    if args.die_in_slot == "EXIT":
                        os._exit(23)
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
