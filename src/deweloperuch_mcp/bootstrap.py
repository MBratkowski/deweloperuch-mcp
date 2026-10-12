"""The composition root (D13): the infrastructure wired into the use cases.

``Session`` is what a process uses to reach the service: one per CLI run, one for the
life of the MCP server, closed on exit. It owns the HTTP client (the shared limiter, the
in-memory cache) and builds the adapters of the ports and the use cases over it::

    with Session() as session:
        found = session.search_offers(OfferSearchCriteria.parse("warszawa", price_max=700_000))

The STOP latch belongs to the process (``infrastructure.deweloperuch.transport``): after a
STOP (401, 403, 429, challenge) in any session, every use case that needs the network
raises the same ``ServiceBlockedError`` without sending anything, and the STOP is
recorded in the shared limiter for every other process. A closed session raises
``SessionClosedError``.

``stop_status`` and ``clear_stop`` work offline on that record, without a session.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Self

from deweloperuch_mcp.application import stop
from deweloperuch_mcp.application.investments import GetInvestment
from deweloperuch_mcp.application.locations import SearchLocations
from deweloperuch_mcp.application.offers import GetOffer, SearchOffers
from deweloperuch_mcp.application.statistics import GetGovernmentStatistics
from deweloperuch_mcp.infrastructure.deweloperuch.links import ServicePageLinks
from deweloperuch_mcp.infrastructure.deweloperuch.locations import ServiceLocationDirectory
from deweloperuch_mcp.infrastructure.deweloperuch.offers import (
    ServiceInvestmentCatalog,
    ServiceOfferCatalog,
)
from deweloperuch_mcp.infrastructure.deweloperuch.statistics import GovernmentStatisticsAdapter
from deweloperuch_mcp.infrastructure.deweloperuch.transport import HttpClient
from deweloperuch_mcp.infrastructure.stop_record import LimiterStopRecord
from deweloperuch_mcp.throttle import (
    CLEAR_NOTICE_AFTER,
    CLEAR_WAIT_LIMIT,
    DEFAULT_MAX_WAIT,
    RequestLimiter,
    StopStatus,
)
from deweloperuch_mcp.throttle import LockWaitTimeout as LockWaitTimeout
from deweloperuch_mcp.throttle import StopRecord as StopRecord
from deweloperuch_mcp.throttle import UnreadableStop as UnreadableStop
from deweloperuch_mcp.throttle import format_time as format_time

StopState = StopStatus
"""The STOP record's state as the limiter reports it (``throttle.StopStatus``)."""

# The STOP record's state as the limiter reports it, for the CLI's ``stop`` commands (the
# use cases only pass it on): ``StopState``, ``StopRecord``, ``UnreadableStop``,
# ``LockWaitTimeout`` and ``format_time`` are re-exported above.


class Session:
    """The connection to the service that a process uses, with its use cases.

    ``limiter`` defaults to the lock shared with ``recon/``; ``max_wait`` is the longest
    pause before ``LimiterWaitError``. Close it at the end (``close()`` or ``with``).
    """

    def __init__(
        self, *, limiter: RequestLimiter | None = None, max_wait: float = DEFAULT_MAX_WAIT
    ) -> None:
        self._http = HttpClient(limiter=limiter, max_wait=max_wait)
        links = ServicePageLinks()
        offers = ServiceOfferCatalog(self._http)
        investments = ServiceInvestmentCatalog(self._http)
        self.search_locations = SearchLocations(ServiceLocationDirectory(self._http))
        self.search_offers = SearchOffers(offers, links)
        self.get_offer = GetOffer(investments, offers, links)
        self.get_investment = GetInvestment(investments, links)
        self.get_government_statistics = GetGovernmentStatistics(
            GovernmentStatisticsAdapter(self._http), links
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    @property
    def closed(self) -> bool:
        return self._http.closed


_sessions: Callable[[], Session] | None = None


def new_session() -> Session:
    """A session for one CLI run or the MCP server's lifetime: ``Session()``, unless
    ``sessions_from`` says otherwise (tests: a limiter without the pause)."""
    return Session() if _sessions is None else _sessions()


@contextmanager
def sessions_from(factory: Callable[[], Session]) -> Iterator[None]:
    """Within the block, ``new_session`` makes its sessions with ``factory``."""
    global _sessions
    previous, _sessions = _sessions, factory
    try:
        yield
    finally:
        _sessions = previous


def stop_status(limiter: RequestLimiter | None = None) -> StopState:
    """The STOP record of the shared limiter (``limiter`` defaults to the shared lock).

    Offline and immediate: reads a local file without waiting for the limiter's lock,
    creates nothing, sends nothing.
    """
    return stop.StopStatus(LimiterStopRecord(limiter))()


def clear_stop(
    limiter: RequestLimiter | None = None,
    *,
    wait_limit: float = CLEAR_WAIT_LIMIT,
    notice_after: float = CLEAR_NOTICE_AFTER,
    on_wait: Callable[[], None] | None = None,
) -> StopState:
    """Remove the STOP record; returns what it held. For people only: no MCP tool calls it.

    Offline. Waits for the limiter's lock: ``on_wait`` once after ``notice_after`` s,
    ``LockWaitTimeout`` (nothing removed) after ``wait_limit`` s. Raises ``OSError`` when
    the record cannot be removed.
    """
    return stop.ClearStop(LimiterStopRecord(limiter))(
        wait_limit=wait_limit, notice_after=notice_after, on_wait=on_wait
    )
