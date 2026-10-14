"""scan_bundles.py run in-process over the fake site, with the test's limiter, cache and
output directories.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import scan_bundles
from deweloperuch_mcp.throttle import LOCK_FILENAME, RequestLimiter
from http_common import Response
from support.fakes.scanner_site import FakeScannedSite


@dataclass
class ScannerEnv:
    limiter: RequestLimiter
    lock_dir: Path
    cache_dir: Path

    def site(self, **kw: Any) -> FakeScannedSite:
        return FakeScannedSite(self.lock_dir / LOCK_FILENAME, **kw)

    def run(self, argv: list[str], site: Callable[..., Response]) -> int:
        return scan_bundles.main(argv, fetch=site, limiter=self.limiter, cache_dir=self.cache_dir)

    def pause_after_last_request(self) -> float:
        state = json.loads((self.lock_dir / LOCK_FILENAME).read_text())
        return float(state["next_start"] - state["last_end"])
