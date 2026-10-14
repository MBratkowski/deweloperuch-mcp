"""Tests of ``deweloperuch_mcp.consumers.mcp.presenters.search_investments_mcp_presenter``."""

import pytest
from pydantic import BaseModel

from deweloperuch_mcp.consumers.mcp.presenters import search_investments_mcp_presenter as presenter
from deweloperuch_mcp.consumers.shared import investment_search_views as views

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


@pytest.mark.parametrize(
    ("shown", "view"),
    [
        (presenter.InvestmentsResult, views.InvestmentSearchView),
        (presenter.InvestmentSearchItem, views.InvestmentSummaryView),
    ],
)
def test_the_mcp_result_keeps_the_names_of_the_view(
    shown: type[BaseModel], view: type[BaseModel]
) -> None:
    """D3: the representation only drops fields of the view the CLI prints whole."""
    assert set(shown.model_fields) <= set(view.model_fields)
