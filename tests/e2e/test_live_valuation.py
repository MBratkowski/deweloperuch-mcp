"""Live: ``estimate_property_value`` (the MCP server over stdio) and ``deweloperuch
valuation estimate`` (the CLI), at most 5 live requests:

- ``search_locations`` for the coordinates of a street (2: cities, districts and streets),
  the way a model fills the gap of T8 (no geocoding of an address);
- one valuation of the MCP server at those coordinates;
- one valuation of the MCP server in Cisna, where the service had 2 transactions from its
  widest radius [P 2026-10-15] (an estimate of low confidence);
- one valuation of the CLI at the point of the sample ``api.standalone_val`` (its own
  process, so no cache is shared with the server).

Assertions are about structure, ranges and consistency, never about today's numbers.
Behaviours marked [W] follow from the code and the discovery docs; the first live run
confirms them.
"""

import json
import warnings
from collections.abc import Iterator
from typing import Any

import pytest

from support.e2e.live import Budget, Call, McpLive, mcp_server, run_cli

pytestmark = pytest.mark.live

STREET_QUERY = "mokot"
"""Finds the street Mokotów in Warszawa with its lat and lng ([P 2026-10-09], sample
api.location_search, the same query and limit as search_locations sends)."""
AREA = 50
SAMPLE_POINT = ("--lat", "52.2297", "--lng", "21.0122", "--area", "50")
"""The point and area of the sample api.standalone_val [P 2026-10-09]."""
CISNA = dict(lat=49.2167, lng=22.3333, area_m2=AREA)
"""The point and area of tests/fixtures/api/standalone_val_cisna_20261015.json: 2
transactions, radiusKm 1 at radiusCeilingM 1000 [P 2026-10-15]."""
MIN_RELIABLE_COMPARABLES = 5
"""[W] deweloperuch_mcp.models.valuation: fewer transactions make low confidence."""
POLAND_LAT, POLAND_LNG = (49.0, 54.9), (14.1, 24.2)
MARKETS = ("primary", "secondary")
"""[P] docs/discovery/entities.md, marketType: pierwotny, wtorny."""
SIZE_DEFAULT = 3_500
RESULT = (
    "lat",
    "lng",
    "area_m2",
    "estimated_value",
    "comparables_total",
    "comparables_returned",
    "comparables_omitted",
    "truncated",
    "comparables",
)
"""Fields every valuation has; the others (price_per_m2, radius_m, period_months, stats,
hint) only when the service gave them."""


@pytest.fixture(scope="module")
def mcp(budget: Budget, tmp_path_factory: pytest.TempPathFactory) -> Iterator[McpLive]:
    log = tmp_path_factory.mktemp("mcp-valuation") / "server-stderr.log"
    with mcp_server(log, budget) as server:
        yield server


@pytest.fixture(scope="module")
def street(mcp: McpLive) -> dict[str, Any]:
    found = mcp.call_network("search_locations", query=STREET_QUERY)
    streets = [
        item
        for item in found.data["items"]
        if item["kind"] == "street" and "lat" in item and "lng" in item
    ]
    assert streets, f"brak ulicy ze współrzędnymi dla {STREET_QUERY!r}: {found.data}"
    chosen: dict[str, Any] = streets[0]
    return chosen


@pytest.fixture(scope="module")
def valuation(mcp: McpLive, street: dict[str, Any]) -> Call:
    return mcp.call_network(
        "estimate_property_value", lat=street["lat"], lng=street["lng"], area_m2=AREA
    )


def counted(result: dict[str, Any]) -> int:
    """The transactions an estimate rests on: the count of stats, else (none or 0) every
    comparable transaction, as Valuation.counted_comparables counts them."""
    count = (result.get("stats") or {}).get("count")
    return int(count) if count else int(result["comparables_total"])


def check_confidence(result: dict[str, Any]) -> None:
    """[W] low_confidence (models.valuation): an estimate from fewer than 5 transactions says
    so, and its hint names how many (or that the service named none); any other estimate
    says it is not of low confidence and its hint has no word of it; no estimate says
    nothing."""
    if result["estimated_value"] is None:
        assert result.get("low_confidence") is None, result
        return
    count, hint = counted(result), result.get("hint") or ""
    if count < MIN_RELIABLE_COMPARABLES:
        assert result["low_confidence"] is True, result
        transactions = "transakcji" if count == 1 else "transakcjach"
        named = "nie podał transakcji" if count == 0 else f"na {count} {transactions}"
        assert named in hint, hint
    else:
        assert result["low_confidence"] is False, result
        assert "wiarygodności" not in hint, hint
    # [W] a one-way guard of the ceiling's meaning: the widest radius is said only of a
    # radius at the ceiling, 1000 m in all 3 captures [P 2026-10-09, P 2026-10-15]. A lower
    # ceiling would go unnoticed; the result does not show it.
    if "największego, jaki serwis" in hint:
        assert result["radius_m"] >= 1000, result


