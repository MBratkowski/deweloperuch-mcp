"""Clocks: the use cases' ``Clock`` port, the transport's monotonic clock and the limiter's
wall clock with its sleep, all moved by hand, and a stopped ``datetime`` module.
"""

import datetime as dt
import types
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

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


def frozen_datetime(instant: dt.datetime, local_offset: dt.timedelta) -> types.SimpleNamespace:
    """The ``datetime`` module (as ``dt``) stopped at ``instant`` (aware) on a machine whose
    local time is ``local_offset`` from UTC: ``datetime.now(tz)`` is ``instant`` in ``tz``,
    ``datetime.now()`` and ``date.today()`` are the local time and day."""
    local = (instant.astimezone(dt.UTC) + local_offset).replace(tzinfo=None)

    class FrozenDatetime(dt.datetime):
        @classmethod
        def now(cls, tz: dt.tzinfo | None = None) -> Self:
            moment = local if tz is None else instant.astimezone(tz)
            return cls.fromisoformat(moment.isoformat())

    class FrozenDate(dt.date):
        @classmethod
        def today(cls) -> Self:
            return cls.fromisoformat(local.date().isoformat())

    return types.SimpleNamespace(datetime=FrozenDatetime, date=FrozenDate, UTC=dt.UTC)


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _clock: ports.Clock = FixedClock()


CLOCK = FixedClock(dt.date(2026, 10, 13))
