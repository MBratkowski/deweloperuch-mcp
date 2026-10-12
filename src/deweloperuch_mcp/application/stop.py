"""Use cases: the state of the STOP record and lifting it (D2). Offline, for people."""

from collections.abc import Callable
from typing import Generic, TypeVar

from deweloperuch_mcp.domain.ports import StopControl

Status = TypeVar("Status")


class StopStatus(Generic[Status]):
    """The STOP record at once, without waiting for the limiter's lock; sends nothing."""

    def __init__(self, control: StopControl[Status]) -> None:
        self._control = control

    def __call__(self) -> Status:
        return self._control.status()


class ClearStop(Generic[Status]):
    """Remove the STOP record; returns what it held. No MCP tool calls it (D2): only a
    person, after checking the cause. A process that latched its own STOP still sends
    nothing until restarted; the pause a 429 recorded in the limiter still holds."""

    def __init__(self, control: StopControl[Status]) -> None:
        self._control = control

    def __call__(
        self,
        *,
        wait_limit: float,
        notice_after: float,
        on_wait: Callable[[], None] | None = None,
    ) -> Status:
        return self._control.clear(
            wait_limit=wait_limit, notice_after=notice_after, on_wait=on_wait
        )
