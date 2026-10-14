"""Tests of
``deweloperuch_mcp.consumers.mcp.presenters.get_transaction_statistics_mcp_presenter``.
"""

from typing import Any

import pytest

from deweloperuch_mcp.consumers.mcp.presenters import (
    get_transaction_statistics_mcp_presenter as tool,
)
from deweloperuch_mcp.consumers.shared.transaction_views import (
    TransactionPeriodView,
    TransactionStatisticsView,
)

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


@pytest.mark.parametrize(
    ("shown", "view"),
    [
        (tool.TransactionStatisticsResult, TransactionStatisticsView),
        (tool.TransactionPeriodItem, TransactionPeriodView),
    ],
)
def test_the_result_keeps_the_domain_field_names(shown: Any, view: Any) -> None:
    """D3: the MCP representation only drops fields of the view the CLI prints whole."""
    assert set(shown.model_fields) <= set(view.model_fields)
