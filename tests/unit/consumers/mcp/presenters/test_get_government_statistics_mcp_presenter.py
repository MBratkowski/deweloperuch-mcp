"""Tests of
``deweloperuch_mcp.consumers.mcp.presenters.get_government_statistics_mcp_presenter``.
"""

import dataclasses
from typing import Any

import pytest
from pydantic import BaseModel

from deweloperuch_mcp.consumers.mcp.presenters.get_government_statistics_mcp_presenter import (
    GovernmentStatisticsResult,
    SeriesItem,
)
from deweloperuch_mcp.consumers.shared.government_statistics_views import GovernmentStatisticsView
from deweloperuch_mcp.models.government_statistics import TimeSeries

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


@pytest.mark.parametrize(
    ("shown", "domain", "added"),
    [
        (GovernmentStatisticsResult, GovernmentStatisticsView, {"periods"}),
        (SeriesItem, TimeSeries, {"values"}),
    ],
)
def test_mcp_statistics_keep_the_domain_field_names(
    shown: type[BaseModel], domain: type[Any], added: set[str]
) -> None:
    """D3 for the statistics (plain dataclasses, D13): the table form adds the periods
    once and each series' values instead of its points."""
    names = {field.name for field in dataclasses.fields(domain)}

    assert set(shown.model_fields) - added <= names
    assert added <= set(shown.model_fields)
