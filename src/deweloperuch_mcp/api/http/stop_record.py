"""``usecases.ports.StopControl`` over the shared limiter's STOP record (D2).

The record lives next to the limiter's lock (``throttle.default_lock_dir``) and is shared
with ``recon/``; reading it never waits for the lock, removing it does.
"""

from collections.abc import Callable

from deweloperuch_mcp.throttle import RequestLimiter, StopStatus


class LimiterStopRecord:
    """The STOP record of ``limiter`` (the shared lock by default)."""

    def __init__(self, limiter: RequestLimiter | None = None) -> None:
        self._limiter = limiter if limiter is not None else RequestLimiter()

    def status(self) -> StopStatus:
        return self._limiter.stop_status()

    def clear(
        self, *, wait_limit: float, notice_after: float, on_wait: Callable[[], None] | None
    ) -> StopStatus:
        return self._limiter.clear_stop(
            wait_limit=wait_limit, notice_after=notice_after, on_wait=on_wait
        )
