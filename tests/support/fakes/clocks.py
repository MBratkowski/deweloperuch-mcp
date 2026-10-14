"""Clocks: the use cases' ``Clock`` port, the transport's monotonic clock and the limiter's
wall clock with its sleep, all moved by hand.
"""

import datetime as dt
from dataclasses import dataclass
from typing import TYPE_CHECKING

from deweloperuch_mcp.usecases import ports


@dataclass(frozen=True)
class FixedClock:
    """``usecases.ports.Clock`` of every golden case: price flags as of one day."""

    day: dt.date = dt.date(2026, 10, 13)

    def today(self) -> dt.date:
        return self.day


class MonotonicClock:
    """Monotonic clock for the cache and the body deadline, moved by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeTime:
    """Wall clock that only moves when the code sleeps or the test advances it."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _clock: ports.Clock = FixedClock()


CLOCK = FixedClock(dt.date(2026, 10, 13))
