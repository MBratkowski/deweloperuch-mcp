"""Tests of ``deweloperuch_mcp.consumers.mcp.support.calls``."""

import logging
import re
from collections.abc import Callable
from typing import Any

import httpx
import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult
from pydantic import BaseModel

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.consumers.mcp.support import calls
from deweloperuch_mcp.usecases.search_locations import SearchLocations
from support.builders.offers import INJECTED, offer_without_history
from support.checks.leaks import LEAKS
from support.providers.mcp import TOOLS, Sessions, call, text, with_client
from support.providers.routes.government_statistics import STATS_PATH, stats_routes
from support.providers.routes.investments import INVESTMENT, investment_routes
from support.providers.routes.locations import location_routes
from support.providers.routes.offers import offers_route
from support.providers.rsc import STATS_POLSKA, raw
from support.providers.samples import rsc_payload

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def no_page_data(router: respx.MockRouter) -> None:
    router.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
        200, content=rsc_payload({"other": {"text": INJECTED}})
    )


ERRORS: dict[str, tuple[str, dict[str, Any], Callable[[respx.MockRouter], Any]]] = {
    "500 with a body": (
        "get_investment",
        {"investment_slug": "smolna"},
        lambda r: r.get(INVESTMENT).respond(500, text=INJECTED),
    ),
    "404 with a body": (
        "get_investment",
        {"investment_slug": "smolna"},
        lambda r: r.get(INVESTMENT).respond(404, text=INJECTED),
    ),
    "redirect": (
        "get_investment",
        {"investment_slug": "smolna"},
        lambda r: r.get(INVESTMENT).respond(301, headers={"Location": "/api/elsewhere"}),
    ),
    "html instead of json": (
        "get_investment",
        {"investment_slug": "smolna"},
        lambda r: r.get(INVESTMENT).respond(
            200, text=f"<html>{INJECTED}</html>", headers={"Content-Type": "text/html"}
        ),
    ),
    "broken json": (
        "get_investment",
        {"investment_slug": "smolna"},
        lambda r: r.get(INVESTMENT).respond(
            200, content=INJECTED.encode(), headers={"Content-Type": "application/json"}
        ),
    ),
    "another shape": (
        "get_investment",
        {"investment_slug": "smolna"},
        lambda r: r.get(INVESTMENT).respond(200, json={INJECTED: True}),
    ),
    "network": (
        "get_investment",
        {"investment_slug": "smolna"},
        lambda r: r.get(INVESTMENT).mock(side_effect=httpx.ConnectError(INJECTED)),
    ),
    "page without the data": ("search_offers", {"city": "warszawa"}, no_page_data),
    "statistics page without the data": (
        "get_government_statistics",
        {"location": "warszawa", "dataset": "wages"},
        lambda r: r.get(path=STATS_PATH + "warszawa").respond(
            200, content=rsc_payload({"other": {"text": INJECTED}})
        ),
    ),
    "statistics page of another location": (
        "get_government_statistics",
        {"location": "krakow", "dataset": "wages"},
        lambda r: r.get(path=STATS_PATH + "krakow").respond(200, content=raw(STATS_POLSKA)),
    ),
    "offer without history": (
        "get_offer",
        {"offer_id": 2377, "investment_slug": "smolna"},
        offer_without_history,
    ),
}


VALID_ARGUMENTS: dict[str, dict[str, Any]] = {
    "search_locations": {"query": "krak"},
    "search_offers": {"city": "warszawa"},
    "get_offer": {"offer_id": 2377, "investment_slug": "smolna"},
    "get_investment": {"investment_slug": "smolna"},
    "get_developer": {"developer_slug": "atal"},
    "get_market_statistics": {"city": "sopot"},
    "get_government_statistics": {"location": "warszawa", "dataset": "wages"},
    "search_developers": {"name": "atal"},
    "search_investments": {"city": "sopot"},
    "get_transaction_statistics": {"city": "warszawa"},
    "rank_locations": {},
    "get_building": {"building_slug": "23-marca-79c-sopot"},
    "estimate_property_value": {"lat": 52.2297, "lng": 21.0122, "area_m2": 50},
}


def test_a_crash_with_a_validation_error_as_its_cause_stays_a_crash(
    server: MCPServer[bootstrap.Session], caplog: pytest.LogCaptureFixture
) -> None:
    """A tool whose result fails its output schema: the SDK's generic message and its
    crash log (with the traceback), not a rewritten argument error."""

    class Count(BaseModel):
        n: int

    def broken() -> Count:
        return {"n": "abc"}  # type: ignore[return-value]

    server.add_tool(broken)
    caplog.set_level(logging.INFO)

    result = call(server, "broken")

    assert result.is_error is True
    assert text(result) == "Error executing tool broken"
    crashes = [r for r in caplog.records if r.name.startswith("mcp.server")]
    assert [(r.levelno, r.getMessage()) for r in crashes] == [
        (logging.ERROR, "Tool 'broken' raised an unexpected exception")
    ]
    assert crashes[0].exc_info is not None


