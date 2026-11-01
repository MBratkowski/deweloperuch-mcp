"""Tests of ``deweloperuch_mcp.consumers.mcp.presenters.search_offers_mcp_presenter``."""

import pytest

from deweloperuch_mcp.consumers.mcp.presenters.search_offers_mcp_presenter import OfferItem
from support.builders.offers import COMPACT_OFFER

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_search_items_are_compact() -> None:
    """A search is of one city (``polska`` is refused), so an item has no city of its own;
    its district comes right after its investment."""
    fields = list(OfferItem.model_fields)

    assert set(fields) == COMPACT_OFFER
    assert fields[fields.index("investment_name") + 1] == "district"
