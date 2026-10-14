"""The golden cases of ``deweloperuch stop clear`` (tests/golden/cli/<case>.json)."""

import time

from support.golden.cli import Case, case, record_stop, stop_file_as_directory, stop_file_with

CASES: dict[str, Case] = {
    "help_stop_clear": case("stop", "clear", "--help"),
    "stop_clear_none": case("stop", "clear"),
    "stop_clear_403": case("stop", "clear", before=record_stop()),
    "stop_clear_429": case("stop", "clear", before=record_stop(429, "limit zapytań", defer=120)),
    "stop_clear_429_ended": case(
        "stop",
        "clear",
        before=record_stop(429, "limit zapytań", defer=60, clock=lambda: time.time() - 3600),
    ),
    "stop_clear_unreadable": case("stop", "clear", before=stop_file_with("garbage")),
    "stop_clear_cannot_remove": case("stop", "clear", before=stop_file_as_directory),
}
