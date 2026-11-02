"""Live: ``search_offers`` in a district written otherwise than the service's slug, through
the installed ``deweloperuch-mcp`` over stdio.

One server for the module, so its cache is its own: the city's districts and the district's
list are not answered from what tests/e2e/test_live_mcp.py read before. Three live requests:
the list of the slug the client makes of the name, the city's districts and the list of the
service's slug.

What it checks on the live service: [P 2026-11-01] the offers variant of ``city-districts``
gives the slug of Praga-Południe, and the search finds the district by a name that folds to
it (no hyphen, so the client's own slug is another one).
"""

from collections.abc import Iterator

import pytest

from support.e2e.live import Budget, McpLive, mcp_server, page_url

pytestmark = pytest.mark.live

WRITTEN_OTHERWISE = "PragaPołudnie"
"""Praga-Południe without its hyphen: the client's slug ``pragapoludnie`` is not the service's
``praga-poludnie`` [P 2026-11-01, sample api.city_districts.offers_v2]."""


@pytest.fixture(scope="module")
def mcp(budget: Budget, tmp_path_factory: pytest.TempPathFactory) -> Iterator[McpLive]:
    log = tmp_path_factory.mktemp("mcp-districts") / "server-stderr.log"
    with mcp_server(log, budget) as server:
        yield server


def test_offers_in_a_district_written_otherwise_are_found(mcp: McpLive) -> None:
    """The client's slug is unknown (the 404 marker), the city's districts name
    Praga-Południe, and its list is asked once more by the service's slug: offers, with the
    link of that list. 3 requests."""
    call = mcp.call_network("search_offers", city="warszawa", district=WRITTEN_OTHERWISE)

    assert not call.error, f"Ustalenie [P 2026-11-01]: dzielnica po slugu serwisu: {call.text}"
    assert call.data["total"] > 0
    assert call.data["list_url"].startswith(page_url("warszawa", "praga-poludnie", "mieszkania"))
    assert "/warszawa/praga-poludnie/mieszkania" in call.data["list_url"]
    assert call.sent == 3
