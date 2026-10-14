"""Live: ``search_investments`` of the installed ``deweloperuch-mcp`` over stdio.

One server for the module. Three live requests planned, four at most: the investments
of Sopot (1), the same list filtered and ordered (0, from the server's cache; 1 if the
reply was not cacheable), a search by name (1) and ``get_investment`` of its first
match (1). Assertions are about structure and consistency, never about today's numbers.

What the adapter takes as [W] (api/investment_search.py) is
checked here:

- ``/api/investments`` honours a ``limit`` other than the UI's 5, and its ``total``
  counts every match (``test_a_name_honours_the_limit_and_counts_every_match``);
- its ``offerCount`` is the number of active offers
  (``test_the_offer_count_of_a_match_is_its_active_offers``);
- an average of 0 in the city's list means no active offers
  (``test_a_city_lists_its_investments``: an average only with active offers).

Not checked (it could end the run as "service unavailable"): what the city's list
answers for an unknown city.
"""

import warnings
from collections.abc import Iterator
from typing import Any

import pytest

from deweloperuch_mcp.consumers.mcp.tools.search_investments_tool import MAX_INVESTMENTS_LIMIT
from deweloperuch_mcp.identity import BASE_URL
from deweloperuch_mcp.models.investment_summary import InvestmentName
from support.e2e.live import Budget, Call, McpLive, mcp_server, page_url

pytestmark = pytest.mark.live

TOOL = "search_investments"
CITY = "sopot"
"""A city with few investments: two on 2026-10-09 (sample api.map_investments_sopot)."""
NAME = "nowy"
"""A common word of investment names: more matches than ``LIMIT`` [W]."""
LIMIT = 3
"""Not the UI's 5 (the only value of the sample api.investments_q)."""
PAGES = BASE_URL + "/ceny-ofertowe"
BY_NAME_ITEM = {"investment_slug", "name", "offers_active"}


@pytest.fixture(scope="module")
def mcp(budget: Budget, tmp_path_factory: pytest.TempPathFactory) -> Iterator[McpLive]:
    log = tmp_path_factory.mktemp("mcp-investments") / "server-stderr.log"
    with mcp_server(log, budget) as server:
        yield server


@pytest.fixture(scope="module")
def city(mcp: McpLive) -> Call:
    return mcp.call_network(TOOL, city=CITY, limit=MAX_INVESTMENTS_LIMIT)


@pytest.fixture(scope="module")
def by_name(mcp: McpLive) -> Call:
    return mcp.call_network(TOOL, name=NAME, limit=LIMIT)


def check_counts(result: dict[str, Any]) -> list[dict[str, Any]]:
    """D4: the counters agree with each other and with the items."""
    items: list[dict[str, Any]] = result["items"]
    assert result["returned"] == len(items)
    total = result["total"]
    if total is not None:
        assert total >= result["returned"]
        if total > result["returned"]:
            assert result["truncated"]
    if result["truncated"]:
        assert result["hint"]
    return items


def test_a_city_lists_its_investments(city: Call) -> None:
    result = city.data
    items = check_counts(result)
    assert items, f"brak inwestycji w {CITY}"
    assert result["truncated"] == (result["total"] > len(items))
    for item in items:
        assert item["city_slug"] == CITY, item
        developer, slug = item["developer_slug"], item["investment_slug"]
        assert item["investment_url"] == page_url(CITY, "deweloperzy", developer, slug)
        assert item["developer_url"] == page_url(CITY, "deweloperzy", developer)
        active, total = item.get("offers_active"), item.get("offers_total")
        if active is not None and total is not None:
            assert 0 <= active <= total, item
        # [W] an average of 0 is no average: an average only with active offers.
        for name in ("avg_price", "avg_area_m2", "avg_price_per_m2"):
            if name in item:
                assert item[name] > 0 and active, item
        if item.get("status") not in {"active", "archived"}:
            warnings.warn(f"{slug}: nowy status {item.get('status')!r}", stacklevel=1)
    # The default order: the most active offers first.
    counts = [item.get("offers_active", -1) for item in items]
    assert counts == sorted(counts, reverse=True)


def test_a_city_is_filtered_and_ordered_without_asking_again(mcp: McpLive, city: Call) -> None:
    """The domain filters and orders the city's list: the same request, from the cache."""
    first = city.data["items"][0]
    part = first["name"][:4]

    call = mcp.call(
        TOOL,
        city=CITY,
        name=part,
        developer_slug=first["developer_slug"],
        sort="price_per_m2_asc",
    )

    if call.sent:
        warnings.warn(
            "lista inwestycji miasta nie przyszła z cache serwera (Cache-Control tego "
            "endpointu jest nieznany); sprawdź log serwera na DEBUG: 'TTL cache'",
            stacklevel=1,
        )
    assert call.sent <= 1
    items = check_counts(call.data)
    assert first["investment_slug"] in [item["investment_slug"] for item in items]
    for item in items:
        assert InvestmentName.folded(part) in InvestmentName.folded(item["name"]), item
        assert item["developer_slug"] == first["developer_slug"], item
    values = [item["avg_price_per_m2"] for item in items if "avg_price_per_m2" in item]
    assert values == sorted(values)


def test_a_name_honours_the_limit_and_counts_every_match(by_name: Call) -> None:
    """[W] limit other than 5, total of every match, hasMore."""
    result = by_name.data
    items = check_counts(result)
    assert 0 < len(items) <= LIMIT
    for item in items:
        assert set(item) <= BY_NAME_ITEM and "investment_slug" in item, item
        assert NAME in item["name"].casefold(), item
    if result["total"] is None:
        warnings.warn("wyszukiwanie po nazwie nie podało total", stacklevel=1)
    elif result["total"] > LIMIT:
        assert len(items) == LIMIT and result["truncated"], result
    else:
        warnings.warn(
            f"{NAME!r} pasuje tylko do {result['total']} inwestycji: limit {LIMIT} niesprawdzony",
            stacklevel=1,
        )


def test_the_offer_count_of_a_match_is_its_active_offers(mcp: McpLive, by_name: Call) -> None:
    """[W] offerCount = active offers; and a match goes to get_investment."""
    match = by_name.data["items"][0]

    investment = mcp.call_network(
        "get_investment", investment_slug=match["investment_slug"], limit=0
    ).data

    assert investment["investment_slug"] == match["investment_slug"]
    assert investment["name"] == match["name"]
    assert investment.get("offers_active") == match.get("offers_active"), (match, investment)
