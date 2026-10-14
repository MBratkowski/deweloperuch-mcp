"""The golden cases of ``deweloperuch skill`` (tests/golden/cli/<case>.json): the help of
its commands and the refusals that happen before any file is touched (installs write to
the home folder: tests/unit/consumers/cli/commands/test_skill_commands.py; ``show`` and
``path`` print the skill and where the package keeps it: tests/skill)."""

from support.golden.cli import Case, case

CASES: dict[str, Case] = {
    "help_skill_install": case("skill", "install", "--help"),
    "help_skill_show": case("skill", "show", "--help"),
    "help_skill_path": case("skill", "path", "--help"),
    "skill_install_dir_and_project": case("skill", "install", "--dir", "x", "--project"),
    "skill_install_unknown_agent": case("skill", "install", "--agent", "vim"),
}
