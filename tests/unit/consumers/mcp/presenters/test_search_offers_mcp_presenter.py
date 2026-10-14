"""Tests of ``deweloperuch_mcp.consumers.mcp.presenters.search_offers_mcp_presenter``."""

import pytest

from deweloperuch_mcp.consumers.mcp.presenters.search_offers_mcp_presenter import OfferItem
from support.builders.offers import COMPACT_OFFER

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_search_items_are_compact() -> None:
    assert set(OfferItem.model_fields) == COMPACT_OFFER | {"city", "city_slug"}