def test_other_tool_errors_pass_unchanged(server: MCPServer[bootstrap.Session]) -> None:
    result = call(server, "no_such_tool")

    assert result.is_error is True
    assert text(result) == "Unknown tool: no_such_tool"


@pytest.mark.parametrize("case", ERRORS)
def test_error_results_carry_no_backend_details(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    caplog: pytest.LogCaptureFixture,
    case: str,
) -> None:
    """D3 and CLAUDE.md: no paths, prop names or text of the service's answer reach the
    model; the details go to the server log only."""
    caplog.set_level(logging.INFO, logger=calls.LOGGER_NAME)
    tool, arguments, answer = ERRORS[case]
    answer(service)

    result = call(server, tool, **arguments)

    assert result.is_error is True
    assert not LEAKS.search(text(result)), text(result)
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "Szczegóły: " in logged
    assert re.search(r"/api|/ceny-|/statystyki", logged)


def test_terminal_sequences_from_the_service_are_escaped_in_the_log(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The log is stderr, often a terminal: the detail is escaped there (``printable``)."""
    caplog.set_level(logging.INFO, logger=calls.LOGGER_NAME)
    service.get(INVESTMENT).respond(500, text="\x1b]0;PWNED\x07\x1b[31mred")

    result = call(server, "get_investment", investment_slug="smolna")

    assert result.is_error is True
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "\\x1b]0;PWNED\\x07\\x1b[31mred" in logged
    assert "\x1b" not in logged and "\x07" not in logged


def test_a_stop_ends_the_series_for_every_tool(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """CLAUDE.md: after 401/403/429/challenge stop and report; the STOP of S1a is sticky."""
    caplog.set_level(logging.INFO, logger=calls.LOGGER_NAME)
    service.get(INVESTMENT).respond(403)
    cities, suggestions = location_routes(service)

    async def two_calls(client: Client) -> tuple[CallToolResult, CallToolResult]:
        first = await client.call_tool("get_investment", {"investment_slug": "smolna"})
        second = await client.call_tool("search_locations", {"query": "krak"})
        return first, second

    first, second = with_client(server, two_calls)

    assert first.is_error is True and text(first).startswith("STOP: ")
    assert second.is_error is True and "jest już przerwana" in text(second)
    assert service.calls.call_count == 1
    assert (cities.call_count, suggestions.call_count) == (0, 0)
    stops = [record for record in caplog.records if "STOP" in record.getMessage()]
    assert stops and all(record.levelno == logging.WARNING for record in stops)


@pytest.mark.parametrize("tool", TOOLS)
def test_a_stop_recorded_by_another_process_ends_the_series_without_a_request(
    server: MCPServer[bootstrap.Session],
    sessions: Sessions,
    service: respx.MockRouter,
    caplog: pytest.LogCaptureFixture,
    tool: str,
) -> None:
    """A STOP of the CLI or recon (the record of the shared limiter) stops every tool; the
    model learns what stopped the series, never when, from which program or how to lift it."""
    caplog.set_level(logging.INFO, logger=calls.LOGGER_NAME)
    with sessions.limiter.slot() as slot:
        slot.stop(403, "odmowa dostępu", source="probe")
    location_routes(service)
    offers_route(service)
    investment_routes(service)
    stats_routes(service)

    result = call(server, tool, **VALID_ARGUMENTS[tool])

    assert result.is_error is True
    message = text(result)
    assert message == (
        "STOP: seria zapytań do deweloperuch.pl jest wstrzymana po wcześniejszym STOP "
        "(HTTP 403, odmowa dostępu). Zapytanie nie zostało wysłane. Przerwij, niczego nie "
        "ponawiaj i zgłoś to użytkownikowi."
    )
    assert not LEAKS.search(message)
    assert service.calls.call_count == 0
    logged = [record.getMessage() for record in caplog.records]
    assert any("Szczegóły: zapis STOP: HTTP 403" in line and "probe" in line for line in logged)


def test_an_unexpected_error_hides_its_details(
    server: MCPServer[bootstrap.Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    def crash(*args: object, **kwargs: object) -> None:
        raise RuntimeError("internal detail /secret/path")

    monkeypatch.setattr(SearchLocations, "execute", crash)

    result = call(server, "search_locations", query="krak")

    assert result.is_error is True
    assert text(result) == calls.UNEXPECTED_ERROR
    assert "secret" not in text(result)
