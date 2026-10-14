"""Golden cases of the MCP tool ``get_investment``: tests/golden/mcp/<case>.json."""

from pathlib import Path

import pytest
import respx

from support.golden.mcp import check_case
from support.golden.mcp_cases.get_investment import CASES

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


@pytest.mark.parametrize("name", CASES)
def test_mcp_results_are_the_recorded_ones(
    name: str, service: respx.MockRouter, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    check_case(name, CASES[name], service, tmp_path, caplog)
