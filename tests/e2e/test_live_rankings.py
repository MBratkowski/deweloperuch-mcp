"""Live: ``rank_locations`` (MCP) and ``deweloperuch stats cities`` (CLI), 4 live requests.

One MCP server for the module: the ranking of cities (1 request; the calls with the
other orders are answered by the cache), the ranking of powiats (1 request; the other
markets and the price order from the cache too), the ranking of cities by an indicator
(1 request; the second indicator from the cache), a refused combination (no request) and
one CLI run (its own process, 1 request). Every call ends the session on a STOP or a
service error and fails on backend details in the result (``live.McpLive``). Assertions
are about structure, order and consistency, never about today's numbers.

[W] checked here: the city slugs of the ranking have the format of search_locations, the
price orders' default threshold (20 transactions, ``PRICE_ORDER_MIN_TRANSACTIONS``) keeps
the cheapest place from being one of a handful of transactions or one without a price (0
PLN/m², live on 2026-10-15), and the packaged table still names every powiat and city the
service ranks (a powiat named ``powiat {id}`` or a city named by its slug means the table
is out of date).
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
FIRST_DAY = re.compile(r"(\d{4})-(\d{2})-01")
MONTH = re.compile(r"(\d{4})-(\d{2})")
QUARTER = re.compile(r"\d{4}-Q[1-4]")
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
    return mcp.call_network(TOOL, level="powiat", limit=100)


@pytest.fixture(scope="module")
def unemployment(mcp: McpLive) -> Call:
    return mcp.call_network(TOOL, indicator="unemployment_rate", limit=100)


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
    assert "market" not in data and "period_start" not in data
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


def test_the_cheapest_cities_skip_small_places_by_default(mcp: McpLive, cities: Call) -> None:
    call = mcp.call(TOOL, sort="price_per_m2_asc")
    data = call.data

    assert call.sent == 0
    assert data["min_transactions"] == 20
    assert 0 < data["total"] < cities.data["total"]
    first = data["items"][0]
    assert first.get("price_per_m2", 0) > 0 and first["transaction_count"] >= 20, first
    assert all(item["transaction_count"] >= 20 for item in data["items"])
    prices = [item["price_per_m2"] for item in data["items"] if "price_per_m2" in item]
    assert prices == sorted(prices)
    assert "min_transactions=0" in data["hint"]


def months_between(start: str, end: str) -> int:
    first, last = FIRST_DAY.fullmatch(start), MONTH.fullmatch(end)
    assert first and last, (start, end)
    return (int(last[1]) - int(first[1])) * 12 + int(last[2]) - int(first[2]) + 1


def test_powiats_by_transactions_on_the_secondary_market(powiats: Call) -> None:
    """[P 2026-11-01] 380 powiats over 12 months; the secondary market by default."""
    data = powiats.data

    assert powiats.sent == 1
    assert (data["level"], data["sort"], data["market"]) == (
        "powiat",
        "transactions_desc",
        "secondary",
    )
    assert months_between(data["period_start"], data["period_end"]) == 12
    assert 300 <= data["total"] <= 400
    assert data["returned"] == 100 and data["truncated"] is True
    assert "ranking_url" not in data
    counts = ranked(data["items"], "transaction_count")
    assert counts == sorted(counts, reverse=True) and counts[-1] >= 1
    for item in data["items"]:
        assert isinstance(item["powiat_id"], int) and "city_slug" not in item
        assert item["name"].startswith("powiat ")
        assert item["name"] != f"powiat {item['powiat_id']}", "tabela nazw jest nieaktualna"
    by_id = {item["powiat_id"]: item for item in data["items"]}
    assert by_id[POWIAT_WARSZAWA]["name"] == "powiat Warszawa"


@pytest.mark.parametrize("market", ["primary", "all"])
def test_the_other_markets_come_from_the_cache(mcp: McpLive, powiats: Call, market: str) -> None:
    """A powiat without figures for the market is left out and counted in the hint, never
    shown with 0 transactions."""
    call = mcp.call(TOOL, level="powiat", market=market, limit=100)
    data = call.data

    assert call.sent == 0
    assert data["market"] == market
    assert (data["period_start"], data["period_end"]) == (
        powiats.data["period_start"],
        powiats.data["period_end"],
    )
    assert 200 <= data["total"] <= 400
    assert min(ranked(data["items"], "transaction_count")) >= 1
    if f"(market={market})" in data.get("hint", ""):
        assert "Pominięto powiaty" in data["hint"]


def test_the_cheapest_powiats_come_from_the_cache(mcp: McpLive, powiats: Call) -> None:
    """The default threshold applies to powiats too; the hint names it only when it left a
    powiat out."""
    call = mcp.call(TOOL, level="powiat", sort="price_per_m2_asc")
    data = call.data

    assert call.sent == 0
    assert data["min_transactions"] == 20
    assert 0 < data["total"] <= powiats.data["total"]
    assert all(item["transaction_count"] >= 20 for item in data["items"])
    prices = [item["price_per_m2"] for item in data["items"] if "price_per_m2" in item]
    assert prices == sorted(prices)
    left_out = data["total"] < powiats.data["total"]
    assert ("min_transactions=0" in data.get("hint", "")) is left_out


def test_cities_by_the_unemployment_rate(unemployment: Call) -> None:
    """66 cities with powiat rights [P 2026-11-01], each linked to its government
    statistics at the unemployment section, named from the packaged table."""
    data = unemployment.data

    assert unemployment.sent == 1
    assert (data["level"], data["sort"], data["indicator"], data["unit"]) == (
        "city",
        "value_desc",
        "unemployment_rate",
        "%",
    )
    assert MONTH.fullmatch(data["period"]), data["period"]
    assert 60 <= data["total"] == data["returned"] <= 70
    assert "min_transactions" not in data and "ranking_url" not in data
    values = ranked(data["items"], "value")
    assert values == sorted(values, reverse=True)
    assert all(0 <= value <= 100 for value in values)
    for item in data["items"]:
        slug = item["city_slug"]
        assert SLUG.fullmatch(slug), item
        assert item["stats_url"] == f"{BASE_URL}/statystyki/{slug}/dane-rzadowe#gus-bezrobocie"
        assert item["name"] != slug, "tabela nazw jest nieaktualna"
        assert "transaction_count" not in item
    assert "warszawa" in ranked(data["items"], "city_slug")


def test_nbp_prices_rank_only_the_cities_that_have_them(mcp: McpLive, unemployment: Call) -> None:
    """[P 2026-11-01] NBP prices for 17 of the 66 cities: the others are left out and
    counted, never ranked as 0. From the cache: one answer holds every indicator."""
    call = mcp.call(TOOL, indicator="nbp_price_per_m2", sort="value_asc", limit=100)
    data = call.data

    assert call.sent == 0
    assert (data["unit"], data["sort"]) == ("PLN/m²", "value_asc")
    assert QUARTER.fullmatch(data["period"]), data["period"]
    assert 10 <= data["total"] < unemployment.data["total"]
    assert "Pominięto miasta, dla których serwis nie podaje tego wskaźnika" in data["hint"]
    values = ranked(data["items"], "value")
    assert values == sorted(values) and values[0] >= 1_000
    assert all(item["stats_url"].endswith("/dane-rzadowe#nbp") for item in data["items"])


def test_a_market_of_cities_is_refused_without_a_request(mcp: McpLive) -> None:
    call = mcp.call(TOOL, market="primary")

    assert call.sent == 0
    assert call.error
    assert "market działa tylko z level=powiat" in call.text


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
