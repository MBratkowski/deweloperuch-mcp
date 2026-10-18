"""Tests of ``deweloperuch_mcp.consumers.mcp.presenters.estimate_property_value_mcp_presenter``."""

from dataclasses import replace

import pytest
from pydantic import BaseModel

from deweloperuch_mcp.consumers.mcp.presenters import estimate_property_value_mcp_presenter as tool
from deweloperuch_mcp.consumers.mcp.support.mcp_model import dump
from deweloperuch_mcp.consumers.shared.valuation_views import (
    ComparableTransactionView,
    PricePerM2StatsView,
    ValuationView,
)
from deweloperuch_mcp.models.valuation import ComparablesLimit
from deweloperuch_mcp.usecases.estimate_property_value import EstimatePropertyValueResult
from support.builders.valuation import CISNA_CAVEAT, CISNA_SUBJECT, api_sample, mapped
from support.providers.routes.valuation import cisna

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


def test_at_the_cap_the_caveat_still_comes_first() -> None:
    """The presenter words a list cut at its cap itself; the caveat of the use case stays."""
    listing = mapped(cisna(), CISNA_SUBJECT).nearest(ComparablesLimit(1))
    presenter = tool.EstimatePropertyValueMcpPresenter(max_comparables=1)

    shown = presenter.present(EstimatePropertyValueResult(listing=listing))

    assert shown.low_confidence is True
    assert shown.hint == (
        f"{CISNA_CAVEAT} Pokazano 1 najbliższą z 2 transakcji porównawczych. To maksimum w "
        "jednym wywołaniu; stats to statystyki podane przez serwis."
    )


def test_a_reliable_estimate_says_so_and_no_estimate_says_nothing() -> None:
    """low_confidence: false is shown (as truncated is); without an estimate it is left out."""
    presenter = tool.EstimatePropertyValueMcpPresenter(max_comparables=50)
    reliable = EstimatePropertyValueResult(listing=mapped(api_sample()).nearest())
    without = EstimatePropertyValueResult(
        listing=replace(mapped(api_sample()), estimated_value=None).nearest()
    )

    assert dump(presenter.present(reliable))["low_confidence"] is False
    assert "low_confidence" not in dump(presenter.present(without))
