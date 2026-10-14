"""Live: ``rank_locations`` (MCP) and ``deweloperuch stats cities`` (CLI), 3 live requests.

One MCP server for the module: the ranking of cities (1 request; the second call with
another order is answered by the cache), the ranking of powiats (1 request), and one
CLI run (its own process, 1 request). Every call ends the session on a STOP or a
service error and fails on backend details in the result (``live.McpLive``). Assertions
are about structure, order and consistency, never about today's numbers.

[W] checked here: the same place counts far more transactions as a powiat than as a
city (the description says "nie porównuj liczb między poziomami"), and the city slugs
of the ranking have the format of search_locations.
"""

import re
from collections.abc import Iterator
from typing import Any

import pytest

from deweloperuch_mcp.identity import BASE_URL
from support.e2e.live import Budget, Call, McpLive, mcp_server, run_cli

pytestmark = pytest.mark.live

TOOL = "rank_locations"
RANKING_PAGE = BASE_URL + "/ceny-transakcyjne/polska/miasta"
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
POWIAT_WARSZAWA = 302
"""[P] sample api.city_powiats_waw: the primary powiat of warszawa."""
CAVEAT = "Serwis nie podaje okresu ani tego, czy ceny i metraż to średnie, czy mediany."


@pytest.fixture(scope="module")
def mcp(budget: Budget, tmp_path_factory: pytest.TempPathFactory) -> Iterator[McpLive]:
    log = tmp_path_factory.mktemp("mcp-rankings") / "server-stderr.log"
    with mcp_server(log, budget) as server:
        yield server


@pytest.fixture(scope="module")
def cities(mcp: McpLive) -> Call:
    return mcp.call_network(TOOL)


@pytest.fixture(scope="module")
def powiats(mcp: McpLive) -> Call:
    return mcp.call_network(TOOL, level="powiat")


def ranked(items: list[dict[str, Any]], key: str) -> list[Any]:
    return [item[key] for item in items]


def test_cities_by_transactions(cities: Call) -> None:
    data = cities.data

    assert cities.sent == 1
    assert (data["level"], data["sort"], data["min_transactions"]) == (
        "city",
        "transactions_desc",
        0,
    )
    assert data["returned"] == len(data["items"]) == 20
    assert data["total"] > 20 and data["truncated"] is True and data["hint"]
    assert data["ranking_url"] == RANKING_PAGE
    counts = ranked(data["items"], "transaction_count")
    assert counts == sorted(counts, reverse=True) and counts[-1] >= 1
    for item in data["items"]:
        assert SLUG.fullmatch(item["city_slug"]), item
        assert "powiat_id" not in item
        if "price_per_m2" in item:
            assert 1_000 <= item["price_per_m2"] <= 100_000, item
    assert "warszawa" in ranked(data["items"], "city_slug")


def test_the_most_expensive_cities_come_from_the_cache(mcp: McpLive, cities: Call) -> None:
    call = mcp.call(TOOL, sort="price_per_m2_desc", min_transactions=50, limit=10)
    data = call.data

    assert call.sent == 0
    assert data["total"] <= cities.data["total"]
    prices = [item["price_per_m2"] for item in data["items"] if "price_per_m2" in item]
    assert prices == sorted(prices, reverse=True)
    assert all(item["transaction_count"] >= 50 for item in data["items"])


def test_powiats_by_transactions(powiats: Call, cities: Call) -> None:
    data = powiats.data

    assert powiats.sent == 1
    assert 300 <= data["total"] <= 400  # 369 in the sample; Poland has 380 powiats
    assert "ranking_url" not in data
    counts = ranked(data["items"], "transaction_count")
    assert counts == sorted(counts, reverse=True)
    for item in data["items"]:
        assert isinstance(item["powiat_id"], int) and "city_slug" not in item
    by_id = {item["powiat_id"]: item for item in data["items"]}
    city = next(i for i in cities.data["items"] if i["city_slug"] == "warszawa")
    assert by_id[POWIAT_WARSZAWA]["transaction_count"] > 2 * city["transaction_count"]


def test_stats_cities_as_text(budget: Budget, tmp_path_factory: pytest.TempPathFactory) -> None:
    run = run_cli(
        budget, tmp_path_factory.mktemp("cli-rankings"), "stats", "cities", "--limit", "5"
    )

    assert run.code == 0, (run.code, run.stderr)
    assert run.stderr == ""
    run.readable()
    lines = run.stdout.splitlines()
    assert lines[0].startswith("Ranking miejscowości wg liczby transakcji: pokazano 5 z ")
    assert f"Ranking miast na deweloperuch.pl: {RANKING_PAGE}" in lines
    numbered = [line for line in lines if re.match(r"[1-5]\. ", line)]
    assert len(numbered) == 5
    assert lines[-1] == CAVEAT
    assert run.sent == 1
