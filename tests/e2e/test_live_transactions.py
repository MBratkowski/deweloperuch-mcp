"""Live: ``get_transaction_statistics`` (MCP over stdio) and ``deweloperuch stats
transactions`` (CLI) on the real service. 3 live requests in file order, at most 5.

One server for the module, so a repeat comes from its cache. Assertions are about
structure, ranges and consistency, never about today's numbers. Behaviours marked [W]
in the code (the meaning of the medians and averages, the lag of the latest months, the
rule of the incomplete periods, other cities than Warsaw) are confirmed here only as far
as the data shows them.

| Test | Requests |
|---|---|
| ``test_months_of_a_city`` | 1 (fixture) |
| ``test_more_months_come_from_the_cache`` | 0 (cache) |
| ``test_the_latest_months_hold_fewer_transactions`` | 0 |
| ``test_the_incomplete_months_are_the_newest_ones`` | 0 (cache) |
| ``test_quarters_of_a_city`` | 1 (fixture) |
| ``test_the_cli_shows_another_city`` | 1 (CLI, own process) |
"""

import json
import re
import statistics
import warnings
from collections.abc import Iterator
from typing import Any

import pytest

from deweloperuch_mcp.identity import BASE_URL
from support.e2e.live import Budget, Call, McpLive, mcp_server, run_cli

pytestmark = pytest.mark.live

TOOL = "get_transaction_statistics"
CITY = "warszawa"
OTHER_CITY = "krakow"
"""[W] a city slug of search_locations works here too (only warszawa is [P])."""
PERIOD = {
    "month": re.compile(r"\d{4}-(?:0[1-9]|1[0-2])"),
    "quarter": re.compile(r"\d{4}-Q[1-4]"),
}
MONTH_FIELDS = {
    "period",
    "transactions",
    "median_price_per_m2",
    "average_price_per_m2",
    "median_area_m2",
    "median_price",
}
QUARTER_FIELDS = {"period", "transactions", "average_price_per_m2"}
FLAG = "incomplete"
"""A period's flag besides its measures: in MCP results only where it is true."""
FEW_TRANSACTIONS = "Transakcji jest za mało, by ocenić"
"""The hint of a series with too few transactions to judge its newest periods."""
PRICE_PER_M2 = (1_000, 100_000)
"""PLN per m² of a flat in a Polish city: far wider than any real median or mean."""
SIZE_BUDGET = 8_000
STATS_PAGE = BASE_URL + "/statystyki/ceny-transakcyjne/mieszkania"
"""The page ``stats_url`` points to (D12, 2026-10-13); never opened here (a D5 dump)."""


@pytest.fixture(scope="module")
def mcp(budget: Budget, tmp_path_factory: pytest.TempPathFactory) -> Iterator[McpLive]:
    log = tmp_path_factory.mktemp("mcp-transactions") / "server-stderr.log"
    with mcp_server(log, budget) as server:
        yield server


@pytest.fixture(scope="module")
def months(mcp: McpLive) -> Call:
    return mcp.call_network(TOOL, city=CITY)


@pytest.fixture(scope="module")
def quarters(mcp: McpLive) -> Call:
    return mcp.call_network(TOOL, city=CITY, granularity="quarter")


def check_counters(result: dict[str, Any], asked: int) -> None:
    """D4: total, returned and truncated agree with the periods shown; a hint when the
    result is cut or shows incomplete periods, otherwise only one about too few
    transactions."""
    assert result["returned"] == len(result["periods"]) == min(asked, result["total"])
    assert result["truncated"] is (result["returned"] < result["total"])
    if result["truncated"] or any(item.get(FLAG) for item in result["periods"]):
        assert "hint" in result
    else:
        assert result.get("hint", FEW_TRANSACTIONS).startswith(FEW_TRANSACTIONS), result
    assert result["available_from"] <= result["periods"][0]["period"]


def check_incomplete(result: dict[str, Any], *, compact: bool) -> list[str]:
    """[W] the incomplete periods (models.transaction_series, INCOMPLETE_SHARE): only the
    newest ones, all after ``last_complete_period`` and every shown one after it, each
    named by the hint. MCP (``compact``) has the flag only where it is true, the CLI's
    ``--json`` on every period. The flagged labels, oldest first."""
    periods = result["periods"]
    labels = [item["period"] for item in periods]
    if compact:
        assert all(item.get(FLAG, True) is True for item in periods), periods
    else:
        assert all(isinstance(item[FLAG], bool) for item in periods), periods
    flagged = [item["period"] for item in periods if item.get(FLAG)]
    assert flagged == labels[len(labels) - len(flagged) :], "niepełne okresy nie są ostatnie"
    last = result.get("last_complete_period")
    if last is not None:
        assert all(label > last for label in flagged), (last, flagged)
        if last in labels:
            assert flagged == labels[labels.index(last) + 1 :], (last, flagged)
    for label in flagged:
        assert label in result["hint"], (label, result["hint"])
    if FEW_TRANSACTIONS in (result.get("hint") or ""):
        assert (flagged, last) == ([], None), "za mało transakcji, a okresy ocenione"
    return flagged


