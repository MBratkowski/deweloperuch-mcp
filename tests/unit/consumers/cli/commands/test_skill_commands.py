"""Tests of ``deweloperuch_mcp.consumers.cli.commands.skill_commands``: offline, on
temporary folders (the home folder, the project and the packaged skill)."""

from pathlib import Path

import pytest

from deweloperuch_mcp.consumers.cli.support.common import ExitCode
from deweloperuch_mcp.tooling import agent_skill_installer
from support.providers.cli import Cli, ok

INSTRUCTIONS = "---\nname: deweloperuch-cli\ndescription: test\n---\n\n# Skill\n"
USAGE = [
    "Agent wczyta go w nowej sesji i sam użyje przy pytaniach o ceny mieszkań, oferty "
    "deweloperów albo ceny transakcyjne.",
    "Treść skilla: deweloperuch skill show · polecenia CLI bez instalacji: "
    "uvx --from deweloperuch-mcp deweloperuch --help",
]


@pytest.fixture
def places(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``tmp_path`` holds ``home``, the current folder ``project`` and the packaged skill."""
    source = tmp_path / "package" / "deweloperuch-cli"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(INSTRUCTIONS, encoding="utf-8")
    (source / "EXAMPLES.md").write_text("examples\n", encoding="utf-8")
    monkeypatch.setattr(agent_skill_installer, "PACKAGED", tmp_path / "no-wheel")
    monkeypatch.setattr(agent_skill_installer, "CHECKOUT", source)
    for folder in ("home", "project"):
        (tmp_path / folder).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path / "project")
    return tmp_path


def test_install_writes_the_users_claude_code_skill_by_default(run: Cli, places: Path) -> None:
    out = ok(run("skill", "install"))

    folder = places / "home" / ".claude" / "skills" / "deweloperuch-cli"
    assert out.splitlines() == [
        f"Zainstalowano skill deweloperuch-cli w {folder} (pliki: EXAMPLES.md, SKILL.md).",
        *USAGE,
    ]
    assert (folder / "SKILL.md").read_text(encoding="utf-8") == INSTRUCTIONS
    assert sorted(path.name for path in folder.iterdir()) == ["EXAMPLES.md", "SKILL.md"]
    assert run.sessions == []


@pytest.mark.parametrize(
    ("args", "folder"),
    [
        (["--project"], "project/.claude/skills"),
        (["--agent", "cursor"], "home/.cursor/skills"),
        (["--agent", "codex", "--project"], "project/.agents/skills"),
        (["--agent", "github-copilot", "--user"], "home/.copilot/skills"),
        (["--dir", "agent-skills"], "project/agent-skills"),
    ],
)
def test_install_goes_to_the_folder_asked_for(
    run: Cli, places: Path, args: list[str], folder: str
) -> None:
    out = ok(run("skill", "install", *args))

    target = places / folder / "deweloperuch-cli"
    assert f" w {target} " in out.splitlines()[0]
    assert (target / "SKILL.md").is_file()


def test_install_again_changes_nothing(run: Cli, places: Path) -> None:
    ok(run("skill", "install"))

    out = ok(run("skill", "install"))

    folder = places / "home" / ".claude" / "skills" / "deweloperuch-cli"
    assert out.splitlines()[0] == (
        f"Skill deweloperuch-cli w {folder} jest już aktualny; nic nie zapisano."
    )


def test_a_different_copy_needs_force(run: Cli, places: Path) -> None:
    ok(run("skill", "install"))
    folder = places / "home" / ".claude" / "skills" / "deweloperuch-cli"
    (folder / "SKILL.md").write_text("my notes", encoding="utf-8")

    refused = run("skill", "install")

    assert refused.exit_code == ExitCode.INVALID_INPUT
    assert refused.stdout == ""
    assert refused.stderr == (
        f"Błąd: W {folder} jest już inna wersja skilla deweloperuch-cli (zmieniona, z innej "
        "wersji pakietu albo jako dowiązanie); nic nie zapisano. Żeby ją zastąpić, dodaj "
        "--force.\n"
    )
    assert (folder / "SKILL.md").read_text(encoding="utf-8") == "my notes"

    out = ok(run("skill", "install", "--force"))

    assert out.splitlines()[0] == (
        f"Zastąpiono skill deweloperuch-cli w {folder} wersją z pakietu "
        "(pliki: EXAMPLES.md, SKILL.md)."
    )
    assert (folder / "SKILL.md").read_text(encoding="utf-8") == INSTRUCTIONS


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--dir", "x", "--project"], "Błąd: Podaj --dir albo --agent/--project, nie razem"),
        (["--dir", "x", "--agent", "codex"], "Błąd: Podaj --dir albo --agent/--project"),
        (["--dir", ""], "Błąd: --dir: podaj ścieżkę katalogu skilli"),
        (["--agent", "vim"], "--agent"),
    ],
)
def test_install_refuses_unclear_places_and_writes_nothing(
    run: Cli, places: Path, args: list[str], message: str
) -> None:
    result = run("skill", "install", *args)

    assert result.exit_code == ExitCode.INVALID_INPUT
    assert message in result.stderr
    assert not (places / "home" / ".claude").exists()
    assert list((places / "project").iterdir()) == []


def test_install_into_a_place_it_cannot_write_exits_with_1(run: Cli, places: Path) -> None:
    (places / "project" / "file").write_text("not a folder", encoding="utf-8")

    result = run("skill", "install", "--dir", "file")

    assert result.exit_code == ExitCode.UNEXPECTED
    assert result.stderr.startswith("Błąd: nie udało się zainstalować skilla: ")
    assert "Traceback" not in result.stderr


def test_show_prints_the_skill_md_as_it_is(run: Cli, places: Path) -> None:
    assert ok(run("skill", "show")) == INSTRUCTIONS


def test_path_prints_the_packaged_folder(run: Cli, places: Path) -> None:
    assert ok(run("skill", "path")) == f"{places / 'package' / 'deweloperuch-cli'}\n"


@pytest.mark.parametrize("command", ["show", "path", "install"])
def test_a_package_without_its_skill_exits_with_1(
    run: Cli, places: Path, command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent_skill_installer, "CHECKOUT", places / "nothing")

    result = run("skill", command)

    assert result.exit_code == ExitCode.UNEXPECTED
    assert result.stderr.startswith("Błąd: nie udało się ")
    assert "SKILL.md" in result.stderr
    assert result.stdout == ""


def test_a_link_in_the_way_is_refused_and_its_target_never_written(run: Cli, places: Path) -> None:
    """A ``SKILL.md`` that links to a file of the home folder: nothing is written there."""
    target = places / "project" / ".claude" / "skills" / "deweloperuch-cli"
    target.mkdir(parents=True)
    victim = places / "home" / ".zshenv"
    (target / "SKILL.md").symlink_to(victim)

    refused = run("skill", "install", "--project")

    assert refused.exit_code == ExitCode.INVALID_INPUT
    assert "dowiązanie" in refused.stderr
    assert not victim.exists()

    ok(run("skill", "install", "--project", "--force"))

    assert not victim.exists()
    assert (target / "SKILL.md").read_text(encoding="utf-8") == INSTRUCTIONS


def test_a_write_error_exits_with_1_and_leaves_no_half_copy(
    run: Cli, places: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def full_disk(folder: Path, name: str, text: str) -> Path:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(
        agent_skill_installer.AgentSkillInstaller, "_staged", staticmethod(full_disk)
    )

    result = run("skill", "install")

    assert result.exit_code == ExitCode.UNEXPECTED
    assert result.stderr == (
        "Błąd: nie udało się zainstalować skilla: [Errno 28] No space left on device\n"
    )
    target = places / "home" / ".claude" / "skills" / "deweloperuch-cli"
    assert list(target.iterdir()) == []
