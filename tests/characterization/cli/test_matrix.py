"""The golden matrix of the CLI as a whole: a case for every recorded file and every command."""

from support.checks.golden import recorded_cases
from support.golden.cli import SURFACE
from support.golden.cli_cases import CASES


def test_every_recorded_cli_case_is_still_a_case() -> None:
    """A case removed from ``CASES`` leaves its file behind: remove the file on purpose."""
    assert recorded_cases(SURFACE) == set(CASES)


def test_the_matrix_covers_every_command() -> None:
    commands = {tuple(arg for arg in c.args[:2] if not arg.startswith("-")) for c in CASES.values()}

    for command in [
        ("locations", "search"),
        ("offers", "search"),
        ("offers", "get"),
        ("investments", "get"),
        ("stats", "government"),
        ("stats", "market"),
        ("stats", "transactions"),
        ("stats", "cities"),
        ("developers", "get"),
        ("developers", "search"),
        ("investments", "search"),
        ("buildings", "get"),
        ("valuation", "estimate"),
        ("stop", "status"),
        ("stop", "clear"),
        ("skill", "install"),
        ("skill", "show"),
        ("skill", "path"),
    ]:
        assert command in commands
