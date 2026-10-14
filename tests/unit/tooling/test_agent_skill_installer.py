"""Tests of ``deweloperuch_mcp.tooling.agent_skill_installer``: temporary folders only (the
packaged skill, the home folder and the current folder)."""

from pathlib import Path
from typing import get_args

import pytest

from deweloperuch_mcp.tooling import agent_skill_installer
from deweloperuch_mcp.tooling.agent_skill_installer import (
    AGENT_FOLDERS,
    AgentSkillInstaller,
    CopyBefore,
    SkillAgent,
    SkillInstallRefusedError,
)
from support.paths import REPO

SHIPPED = {"EXAMPLES.md": "examples\n", "SKILL.md": "---\nname: x\n---\nżółw\n"}


def a_skill(folder: Path) -> Path:
    folder.mkdir(parents=True)
    for name, text in SHIPPED.items():
        (folder / name).write_text(text, encoding="utf-8")
    (folder / "notes.txt").write_text("not part of the skill\n", encoding="utf-8")
    return folder


@pytest.fixture
def places(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``tmp_path`` holds ``home``, the current folder ``project`` and the skill."""
    for folder in ("home", "project"):
        (tmp_path / folder).mkdir()
    a_skill(tmp_path / "package" / "deweloperuch-cli")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path / "project")
    return tmp_path


def installer(places: Path) -> AgentSkillInstaller:
    return AgentSkillInstaller(places / "package" / "deweloperuch-cli")


def test_the_agents_are_the_ones_with_folders() -> None:
    assert get_args(SkillAgent) == tuple(AGENT_FOLDERS)


def test_path_and_show_read_the_packaged_skill(places: Path) -> None:
    assert installer(places).path() == places / "package" / "deweloperuch-cli"
    assert installer(places).show() == SHIPPED["SKILL.md"]


def test_a_skill_without_its_main_file_is_an_os_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="SKILL.md"):
        AgentSkillInstaller(tmp_path).path()


def test_a_checkout_reads_the_repositorys_skills_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the wheel's copy (a checkout, an editable install) the repository's
    ``skills/`` is the source; the wheel's copy wins when it exists."""
    checkout = a_skill(tmp_path / "repo" / "deweloperuch-cli")
    monkeypatch.setattr(agent_skill_installer, "PACKAGED", tmp_path / "wheel" / "x")
    monkeypatch.setattr(agent_skill_installer, "CHECKOUT", checkout)

    assert AgentSkillInstaller().path() == checkout

    wheel = a_skill(tmp_path / "wheel" / "x")
    assert AgentSkillInstaller().path() == wheel


def test_the_sources_are_the_wheels_and_the_repositorys() -> None:
    package = Path(agent_skill_installer.__file__).resolve().parents[1]

    assert agent_skill_installer.CHECKOUT == REPO / "skills" / "deweloperuch-cli"
    assert package / "skills" / "deweloperuch-cli" == agent_skill_installer.PACKAGED


@pytest.mark.parametrize(
    ("raw", "folder"),
    [
        ({}, "home/.claude/skills"),
        ({"project": True}, "project/.claude/skills"),
        ({"agent": "codex"}, "home/.agents/skills"),
        ({"agent": "codex", "project": True}, "project/.agents/skills"),
        ({"agent": "cursor"}, "home/.cursor/skills"),
        ({"agent": "cursor", "project": True}, "project/.agents/skills"),
        ({"agent": "gemini-cli"}, "home/.gemini/skills"),
        ({"agent": "github-copilot"}, "home/.copilot/skills"),
        ({"folder": "given"}, "project/given"),
        ({"folder": "~/mine"}, "home/mine"),
    ],
)
def test_install_writes_the_skills_files_where_asked(
    places: Path, raw: dict[str, object], folder: str
) -> None:
    """The skills CLI 1.7.2's folders (its table of agents), or a folder as given."""
    installation = installer(places).install(**raw)  # type: ignore[arg-type]

    target = places / folder / "deweloperuch-cli"
    assert installation.folder == target
    assert installation.before is CopyBefore.NONE
    assert installation.files == ("EXAMPLES.md", "SKILL.md")
    assert {path.name: path.read_text(encoding="utf-8") for path in target.iterdir()} == SHIPPED


def test_an_absolute_folder_stays_as_given(places: Path) -> None:
    installation = installer(places).install(folder=str(places / "x"))

    assert installation.folder == places / "x" / "deweloperuch-cli"


def test_install_again_writes_nothing(places: Path) -> None:
    installer(places).install()
    target = places / "home" / ".claude" / "skills" / "deweloperuch-cli"
    (target / "notes.txt").write_text("mine", encoding="utf-8")

    assert installer(places).install().before is CopyBefore.SAME
    assert sorted(path.name for path in target.iterdir()) == [
        "EXAMPLES.md",
        "SKILL.md",
        "notes.txt",
    ]


def test_a_different_copy_is_replaced_only_with_force(places: Path) -> None:
    installer(places).install()
    target = places / "home" / ".claude" / "skills" / "deweloperuch-cli"
    (target / "SKILL.md").write_text("my notes", encoding="utf-8")

    with pytest.raises(SkillInstallRefusedError, match="inna wersja skilla") as refused:
        installer(places).install()

    assert str(target) in str(refused.value) and "--force" in str(refused.value)
    assert (target / "SKILL.md").read_text(encoding="utf-8") == "my notes"

    assert installer(places).install(force=True).before is CopyBefore.DIFFERENT
    assert (target / "SKILL.md").read_text(encoding="utf-8") == SHIPPED["SKILL.md"]


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"folder": "x", "project": True}, "Podaj --dir albo --agent/--project, nie razem"),
        ({"folder": "x", "agent": "codex"}, "Podaj --dir albo --agent/--project, nie razem"),
        ({"folder": "  "}, "--dir: podaj ścieżkę katalogu skilli"),
        ({"agent": "vim"}, "--agent: oczekiwano jednej z wartości claude-code, codex"),
    ],
)
def test_install_refuses_unclear_places_and_writes_nothing(
    places: Path, raw: dict[str, object], message: str
) -> None:
    with pytest.raises(SkillInstallRefusedError, match=message):
        installer(places).install(**raw)  # type: ignore[arg-type]

    assert list((places / "home").iterdir()) == list((places / "project").iterdir()) == []


