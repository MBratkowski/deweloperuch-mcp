"""Live: ``get_building`` (the MCP server over stdio) and ``deweloperuch buildings get``
(the CLI), at most four live requests.

The building is the one of the sample api.tx_visible (``23-marca-79c-sopot``, [P
2026-10-09]): no tool finds a building's slug (the streets of the transaction search
have none, docs/discovery/endpoints.md), so the suite takes a known one. Assertions are
about structure, ranges and consistency, never about today's numbers.

[H] What the service answers for an unknown slug is not documented: the client takes a
404, or a 200 with null or with an error object, as "not found"
(api.adapters.buildings_api), and ``test_an_unknown_building_is_not_found``
finds out which one it is. A 5xx or a 400 there ends the session as a service error
(``live.unavailable_exit``), so that test comes last in this module.
"""

import json
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from deweloperuch_mcp.identity import BASE_URL
from support.e2e.live import Budget, Call, McpLive, Run, mcp_server, run_cli

pytestmark = pytest.mark.live

SLUG = "23-marca-79c-sopot"
CITY = "sopot"
PAGE = BASE_URL + "/ceny-transakcyjne/" + CITY + "/adresy/" + SLUG
UNKNOWN_BUILDING = "nieistniejacy-budynek-e2e"
LIMIT = 5
TREND_QUARTERS = 12
SIZE_BUDGET = 8_000
QUARTER = re.compile(r"\d{4}-Q[1-4]")
MARKETS = ("primary", "secondary")


@pytest.fixture(scope="module")
def mcp(budget: Budget, tmp_path_factory: pytest.TempPathFactory) -> Iterator[McpLive]:
    log = tmp_path_factory.mktemp("mcp-buildings") / "server-stderr.log"
    with mcp_server(log, budget) as server:
        yield server


@pytest.fixture(scope="module")
def building(mcp: McpLive) -> Call:
    """The building with its trend: two requests (the building, then its trend)."""
    call = mcp.call_network("get_building", building_slug=SLUG, limit=LIMIT, include_trend=True)
    assert call.sent == 2, call.sent
    return call


def day(text: str) -> date:
    return date.fromisoformat(text)


def test_the_building_with_its_units_and_their_transactions(building: Call) -> None:
    found = building.data

    assert len(building.text) <= SIZE_BUDGET
    assert (found["building_slug"], found["city_slug"]) == (SLUG, CITY)
    assert found["building_url"] == PAGE
    assert found["name"] and found["city"]
    returned, omitted, total = found["units_returned"], found["units_omitted"], found["units_total"]
    assert returned == len(found["units"]) <= LIMIT
    assert returned + omitted == total
    assert found["truncated"] is (omitted > 0)
    deeds = [deed for unit in found["units"] for deed in unit["transactions"]]
    assert deeds, "lokale bez transakcji"
    assert found["transactions_total"] >= len(deeds)
    first, last = day(found["first_transaction_date"]), day(found["last_transaction_date"])
    assert first <= last
    for unit in found["units"]:
        dates = [day(deed["date"]) for deed in unit["transactions"]]
        assert dates == sorted(dates), unit
        assert all(first <= when <= last for when in dates)
        if unit.get("area_m2") is not None:
            assert unit["area_m2"] > 0
    for deed in deeds:
        assert deed.get("price", 1) > 0
        assert deed.get("price_per_m2", 1) > 0
        assert deed.get("market", "primary") in MARKETS, deed
    newest = [max(day(d["date"]) for d in unit["transactions"]) for unit in found["units"]]
    assert newest == sorted(newest, reverse=True)
    assert newest[0] == last


def test_the_trend_around_the_building(building: Call) -> None:
    trend: dict[str, Any] = building.data["neighbourhood_trend"]

    assert trend["radius_km"] > 0
    assert trend["returned"] == len(trend["quarters"]) <= TREND_QUARTERS
    assert trend["total"] >= trend["returned"]
    assert trend["truncated"] is (trend["total"] > trend["returned"])
    periods = [quarter["period"] for quarter in trend["quarters"]]
    assert all(QUARTER.fullmatch(period) for period in periods)
    assert periods == sorted(periods) and len(set(periods)) == len(periods)
    assert all(q.get("avg_price_per_m2", 1) > 0 for q in trend["quarters"])


def test_the_same_building_again_comes_from_the_cache(building: Call, mcp: McpLive) -> None:
    again = mcp.call("get_building", building_slug=SLUG, limit=0)

    assert again.sent == 0
    summary = again.data
    assert summary["units"] == []
    assert summary["units_omitted"] == summary["units_total"] == building.data["units_total"]
    assert "neighbourhood_trend" not in summary


def test_the_cli_shows_the_building_as_json(
    budget: Budget, tmp_path_factory: pytest.TempPathFactory
) -> None:
    logs: Path = tmp_path_factory.mktemp("cli-buildings")

    run: Run = run_cli(budget, logs, "buildings", "get", SLUG, "--limit", "2", "--json")

    assert (run.code, run.stderr, run.sent) == (0, "", 1)
    run.readable()
    view = json.loads(run.stdout)
    assert (view["building_slug"], view["building_url"]) == (SLUG, PAGE)
    assert len(view["units"]) == min(2, view["units_total"])
    assert all(unit["unit_id"] > 0 and unit["name"] for unit in view["units"])
    assert view["neighbourhood_trend"] is None


def test_an_unknown_building_is_not_found(mcp: McpLive) -> None:
    """[H] (module docstring): the last test of the module."""
    call = mcp.call("get_building", building_slug=UNKNOWN_BUILDING)

    assert call.sent == 1
    assert call.error, call.text
    assert call.text.startswith(f"Nie znaleziono budynku '{UNKNOWN_BUILDING}'.")
