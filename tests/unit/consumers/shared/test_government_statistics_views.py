"""Tests of ``deweloperuch_mcp.consumers.shared.government_statistics_views``."""

import dataclasses

from deweloperuch_mcp.consumers.shared.government_statistics_views import GovernmentStatisticsView


def test_the_statistics_view_has_the_fields_the_cli_prints_in_order() -> None:
    """``--json`` prints ``dataclasses.asdict`` of it: the order is the output's order."""
    assert [field.name for field in dataclasses.fields(GovernmentStatisticsView)] == [
        "location_slug",
        "location_name",
        "dataset",
        "title",
        "source",
        "frequency",
        "total",
        "returned",
        "truncated",
        "available_from",
        "hint",
        "note",
        "stats_url",
        "series",
    ]