@pytest.mark.parametrize("victim_exists", [False, True])
def test_a_link_where_a_file_goes_is_replaced_never_written_through(
    places: Path, victim_exists: bool
) -> None:
    """A dangling link or a link to a file outside the target is a different copy: refused
    without ``force``, replaced by a file with it; the linked file stays as it was."""
    victim = places / "home" / ".zshenv"
    if victim_exists:
        victim.write_text("export SECRET=1\n", encoding="utf-8")
    target = places / "project" / ".claude" / "skills" / "deweloperuch-cli"
    target.mkdir(parents=True)
    (target / "SKILL.md").symlink_to(victim)

    with pytest.raises(SkillInstallRefusedError, match="dowiązanie"):
        installer(places).install(project=True)
    assert (target / "SKILL.md").is_symlink()

    assert installer(places).install(project=True, force=True).before is CopyBefore.DIFFERENT
    assert not (target / "SKILL.md").is_symlink()
    assert (target / "SKILL.md").read_text(encoding="utf-8") == SHIPPED["SKILL.md"]
    assert victim.exists() is victim_exists
    if victim_exists:
        assert victim.read_text(encoding="utf-8") == "export SECRET=1\n"


@pytest.mark.parametrize("linked", ["elsewhere", "nowhere"])
def test_a_linked_skill_folder_is_replaced_never_written_into(places: Path, linked: str) -> None:
    elsewhere = places / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "SKILL.md").write_text("someone else's\n", encoding="utf-8")
    skills = places / "home" / ".claude" / "skills"
    skills.mkdir(parents=True)
    (skills / "deweloperuch-cli").symlink_to(places / linked)

    with pytest.raises(SkillInstallRefusedError, match="inna wersja"):
        installer(places).install()

    installer(places).install(force=True)
    target = skills / "deweloperuch-cli"
    assert not target.is_symlink()
    assert {path.name: path.read_text(encoding="utf-8") for path in target.iterdir()} == SHIPPED
    assert [path.name for path in elsewhere.iterdir()] == ["SKILL.md"]
    assert (elsewhere / "SKILL.md").read_text(encoding="utf-8") == "someone else's\n"


def test_a_linked_skill_folder_with_the_same_files_is_left_as_it_is(places: Path) -> None:
    """``npx skills add`` links an agent's folder to one shared copy by default."""
    shared = a_skill(places / "home" / ".agents" / "skills" / "deweloperuch-cli")
    (shared / "notes.txt").unlink()
    skills = places / "home" / ".claude" / "skills"
    skills.mkdir(parents=True)
    (skills / "deweloperuch-cli").symlink_to(shared)

    assert installer(places).install().before is CopyBefore.SAME
    assert (skills / "deweloperuch-cli").is_symlink()


@pytest.mark.parametrize("existing", [False, True])
def test_a_failure_while_writing_leaves_the_folder_as_it_was(
    places: Path, monkeypatch: pytest.MonkeyPatch, existing: bool
) -> None:
    target = places / "home" / ".claude" / "skills" / "deweloperuch-cli"
    if existing:
        target.mkdir(parents=True)
        (target / "EXAMPLES.md").write_text("old examples\n", encoding="utf-8")
        (target / "SKILL.md").write_text("old\n", encoding="utf-8")
    before = {path.name: path.read_text(encoding="utf-8") for path in target.glob("*")}
    staged = AgentSkillInstaller._staged
    calls: list[str] = []

    def second_fails(folder: Path, name: str, text: str) -> Path:
        calls.append(name)
        if len(calls) == 2:
            raise OSError(28, "No space left on device")
        return staged(folder, name, text)

    monkeypatch.setattr(AgentSkillInstaller, "_staged", staticmethod(second_fails))

    with pytest.raises(OSError, match="No space left"):
        installer(places).install(force=True)

    after = {path.name: path.read_text(encoding="utf-8") for path in target.glob("*")}
    assert after == before  # no half copy and no staged file left behind
