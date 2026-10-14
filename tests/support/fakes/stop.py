"""``StopControl`` that answers a fixed state and records what it was asked to clear."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from deweloperuch_mcp.usecases import ports


@dataclass
class FakeStopControl:
    cleared: list[tuple[float, float, Callable[[], None] | None]] = field(default_factory=list)

    def status(self) -> str:
        return "state"

    def clear(
        self, *, wait_limit: float, notice_after: float, on_wait: Callable[[], None] | None
    ) -> str:
        self.cleared.append((wait_limit, notice_after, on_wait))
        return "before"


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _stop_control: ports.StopControl[str] = FakeStopControl()
