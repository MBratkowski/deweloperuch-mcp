"""Golden CLI output uses the same terminal geometry on Windows and POSIX."""

import pytest
import respx
import rich.console

from support.golden.cli import check_case
from support.golden.cli_cases.agent_skill import CASES as SKILL_CASES
from support.golden.cli_cases.app import CASES as APP_CASES

CASES = {
    "help": APP_CASES["help"],
    "no_arguments": APP_CASES["no_arguments"],
    "unknown_command": APP_CASES["unknown_command"],
    "help_skill_install": SKILL_CASES["help_skill_install"],
}


@pytest.mark.parametrize("name", CASES)
def test_legacy_windows_console_keeps_the_recorded_help_and_usage(
    monkeypatch: pytest.MonkeyPatch, service: respx.MockRouter, name: str
) -> None:
    monkeypatch.setattr(rich.console, "detect_legacy_windows", lambda: True)

    check_case(name, CASES[name], service)
