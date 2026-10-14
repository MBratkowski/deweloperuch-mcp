"""Use case ``GetStopStatus``: the state of the STOP record (D2). Offline, for people."""

from dataclasses import dataclass
from typing import Generic, Self, TypeVar

from deweloperuch_mcp.usecases.ports import StopControl

Status = TypeVar("Status")


@dataclass(frozen=True, kw_only=True)
class GetStopStatusRequest:
    """Nothing to choose: the record is one for every process."""

    @classmethod
    def parse(cls) -> Self:
        return cls()


@dataclass(frozen=True, kw_only=True)
class GetStopStatusResult(Generic[Status]):
    """The record's state as the limiter reports it (the use case only passes it on)."""

    state: Status


class GetStopStatus(Generic[Status]):
    """The STOP record at once, without waiting for the limiter's lock; sends nothing."""

    def __init__(self, control: StopControl[Status]) -> None:
        self._control = control

    def execute(self, _request: GetStopStatusRequest) -> GetStopStatusResult[Status]:
        """The record's state; the request has nothing to choose."""
        return GetStopStatusResult(state=self._control.status())
