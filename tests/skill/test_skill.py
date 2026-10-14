"""The agent skill ``deweloperuch-cli`` as the repository publishes it (``skills/
deweloperuch-cli``: what ``npx skills add``, the Claude Code plugin and the wheel ship).

The Agent Skills format (front matter, size), a reference that is what the CLI says of
itself, examples the CLI accepts, every exit code explained, and no word on how to lift a
STOP (only the user does that). Offline: nothing runs but the CLI's argument parser.
"""

import json
import re
import runpy
import shlex
import tomllib

import pytest
from typer.core import TyperCommand, TyperGroup
from typer.main import get_group

from deweloperuch_mcp.consumers.cli.app import app
from deweloperuch_mcp.consumers.cli.support.common import ExitCode
from deweloperuch_mcp.tooling import agent_skill_installer
from support.paths import PACKAGING, PLUGIN_MANIFESTS, REPO, SKILL

FILES = ("EXAMPLES.md", "REFERENCE.md", "SKILL.md")
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
"""Front-matter fields of the Agent Skills specification."""
MAX_LINES = 200
FENCED = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
PREFIXES = ("uvx --from deweloperuch-mcp deweloperuch ", "deweloperuch ")


def text(name: str) -> str:
    return (SKILL / name).read_text(encoding="utf-8")


def front_matter(source: str) -> dict[str, str]:
    """``key: value`` lines between the opening ``---`` lines: one line per field, so any
    agent's YAML reader takes them the same way."""
    head, separator, _ = source.removeprefix("---\n").partition("\n---\n")
    assert source.startswith("---\n") and separator, "SKILL.md opens with front matter"
    fields = dict(line.split(": ", 1) for line in head.splitlines())
    assert len(fields) == len(head.splitlines()), "one field per line"
    return fields


def commands(source: str) -> list[list[str]]:
    """The arguments of every ``deweloperuch`` command in the code blocks of ``source``."""
    found = []
    for block in FENCED.findall(source):
        for line in block.splitlines():
            prefix = next((p for p in PREFIXES if line.startswith(p)), None)
            if prefix is not None:
                found.append(shlex.split(line.removeprefix(prefix)))
    return found


def parse(args: list[str]) -> None:
    """Parse ``deweloperuch ARGS`` as the CLI would, without running the command: a wrong
    command, option, value or a missing argument raises the CLI's usage error."""
    root = get_group(app)
    context = root.make_context("deweloperuch", [], resilient_parsing=True)
    group_name, command_name, *rest = args
    group = root.get_command(context, group_name)
    assert isinstance(group, TyperGroup), f"no group {group_name}"
    group_context = group.make_context(group_name, [], parent=context, resilient_parsing=True)
    command = group.get_command(group_context, command_name)
    assert isinstance(command, TyperCommand), f"no command {group_name} {command_name}"
    command.make_context(command_name, rest, parent=group_context)


def test_the_skill_is_its_three_files() -> None:
    assert sorted(path.name for path in SKILL.iterdir()) == list(FILES)
    assert agent_skill_installer.CHECKOUT == SKILL


def test_the_front_matter_follows_the_agent_skills_format() -> None:
    fields = front_matter(text("SKILL.md"))

    assert set(fields) <= FIELDS
    assert fields["name"] == SKILL.name == agent_skill_installer.SKILL
    assert NAME.fullmatch(fields["name"]) and len(fields["name"]) <= 64
    assert not {"claude", "anthropic"} & set(fields["name"].split("-"))
    assert 0 < len(fields["description"]) <= 1024
    for value in fields.values():  # plain YAML scalars: no mapping, no comment, no quote
        assert ": " not in value and " #" not in value and value[0] not in "\"'[{>|*&!%@`"


def test_the_description_says_when_to_use_it_in_both_languages() -> None:
    description = front_matter(text("SKILL.md"))["description"]

    for trigger in ("ceny mieszkań", "deweloper", "ceny transakcyjne", "RCN", "GUS", "NBP"):
        assert trigger in description
    assert "wycena mieszkania" in description and "Poland" in description


def test_the_instructions_stay_short_and_point_to_the_other_files() -> None:
    instructions = text("SKILL.md")

    assert len(instructions.splitlines()) <= MAX_LINES
    assert set(re.findall(r"\]\(([A-Z]+\.md)\)", instructions)) == {"REFERENCE.md", "EXAMPLES.md"}


def test_the_reference_is_what_the_cli_says_of_itself() -> None:
    render = runpy.run_path(str(PACKAGING / "skill_reference.py"), run_name="reference")["render"]

    assert text("REFERENCE.md") == render(), "run `make skill`"


@pytest.mark.parametrize("name", ["SKILL.md", "EXAMPLES.md"])
def test_every_example_is_a_command_the_cli_accepts(name: str) -> None:
    found = [args for args in commands(text(name)) if "--help" not in args]

    assert len(found) >= 10
    for args in found:
        parse(args)


def test_the_check_of_the_examples_sees_a_wrong_command() -> None:
    with pytest.raises(Exception, match="--rooms"):
        parse(["offers", "search", "krakow", "--rooms", "2"])
    with pytest.raises(AssertionError, match="no command"):
        parse(["offers", "list"])


def test_every_exit_code_is_explained() -> None:
    instructions = text("SKILL.md")

    for code in ExitCode:
        assert f"\n| {code.value} | " in instructions


@pytest.mark.parametrize("name", FILES)
def test_the_skill_never_says_how_to_lift_a_stop(name: str) -> None:
    """Only the user lifts a STOP, after checking its cause (the reference leaves the
    command out, the instructions only say it is for people)."""
    assert not re.search(r"stop\W+clear", text(name), re.IGNORECASE)


def test_the_claude_code_plugin_is_the_repository_with_its_skills_folder() -> None:
    plugin = json.loads((PLUGIN_MANIFESTS / "plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads((PLUGIN_MANIFESTS / "marketplace.json").read_text(encoding="utf-8"))

    assert plugin["name"] == "deweloperuch"
    (entry,) = marketplace["plugins"]
    assert entry["name"] == plugin["name"] and entry["source"] == "./"
    assert marketplace["name"] == "deweloperuch-mcp"
    assert (REPO / "skills" / SKILL.name / "SKILL.md").is_file()  # the plugin's skills/


def test_the_wheel_carries_the_skill_where_the_package_reads_it() -> None:
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = project["tool"]["hatch"]["build"]["targets"]["wheel"]
    sdist = project["tool"]["hatch"]["build"]["targets"]["sdist"]

    assert f"skills/{SKILL.name}" in wheel["only-include"]
    assert "skills" in sdist["only-include"]
    packaged = agent_skill_installer.PACKAGED.relative_to(agent_skill_installer.PACKAGED.parents[2])
    assert f"{wheel['sources']['skills']}/{SKILL.name}" == packaged.as_posix()
