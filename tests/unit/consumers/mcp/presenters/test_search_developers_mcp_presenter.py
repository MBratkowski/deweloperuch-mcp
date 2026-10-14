"""Tests of ``deweloperuch_mcp.consumers.mcp.presenters.search_developers_mcp_presenter``."""

import pytest

from deweloperuch_mcp.consumers.mcp.presenters import search_developers_mcp_presenter as results
from deweloperuch_mcp.consumers.shared import developer_views as views

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_the_result_keeps_the_field_names_of_the_view() -> None:
    """D3: the MCP representation only drops fields of the view the CLI prints whole."""
    assert set(results.DevelopersResult.model_fields) == set(views.DeveloperSearchView.model_fields)
    assert set(results.DeveloperItem.model_fields) == set(views.DeveloperMatchView.model_fields)
