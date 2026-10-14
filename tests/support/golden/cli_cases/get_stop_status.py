"""The golden cases of ``deweloperuch stop status`` (tests/golden/cli/<case>.json)."""

import time

from support.golden.cli import PLANTED, Case, case, record_stop, stop_file_with

CASES: dict[str, Case] = {
    "help_stop_status": case("stop", "status", "--help"),
    # the STOP record
    "stop_status_none": case("stop", "status"),
    "stop_status_none_json": case("stop", "status", "--json"),
    "stop_status_403": case("stop", "status", before=record_stop()),
    "stop_status_403_json": case("stop", "status", "--json", before=record_stop()),
    "stop_status_429": case("stop", "status", before=record_stop(429, "limit zapytań", defer=120)),
    "stop_status_429_json": case(
        "stop", "status", "--json", before=record_stop(429, "limit zapytań", defer=120)
    ),
    "stop_status_429_ended": case(
        "stop",
        "status",
        before=record_stop(429, "limit zapytań", defer=60, clock=lambda: time.time() - 3600),
    ),
    "stop_status_unreadable": case("stop", "status", before=stop_file_with("{")),
    "stop_status_unreadable_json": case("stop", "status", "--json", before=stop_file_with("{")),
    "stop_status_planted_text": case("stop", "status", before=stop_file_with(PLANTED)),
}
