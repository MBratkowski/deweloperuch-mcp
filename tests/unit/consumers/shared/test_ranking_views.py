"""Tests of ``deweloperuch_mcp.consumers.shared.ranking_views``."""

from typing import get_args

import pytest

from deweloperuch_mcp.consumers.shared import ranking_views as views
from deweloperuch_mcp.models.location_ranking import RankingLevel, RankingOrder

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_the_choices_are_the_domains() -> None:
    assert get_args(views.RankingLevelChoice) == tuple(level.value for level in RankingLevel)
    assert get_args(views.RankingSortChoice) == tuple(order.value for order in RankingOrder)