def check_valuation(result: dict[str, Any], limit: int) -> None:
    """Structure, ranges and consistency of one valuation (MCP or the CLI's view)."""
    for name in ("estimated_value", "comparables_total", "comparables_omitted", "comparables"):
        assert name in result, (name, result)
    comparables = result["comparables"]
    assert len(comparables) <= limit
    assert result["comparables_total"] == len(comparables) + result["comparables_omitted"]
    if result["estimated_value"] is not None:
        assert result["estimated_value"] > 0 and result["price_per_m2"] > 0
        # [W] both samples: the value is the price per m² times the area, rounded.
        expected = result["price_per_m2"] * result["area_m2"]
        assert abs(result["estimated_value"] - expected) <= result["area_m2"]
    else:
        assert result["hint"]
    if result.get("radius_m") is not None:
        assert result["radius_m"] > 0
    if result.get("period_months") is not None:
        assert result["period_months"] > 0
    distances = [item["distance_m"] for item in comparables if item.get("distance_m") is not None]
    assert distances == sorted(distances), "najbliższe transakcje nie są pierwsze"
    for item in comparables:
        if item.get("market") is not None:
            assert item["market"] in MARKETS, item
        if None not in (item.get("price"), item.get("area_m2"), item.get("price_per_m2")):
            # [P] both samples: the price per m² is the price over the area, rounded.
            assert item["price_per_m2"] == pytest.approx(item["price"] / item["area_m2"], abs=1)
    check_confidence(result)


def test_search_locations_gives_the_coordinates_of_a_street(street: dict[str, Any]) -> None:
    assert POLAND_LAT[0] <= street["lat"] <= POLAND_LAT[1]
    assert POLAND_LNG[0] <= street["lng"] <= POLAND_LNG[1]


def test_a_valuation_at_the_coordinates_of_a_street(valuation: Call) -> None:
    result = valuation.data

    assert valuation.sent == 1
    assert [name for name in result if name in RESULT] == list(RESULT)
    assert result["comparables_returned"] == len(result["comparables"])
    assert result["truncated"] is (result["comparables_omitted"] > 0)
    check_valuation(result, limit=10)
    assert len(valuation.text) <= SIZE_DEFAULT


def test_a_valuation_from_few_transactions_is_of_low_confidence(mcp: McpLive) -> None:
    """Cisna: while the service has fewer than 5 transactions there, the result says
    low_confidence and the hint names their number (``check_confidence``); when it has
    more, the scenario is only warned about."""
    call = mcp.call_network("estimate_property_value", **CISNA)
    result = call.data

    assert call.sent == 1
    check_valuation(result, limit=10)
    if not result.get("low_confidence"):
        warnings.warn(
            f"Cisna nie jest już wyceną o niskiej wiarygodności: {counted(result)} transakcji, "
            f"promień {result.get('radius_m')} m",
            stacklevel=1,
        )


def test_a_point_outside_poland_sends_nothing(mcp: McpLive) -> None:
    call = mcp.call("estimate_property_value", lat=60.0, lng=21.0, area_m2=AREA)

    assert call.error and call.sent == 0
    assert "lat" in call.text


def test_the_cli_valuation_as_json(
    budget: Budget, tmp_path_factory: pytest.TempPathFactory
) -> None:
    logs = tmp_path_factory.mktemp("cli-valuation")

    run = run_cli(budget, logs, "valuation", "estimate", *SAMPLE_POINT, "--limit", "3", "--json")

    assert run.code == 0, (run.code, run.stderr)
    assert run.sent == 1
    run.readable()
    shown = json.loads(run.stdout)
    assert (shown["lat"], shown["lng"], shown["area_m2"]) == (52.2297, 21.0122, 50)
    assert {"low_confidence", "hint"} <= set(shown)
    # Warsaw centre (9 transactions from 200 m [P 2026-10-09]): with 5 or more,
    # low_confidence is false (check_confidence).
    check_valuation(shown, limit=3)
