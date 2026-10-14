"""Tests of ``deweloperuch_mcp.consumers.mcp.presenters.rank_locations_mcp_presenter``."""

import pytest

from deweloperuch_mcp.consumers.mcp.presenters import rank_locations_mcp_presenter as tool
from deweloperuch_mcp.consumers.shared import ranking_views as views

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_the_output_keeps_the_names_of_the_view() -> None:
    """D3: the MCP representation only describes and compacts the view."""
    assert set(tool.LocationRankingResult.model_fields) == set(
        views.LocationRankingView.model_fields
    )
    assert set(tool.RankedLocationItem.model_fields) == set(views.RankedLocationView.model_fields)
