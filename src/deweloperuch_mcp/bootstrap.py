"""The composition root (D13, D16): the adapters of ``api`` wired into the use cases.

``Session`` is what a process uses to reach the service: one per CLI run, one for the
life of the MCP server, closed on exit. It owns the HTTP client (the shared limiter, the
in-memory cache) and builds the adapters of the ports and the use cases over it::

    with Session() as session:
        found = session.search_offers.execute(
            SearchOffersRequest.parse(city="warszawa", price_max=700_000)
        )

The STOP latch belongs to the process (``api.http.transport``): after a
STOP (401, 403, 429, challenge) in any session, every use case that needs the network
raises the same ``ServiceBlockedError`` without sending anything, and the STOP is
recorded in the shared limiter for every other process. A closed session raises
``SessionClosedError``.

``StopUseCases`` work offline on that record, without a session.
"""

import datetime as dt
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Self

from deweloperuch_mcp.api.adapters.buildings_api import BuildingsApi
from deweloperuch_mcp.api.adapters.city_sales_api import CitySalesApi
from deweloperuch_mcp.api.adapters.developer_profile_api import DeveloperProfileApi
from deweloperuch_mcp.api.adapters.developer_search_api import DeveloperSearchApi
from deweloperuch_mcp.api.adapters.government_statistics_api import GovernmentStatisticsApi
from deweloperuch_mcp.api.adapters.investment_search_api import InvestmentSearchApi
from deweloperuch_mcp.api.adapters.investments_api import InvestmentsApi
from deweloperuch_mcp.api.adapters.locations_api import LocationsApi
from deweloperuch_mcp.api.adapters.offers_api import OffersApi
from deweloperuch_mcp.api.adapters.transaction_ranking_api import TransactionRankingApi
from deweloperuch_mcp.api.adapters.transaction_statistics_api import TransactionStatisticsApi
from deweloperuch_mcp.api.adapters.valuation_api import ValuationApi
from deweloperuch_mcp.api.http.stop_record import LimiterStopRecord
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.links import ServicePageLinks
from deweloperuch_mcp.throttle import (
    DEFAULT_MAX_WAIT,
    RequestLimiter,
    StopStatus,
)
from deweloperuch_mcp.throttle import LockWaitTimeoutError as LockWaitTimeoutError
from deweloperuch_mcp.throttle import StopRecord as StopRecord
from deweloperuch_mcp.throttle import UnreadableStop as UnreadableStop
from deweloperuch_mcp.throttle import format_time as format_time
from deweloperuch_mcp.usecases.clear_stop import ClearStop
from deweloperuch_mcp.usecases.estimate_property_value import EstimatePropertyValue
from deweloperuch_mcp.usecases.get_building import GetBuilding
from deweloperuch_mcp.usecases.get_developer import GetDeveloper
from deweloperuch_mcp.usecases.get_government_statistics import GetGovernmentStatistics
from deweloperuch_mcp.usecases.get_investment import GetInvestment
from deweloperuch_mcp.usecases.get_market_statistics import GetMarketStatistics
from deweloperuch_mcp.usecases.get_offer import GetOffer
from deweloperuch_mcp.usecases.get_stop_status import GetStopStatus
from deweloperuch_mcp.usecases.get_transaction_statistics import GetTransactionStatistics
from deweloperuch_mcp.usecases.ports import Clock
from deweloperuch_mcp.usecases.rank_locations import RankLocations
from deweloperuch_mcp.usecases.search_developers import SearchDevelopers
from deweloperuch_mcp.usecases.search_investments import SearchInvestments
from deweloperuch_mcp.usecases.search_locations import SearchLocations
from deweloperuch_mcp.usecases.search_offers import SearchOffers


class SystemClock:
    """``usecases.ports.Clock`` of the process: today in UTC, the time zone of the
    service's dates (``api.dto.dto.Dto._day``)."""

    def today(self) -> dt.date:
        return dt.datetime.now(dt.UTC).date()


StopState = StopStatus
"""The STOP record's state as the limiter reports it (``throttle.StopStatus``)."""

# The STOP record's state as the limiter reports it, for the CLI's ``stop`` commands (the
# use cases only pass it on): ``StopState``, ``StopRecord``, ``UnreadableStop``,
# ``LockWaitTimeoutError`` and ``format_time`` are re-exported above.


class Session:
    """The connection to the service that a process uses, with its use cases.

    ``limiter`` defaults to the lock shared with ``recon/``; ``max_wait`` is the longest
    pause before ``LimiterWaitError``; ``clock`` gives today's date (price flags), by
    default in UTC. Close it at the end (``close()`` or ``with``).
    """

    def __init__(
        self,
        *,
        limiter: RequestLimiter | None = None,
        max_wait: float = DEFAULT_MAX_WAIT,
        clock: Clock | None = None,
    ) -> None:
        self._http = HttpClient(limiter=limiter, max_wait=max_wait)
        links = ServicePageLinks()
        offers = OffersApi(self._http)
        investments = InvestmentsApi(self._http)
        self.search_locations = SearchLocations(LocationsApi(self._http))
        self.search_offers = SearchOffers(offers, links)
        self.get_offer = GetOffer(investments, offers, links, clock or SystemClock())
        self.get_investment = GetInvestment(investments, links)
        self.get_developer = GetDeveloper(DeveloperProfileApi(self._http), links)
        self.get_market_statistics = GetMarketStatistics(CitySalesApi(self._http), links)
        self.get_government_statistics = GetGovernmentStatistics(
            GovernmentStatisticsApi(self._http), links
        )
        self.search_developers = SearchDevelopers(DeveloperSearchApi(self._http), links)
        self.search_investments = SearchInvestments(InvestmentSearchApi(self._http), links)
        self.get_transaction_statistics = GetTransactionStatistics(
            TransactionStatisticsApi(self._http), links
        )
        self.rank_locations = RankLocations(TransactionRankingApi(self._http), links)
        self.get_building = GetBuilding(BuildingsApi(self._http), links)
        self.estimate_property_value = EstimatePropertyValue(ValuationApi(self._http))

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
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


class StopUseCases:
    """The use cases of the STOP record of the shared limiter (``limiter`` defaults to the
    shared lock), offline and without a session: they read or remove a local file and
    send nothing.

    - ``get_stop_status``: at once, without waiting for the limiter's lock; creates
      nothing.
    - ``clear_stop``: for people only, no MCP tool calls it. Waits for the limiter's lock
      as its request says; ``LockWaitTimeoutError`` (nothing removed) when the wait runs out,
      ``OSError`` when the record cannot be removed.
    """

    def __init__(self, limiter: RequestLimiter | None = None) -> None:
        record = LimiterStopRecord(limiter)
        self.get_stop_status: GetStopStatus[StopState] = GetStopStatus(record)
        self.clear_stop: ClearStop[StopState] = ClearStop(record)
