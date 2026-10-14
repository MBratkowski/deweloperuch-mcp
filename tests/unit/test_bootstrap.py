"""Tests of ``deweloperuch_mcp.bootstrap``."""

from pathlib import Path

import pytest
import respx

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.api.http import transport
from deweloperuch_mcp.errors import (
    LimiterWaitError,
    RateLimitedError,
    ServiceBlockedError,
    SessionClosedError,
)
from deweloperuch_mcp.throttle import (
    CLEAR_NOTICE_AFTER,
    CLEAR_WAIT_LIMIT,
    LOCK_FILENAME,
    RequestLimiter,
)
from deweloperuch_mcp.usecases.clear_stop import ClearStopRequest
from support.providers import operations
from support.providers.routes.investments import (
    INVESTMENT,
    investment_routes,
)
from support.providers.routes.locations import location_routes


def test_session_closes_its_connections(limiter: RequestLimiter) -> None:
    with bootstrap.Session(limiter=limiter) as opened:
        assert opened.closed is False

    assert opened.closed is True


def test_a_stop_in_one_service_stops_every_service_of_the_session(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """CLAUDE.md: after 401/403/429/challenge stop the series and report; no retries."""
    blocked = service.route(method="GET", path__startswith="/ceny-ofertowe/").respond(403)
    investment_routes(service)
    location_routes(service)

    with pytest.raises(ServiceBlockedError):
        operations.search_offers(session, "warszawa")
    with pytest.raises(ServiceBlockedError, match="jest już przerwana"):
        operations.get_investment(session, "smolna")
    with pytest.raises(ServiceBlockedError, match="jest już przerwana"):
        operations.search_locations(session, "krak")

    assert blocked.call_count == 1
    assert service.calls.call_count == 1


def test_a_429_keeps_its_pause_in_the_repeated_error(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    service.get(INVESTMENT).respond(429, headers={"Retry-After": "300"})

    with pytest.raises(RateLimitedError):
        operations.get_investment(session, "smolna")
    with pytest.raises(RateLimitedError) as again:
        operations.get_offer(session, 2377, "smolna")

    assert again.value.pause_seconds == 300
    assert service.calls.call_count == 1


def test_a_new_session_stops_during_the_pause_of_the_old_one(
    session: bootstrap.Session, limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    """The 429 is recorded for every process, so a new one stops while the pause lasts;
    the pause is in the shared limiter too, so it waits even without the record."""
    service.get(INVESTMENT).respond(429, headers={"Retry-After": "300"})
    with pytest.raises(RateLimitedError):
        operations.get_investment(session, "smolna")
    transport.HttpClient.testing_only_reset_stop()  # what a new process starts with

    with bootstrap.Session(limiter=limiter) as fresh:
        with pytest.raises(RateLimitedError, match="wcześniejszym STOP"):
            operations.get_investment(fresh, "smolna")
        transport.HttpClient.testing_only_reset_stop()
        bootstrap.StopUseCases(limiter).clear_stop.execute(
            ClearStopRequest.parse(wait_limit=CLEAR_WAIT_LIMIT, notice_after=CLEAR_NOTICE_AFTER)
        )
        with pytest.raises(LimiterWaitError):
            operations.get_investment(fresh, "smolna")

    assert service.calls.call_count == 1


def test_a_stop_in_one_session_stops_every_session_of_the_process(
    session: bootstrap.Session, limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    """The latch is per process: "jest już przerwana" holds for a new session."""
    service.get(INVESTMENT).respond(403)
    cities, suggestions = location_routes(service)
    with pytest.raises(ServiceBlockedError):
        operations.get_investment(session, "smolna")

    with (
        bootstrap.Session(limiter=limiter) as second,
        pytest.raises(ServiceBlockedError, match="jest już przerwana"),
    ):
        operations.search_locations(second, "krak")

    assert (cities.call_count, suggestions.call_count) == (0, 0)


def test_a_closed_session_sends_nothing(
    limiter: RequestLimiter, service: respx.MockRouter, tmp_path: Path
) -> None:
    investment_routes(service)
    opened = bootstrap.Session(limiter=limiter)
    opened.close()

    with pytest.raises(SessionClosedError, match="Session"):
        operations.get_investment(opened, "smolna")

    assert service.calls.call_count == 0
    assert not (tmp_path / LOCK_FILENAME).exists()  # no limiter slot was taken
