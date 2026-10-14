"""Use case ``ClearStop``: lifting the STOP record (D2). Offline, for people."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Self, TypeVar

from deweloperuch_mcp.usecases.ports import StopControl

Status = TypeVar("Status")


@dataclass(frozen=True, kw_only=True)
class ClearStopRequest:
    """How long to wait for the limiter's lock: ``on_wait`` once after ``notice_after``
    s, giving up (nothing removed) after ``wait_limit`` s."""

    wait_limit: float
    notice_after: float
    on_wait: Callable[[], None] | None = None

    @classmethod
    def parse(
        cls, *, wait_limit: float, notice_after: float, on_wait: Callable[[], None] | None = None
    ) -> Self:
        """The caller's own settings, not a person's input: nothing to check."""
        return cls(wait_limit=wait_limit, notice_after=notice_after, on_wait=on_wait)


@dataclass(frozen=True, kw_only=True)
class ClearStopResult(Generic[Status]):
    """What the record held before it was removed (the use case only passes it on)."""

    before: Status


class ClearStop(Generic[Status]):
    """Remove the STOP record; the result says what it held. No MCP tool calls it (D2):
    only a person, after checking the cause. A process that latched its own STOP still
    sends nothing until restarted; the pause a 429 recorded in the limiter still holds."""

    def __init__(self, control: StopControl[Status]) -> None:
        self._control = control

    def execute(self, request: ClearStopRequest) -> ClearStopResult[Status]:
        before = self._control.clear(
            wait_limit=request.wait_limit,
            notice_after=request.notice_after,
            on_wait=request.on_wait,
        )
        return ClearStopResult(before=before)