def check_periods(periods: list[dict[str, Any]], granularity: str) -> None:
    """Labels in order; prices in range only when present; a period without transactions
    has no price nor area ([P 2026-10-13]: the service sends them as 0, e.g. Warsaw
    2026-05 and 2026-06), as missing fields (MCP) or ``null`` (the CLI's ``--json``)."""
    labels = [item["period"] for item in periods]
    assert all(PERIOD[granularity].fullmatch(label) for label in labels), labels
    assert labels == sorted(set(labels)), "okresy nie rosną albo się powtarzają"
    for item in periods:
        assert isinstance(item["transactions"], int) and item["transactions"] >= 0
        measures = {
            key: value
            for key, value in item.items()
            if key not in ("period", "transactions", FLAG) and value is not None
        }
        assert all(value > 0 for value in measures.values()), (item["period"], measures)
        if item["transactions"] == 0:
            assert measures == {}, (item["period"], measures)
        low, high = PRICE_PER_M2
        for key in ("median_price_per_m2", "average_price_per_m2"):
            if item.get(key) is not None:
                assert low <= item[key] <= high, (item["period"], key, item[key])


def test_months_of_a_city(months: Call) -> None:
    result = months.data

    assert months.sent == 1
    assert (result["city_slug"], result["granularity"]) == (CITY, "month")
    check_counters(result, 12)
    check_periods(result["periods"], "month")
    check_incomplete(result, compact=True)
    assert {key for item in result["periods"] for key in item} <= MONTH_FIELDS | {FLAG}
    full = [item for item in result["periods"] if set(item) == MONTH_FIELDS]
    assert full, "żaden pełny miesiąc nie ma median i średnich"
    for item in full:
        assert 10 <= item["median_area_m2"] <= 200
        assert item["median_price"] > item["median_price_per_m2"]
    # Five years of Warsaw's months, about a thousand transactions each: the month right
    # before the incomplete ones is judged, and usual.
    assert PERIOD["month"].fullmatch(result.get("last_complete_period", "")), result
    assert result["note"].startswith("Ostatnie miesiące są niepełne")
    assert result["stats_url"] == f"{STATS_PAGE}/{CITY}"
    assert len(months.text) < SIZE_BUDGET


def test_more_months_come_from_the_cache(mcp: McpLive, months: Call) -> None:
    """Cache: the same request as the fixture's, cut differently; the incomplete periods
    are judged on the whole series, so the flags do not depend on the cut."""
    more = mcp.call(TOOL, city=CITY, periods=60)

    assert more.sent == 0
    result = more.data
    check_counters(result, 60)
    assert result["periods"][-len(months.data["periods"]) :] == months.data["periods"]
    assert result["last_complete_period"] == months.data["last_complete_period"]


def test_the_latest_months_hold_fewer_transactions(mcp: McpLive, months: Call) -> None:
    """[P 2026-10-09] the latest months have few transactions (the RCN lag the note
    states). A warning, not a failure, if the data no longer shows it: the note may then
    need another look."""
    every = mcp.call(TOOL, city=CITY, periods=60).data["periods"]
    counts = [item["transactions"] for item in every]
    typical = statistics.median(counts)

    if not counts[-1] < typical:
        warnings.warn(
            f"ostatni miesiąc ({every[-1]['period']}) ma {counts[-1]} transakcji, mediana "
            f"{typical}: opóźnienie RCN nie jest już widoczne w danych",
            UserWarning,
            stacklevel=1,
        )


def test_the_incomplete_months_are_the_newest_ones(mcp: McpLive, months: Call) -> None:
    """[W] the rule of the incomplete periods on today's data (the revision horizon is
    open, T46): over 60 months the flagged ones are the newest, after the last complete
    one, each named by the hint. A warning, not a failure, when none is flagged: the
    register may have caught up, or the rule may need another look."""
    more = mcp.call(TOOL, city=CITY, periods=60)

    assert more.sent == 0
    flagged = check_incomplete(more.data, compact=True)
    if not flagged:
        warnings.warn(
            "żaden z ostatnich 60 miesięcy nie jest niepełny (ostatni pełny: "
            f"{more.data.get('last_complete_period')}): opóźnienie RCN nie jest już widoczne",
            UserWarning,
            stacklevel=1,
        )


def test_quarters_of_a_city(quarters: Call, months: Call) -> None:
    result = quarters.data

    assert quarters.sent == 1
    assert (result["city_slug"], result["granularity"]) == (CITY, "quarter")
    check_counters(result, 12)
    check_periods(result["periods"], "quarter")
    check_incomplete(result, compact=True)
    assert {key for item in result["periods"] for key in item} <= QUARTER_FIELDS | {FLAG}
    assert result["note"].startswith("Ostatnie kwartały są niepełne")
    assert result["stats_url"] == f"{STATS_PAGE}/{CITY}"
    # [W] the quarters reach further back than the months (2017 vs 2021 in the samples).
    assert result["available_from"][:4] <= months.data["available_from"][:4]


def test_the_cli_shows_another_city(
    budget: Budget, tmp_path_factory: pytest.TempPathFactory
) -> None:
    logs = tmp_path_factory.mktemp("cli-transactions")

    run = run_cli(budget, logs, "stats", "transactions", OTHER_CITY, "--periods", "3", "--json")

    assert run.code == 0, (run.code, run.stderr)
    assert run.stderr == ""
    run.readable()
    assert run.sent == 1
    shown = json.loads(run.stdout)
    assert (shown["city_slug"], shown["granularity"], shown["returned"]) == (OTHER_CITY, "month", 3)
    check_periods(shown["periods"], "month")
    check_incomplete(shown, compact=False)
    assert {"average_area_m2", "average_price"} <= set(shown["periods"][-1])
    assert shown["stats_url"] == f"{STATS_PAGE}/{OTHER_CITY}"
