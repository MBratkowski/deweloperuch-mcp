"""The golden matrix of the MCP as a whole: a case for every recorded file and every tool."""

from deweloperuch_mcp.consumers.mcp.server import TOOLS
from deweloperuch_mcp.models.government_statistics import Dataset
from support.checks.golden import recorded_cases
from support.golden.mcp import SURFACE
from support.golden.mcp_cases import CASES


def test_every_recorded_mcp_case_is_still_a_case() -> None:
    """A case removed from ``CASES`` leaves its file behind: remove the file on purpose."""
    assert recorded_cases(SURFACE) == set(CASES)


def test_the_matrix_calls_every_tool() -> None:
    called = {tool for golden in CASES.values() for tool, _ in golden.calls}

    assert called == {tool.name for tool in TOOLS}


def test_the_matrix_has_every_dataset_of_both_locations() -> None:
    for location in ("polska", "warszawa"):
        for dataset in Dataset:
            assert f"stats_{location}_{dataset.value}" in CASES
