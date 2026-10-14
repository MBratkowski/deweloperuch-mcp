"""Live: ``search_developers`` (MCP, the installed server over stdio) and
``deweloperuch developers search`` (CLI): at most 4 live requests.

One server for the module, so a repeated search comes from its cache. Assertions are
about structure, ranges and consistency, never about today's numbers. Behaviours marked
[W] in the code are checked here on the first live run:

- ``total`` and ``hasMore`` of the service mean what they mean for its city search (every
  match; more than given), so a complete result has ``total == returned``;
- a ``limit`` other than the UI's 5 is honoured up to 20 (``returned == min(20, total)``);
- the developer's profile of the whole country (``/ceny-ofertowe/polska/deweloperzy/…``)
  is the link of every match (only its address is checked here: opening it would be
  one more request; ``get_developer`` opens that page).
"""

import json
import re
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from deweloperuch_mcp.identity import BASE_URL
from support.e2e.live import Budget, Call, McpLive, Run, mcp_server, run_cli

pytestmark = pytest.mark.live

TOOL = "search_developers"
PROFILES = BASE_URL + "/ceny-ofertowe/polska/deweloperzy/"
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
KNOWN = "atal"
"""A large developer of the samples (``api.developers_q``: ATAL S.A., slug ``atal``)."""
COMMON = "dev"
"""A fragment many developers' names hold (e.g. "Development"), so 20 may not be all of them."""
NOTHING = "zzqxv-brak"
MAX_MATCHES = 20

Cli = Callable[..., Run]


@pytest.fixture(scope="module")
def mcp(budget: Budget, tmp_path_factory: pytest.TempPathFactory) -> Iterator[McpLive]:
    log = tmp_path_factory.mktemp("mcp-developers") / "server-stderr.log"
    with mcp_server(log, budget) as server:
        yield server


@pytest.fixture(scope="module")
def known(mcp: McpLive) -> Call:
    return mcp.call_network(TOOL, name=KNOWN)


@pytest.fixture(scope="module")
def cli(budget: Budget, tmp_path_factory: pytest.TempPathFactory) -> Cli:
    logs = tmp_path_factory.mktemp("cli-developers")

    def run(*args: str) -> Run:
        return run_cli(budget, logs, *args)

    return run


def check(result: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    """D4 counters consistent with the items and each other; slugs and links (D12)."""
    assert list(result)[:3] == ["total", "returned", "truncated"]
    items: list[dict[str, Any]] = result["items"]
    assert result["returned"] == len(items) <= limit
    total = result["total"]
    # [W] total is every match: known whenever the service says how many there are.
    assert total is not None, f"total null: liczba z serwisu nie pasuje do wyników ({result})"
    assert total >= result["returned"]
    assert result["truncated"] == (total > result["returned"])
    # [W] the limit is honoured up to 20: a page as full as the matches allow.
    assert result["returned"] == min(limit, total)
    if result["truncated"]:
        assert "Doprecyzuj nazwę" in result["hint"]
    slugs = [item["developer_slug"] for item in items]
    assert len(set(slugs)) == len(slugs)
    for item in items:
        assert SLUG.fullmatch(item["developer_slug"]), item
        assert item["name"].strip(), item
        assert item.get("offer_count", 0) >= 0, item
        assert item["developer_url"] == PROFILES + item["developer_slug"], item
    return items


# --- MCP ---------------------------------------------------------------------------------


def test_a_known_developer_gives_its_slug_and_profile(known: Call) -> None:
    items = check(known.data, limit=5)

    atal = [item for item in items if item["developer_slug"] == KNOWN]
    assert atal, items
    assert "ATAL" in atal[0]["name"].upper()
    assert known.sent == 1


def test_the_same_search_comes_from_the_cache(mcp: McpLive, known: Call) -> None:
    call = mcp.call(TOOL, name=f"  {KNOWN} ", limit="5")

    assert call.sent == 0, "powtórzone wyszukiwanie nie przyszło z cache serwera"
    assert call.data == known.data


def test_a_common_fragment_with_the_largest_limit(mcp: McpLive) -> None:
    call = mcp.call_network(TOOL, name=COMMON, limit=MAX_MATCHES)

    check(call.data, limit=MAX_MATCHES)
    assert call.sent == 1


def test_nothing_found_says_what_to_try(mcp: McpLive) -> None:
    call = mcp.call_network(TOOL, name=NOTHING)

    result = call.data
    assert (result["total"], result["returned"], result["truncated"]) == (0, 0, False)
    assert result["items"] == []
    assert NOTHING in result["hint"]


@pytest.mark.parametrize(
    ("arguments", "said"),
    [
        ({"name": "a"}, "name: podaj od 2 do 100 znaków nazwy dewelopera"),
        ({"name": KNOWN, "limit": 21}, "limit"),
        ({"name": KNOWN, "limit": 0}, "limit"),
    ],
)
def test_invalid_arguments_are_refused_without_a_request(
    mcp: McpLive, arguments: dict[str, Any], said: str
) -> None:
    call = mcp.call(TOOL, **arguments)

    assert call.error and said in call.text
    assert call.sent == 0


# --- CLI ---------------------------------------------------------------------------------


def test_cli_json_of_a_known_developer(cli: Cli) -> None:
    run = cli("developers", "search", KNOWN, "--json")

    assert run.code == 0, (run.code, run.stderr)
    assert run.stderr == ""
    run.readable()
    result = json.loads(run.stdout)
    items = check(result, limit=5)
    assert any(item["developer_slug"] == KNOWN for item in items)
    assert run.sent == 1
