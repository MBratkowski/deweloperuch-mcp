"""Writes the agent skill's ``skills/deweloperuch-cli/REFERENCE.md`` from the CLI itself.

    uv run python packaging/skill_reference.py           # write it (``make skill``)
    uv run python packaging/skill_reference.py --check   # exit 1 when it is out of date

Every group, command, argument and option of ``deweloperuch``, with the CLI's own help
texts (Polish), read from the Typer app: the reference never drifts from the CLI
(tests/skill/test_skill.py fails when the file is not what this script writes). Offline:
it imports the CLI and reads its help; no command runs.

The command that lifts a STOP is left out on purpose: the skill is for agents, and only
the user lifts a STOP, after checking its cause.
"""

import sys
from pathlib import Path

from typer.core import TyperCommand, TyperGroup
from typer.main import get_group

from deweloperuch_mcp.consumers.cli.app import app

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "skills" / "deweloperuch-cli" / "REFERENCE.md"
PROGRAM = "deweloperuch"
FOR_PEOPLE_ONLY = {("stop", "clear")}
"""Commands an agent must never run, left out of the reference."""

HEADER = f"""\
# `{PROGRAM}`: command reference

<!-- Generated from the CLI by packaging/skill_reference.py (`make skill`); do not edit. -->

Every command runs as `{PROGRAM} …` or, without installing, as \
`uvx --from deweloperuch-mcp {PROGRAM} …`. The descriptions are the CLI's own help texts \
(Polish); `--help` after any group or command prints them offline. `[required]` marks what \
must be given, `[default: …]` the value used otherwise; `--json` prints the result as JSON. \
The `stop` group's command that lifts a STOP is left out on purpose: only the user lifts a \
STOP, after checking its cause.
"""


def render() -> str:
    """The whole reference, as this version of the CLI describes itself."""
    root = get_group(app)
    context = root.make_context(PROGRAM, [], resilient_parsing=True)
    sections = [HEADER]
    for name in root.list_commands(context):
        group = root.get_command(context, name)
        assert isinstance(group, TyperGroup), f"{name}: every command lives in a group"
        sections.append(_group(name, group))
    return "\n".join(sections)


def _group(name: str, group: TyperGroup) -> str:
    context = group.make_context(f"{PROGRAM} {name}", [], resilient_parsing=True)
    lines = [f"## `{PROGRAM} {name}`", "", _text(group.help), ""]
    for command_name in group.list_commands(context):
        if (name, command_name) in FOR_PEOPLE_ONLY:
            continue
        command = group.get_command(context, command_name)
        assert isinstance(command, TyperCommand), f"{name} {command_name}: a command"
        lines += _command(f"{PROGRAM} {name} {command_name}", command)
    return "\n".join(lines)


def _command(path: str, command: TyperCommand) -> list[str]:
    context = command.make_context(path, [], resilient_parsing=True)
    usage = " ".join(piece.strip("{}") for piece in command.collect_usage_pieces(context))
    parameters = []
    for parameter in command.get_params(context):
        record = parameter.get_help_record(context)
        if record is None or "--help" in parameter.opts:
            continue
        names, help_text = record
        choices = getattr(parameter.type, "choices", None)
        if choices and not names.startswith("-"):  # an argument's help shows no choices
            names += f" <{'|'.join(map(str, choices))}>"
        parameters.append(f"- `{names}`: {_text(help_text)}")
    heading = [f"### `{path} {usage}`", "", _text(command.help), ""]
    return [*heading, *parameters, ""] if parameters else heading


def _text(help_text: str | None) -> str:
    """Help as Markdown: one space before ``[default: …]`` and ``[required]``."""
    return (help_text or "").strip().replace("  [", " [")


def main(argv: list[str]) -> int:
    reference = render()
    if argv[1:] == ["--check"]:
        current = REFERENCE.read_text(encoding="utf-8") if REFERENCE.exists() else ""
        if current != reference:
            print(f"{REFERENCE.relative_to(ROOT)} is out of date: run `make skill`.")
            return 1
        return 0
    REFERENCE.write_text(reference, encoding="utf-8")
    print(f"OK: {REFERENCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
