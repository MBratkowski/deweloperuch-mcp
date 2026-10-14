"""Tests of ``deweloperuch_mcp.consumers.mcp.presenters.estimate_property_value_mcp_presenter``."""

import pytest
from pydantic import BaseModel

from deweloperuch_mcp.consumers.mcp.presenters import estimate_property_value_mcp_presenter as tool
from deweloperuch_mcp.consumers.shared.valuation_views import (
    ComparableTransactionView,
    PricePerM2StatsView,
    ValuationView,
)

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_the_mcp_result_keeps_the_names_of_the_view() -> None:
    """D3: the representation only drops fields of the view (the address the caller gave,
    the city of each building) and adds the D4 counters."""
    pairs: list[tuple[type[BaseModel], type[BaseModel], set[str]]] = [
        (tool.ValuationResult, ValuationView, {"comparables_returned", "truncated"}),
        (tool.ComparableItem, ComparableTransactionView, set()),
        (tool.PriceStatsItem, PricePerM2StatsView, set()),
    ]
    for shown, view, added in pairs:
        assert set(shown.model_fields) - added <= set(view.model_fields)
        assert added <= set(shown.model_fields)
