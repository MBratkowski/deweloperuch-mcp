"""probe.py run in-process: its limiter, lock directory and samples directory of the test."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import probe
from deweloperuch_mcp.throttle import (
    LOCK_FILENAME,
    RequestLimiter,
)

CAPTURED = date(2026, 10, 9)  # `_captured` of the existing samples


@dataclass
class ProbeEnv:
    limiter: RequestLimiter
    lock_dir: Path
    samples_dir: Path

    def run(self, argv: list[str], service: Callable[..., probe.Response], **kw: Any) -> int:
        kw.setdefault("today", CAPTURED)
        return probe.main(
            argv, fetch=service, limiter=self.limiter, samples_dir=self.samples_dir, **kw
        )

    def pause_after_last_request(self) -> float:
        state = json.loads((self.lock_dir / LOCK_FILENAME).read_text())
        return float(state["next_start"] - state["last_end"])
