"""``AgentSkillInstaller``: the agent skill ``deweloperuch-cli`` (how AI agents use the
``deweloperuch`` CLI) on this machine, for ``deweloperuch skill``. Plain files; nothing
goes to the service.

The skill's source is the repository's ``skills/deweloperuch-cli/`` (what ``npx skills
add`` installs from GitHub). The wheel carries the same files as
``deweloperuch_mcp/skills/deweloperuch-cli/`` (``[tool.hatch.build.targets.wheel]`` in
``pyproject.toml``); a source checkout, also an editable install, reads the repository's.
"""

import os
import secrets
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

SKILL = "deweloperuch-cli"
MAIN = "SKILL.md"
"""The file an agent reads first: front matter (name, description) and instructions."""
_PACKAGE = Path(__file__).resolve().parents[1]
PACKAGED = _PACKAGE / "skills" / SKILL
"""The skill in an installed wheel."""
CHECKOUT = _PACKAGE.parents[1] / "skills" / SKILL
"""The skill in a source checkout (``src/deweloperuch_mcp`` -> the repository's root)."""

SkillAgent = Literal["claude-code", "codex", "cursor", "gemini-cli", "github-copilot"]
"""Agents whose skills folders the installer knows, named as the ``skills`` CLI
(vercel-labs, ``npx skills add --agent``) names them."""
AGENT_FOLDERS: dict[str, tuple[str, str]] = {
    "claude-code": (".claude/skills", ".claude/skills"),
    "codex": (".agents/skills", ".agents/skills"),
    "cursor": (".agents/skills", ".cursor/skills"),
    "gemini-cli": (".agents/skills", ".gemini/skills"),
    "github-copilot": (".agents/skills", ".copilot/skills"),
}
"""Each agent's skills folder in a project and in the home folder, as the ``skills`` CLI
1.7.2 installs them (its table of agents; ``codex`` reads ``~/.agents/skills``)."""
DEFAULT_AGENT = "claude-code"


class SkillInstallRefusedError(Exception):
    """Arguments that place the skill nowhere clear, or a different copy without
    ``force``; nothing was written. ``str(err)`` says what to fix."""


class CopyBefore(StrEnum):
    """What the target folder held of the skill before installing."""

    NONE = "none"
    """None of the skill's files."""
    SAME = "same"
    """Every file of the skill, with the same text."""
    DIFFERENT = "different"
    """Some file of the skill missing or with another text (edited, another version)."""


@dataclass(frozen=True)
class SkillInstallation:
    """The skill's folder after installing, its files and what was there before."""

    folder: Path
    files: tuple[str, ...]
    before: CopyBefore


class AgentSkillInstaller:
    """The packaged skill (from ``source``: by default the wheel's copy, else the
    checkout's) and its copies in agents' skills folders, under the home folder or the
    current folder. ``OSError`` when a file cannot be read or written."""

    def __init__(self, source: Path | None = None) -> None:
        self._source = source

    def path(self) -> Path:
        """The folder the package ships the skill in."""
        folder = self._source or (PACKAGED if PACKAGED.is_dir() else CHECKOUT)
        if not (folder / MAIN).is_file():
            raise FileNotFoundError(f"Brak pliku skilla w pakiecie: {folder / MAIN}")
        return folder

    def show(self) -> str:
        """The text of ``SKILL.md``."""
        return (self.path() / MAIN).read_text(encoding="utf-8")

    def install(
        self,
        *,
        agent: str | None = None,
        project: bool = False,
        folder: str | None = None,
        force: bool = False,
    ) -> SkillInstallation:
        """Copy the skill's files into ``<skills folder>/deweloperuch-cli``: the folder of
        ``agent`` (default ``claude-code``) for the user or, with ``project``, the current
        project, or ``folder`` as given. A different copy there is replaced only with
        ``force``; other files of that folder stay."""
        target = self._target(agent, project, folder)
        source = self.path()
        files = {
            path.name: path.read_text(encoding="utf-8") for path in sorted(source.glob("*.md"))
        }
        before = self._existing_copy(target, files)
        if before is CopyBefore.DIFFERENT and not force:
            raise SkillInstallRefusedError(
                f"W {target} jest już inna wersja skilla {SKILL} (zmieniona, z innej wersji "
                "pakietu albo jako dowiązanie); nic nie zapisano. Żeby ją zastąpić, dodaj --force."
            )
        if before is not CopyBefore.SAME:
            self._write(target, files)
        return SkillInstallation(folder=target, files=tuple(files), before=before)

    @staticmethod
    def _target(agent: str | None, project: bool, folder: str | None) -> Path:
        if folder is not None:
            if agent is not None or project:
                raise SkillInstallRefusedError(
                    "Podaj --dir albo --agent/--project, nie razem: --dir to już katalog skilli."
                )
            if not folder.strip():
                raise SkillInstallRefusedError(
                    "--dir: podaj ścieżkę katalogu skilli, np. ~/.claude/skills."
                )
            return (Path(folder).expanduser() / SKILL).absolute()
        folders = AGENT_FOLDERS.get(agent or DEFAULT_AGENT)
        if folders is None:
            raise SkillInstallRefusedError(
                f"--agent: oczekiwano jednej z wartości {', '.join(AGENT_FOLDERS)}, podano "
                f"{agent!r}; dla innego agenta podaj jego katalog skilli w --dir."
            )
        in_project, in_home = folders
        base, path = (Path.cwd(), in_project) if project else (Path.home(), in_home)
        return (base / path / SKILL).absolute()

    @staticmethod
    def _existing_copy(target: Path, files: dict[str, str]) -> CopyBefore:
        """What ``target`` holds of ``files``. A symbolic link where a file of the skill
        goes, or a target folder that is a link to no folder, is a different copy: the
        installer never writes through a link (``_write`` replaces it with ``force``)."""
        if target.is_symlink() and not target.is_dir():
            return CopyBefore.DIFFERENT
        paths = [target / name for name in files]
        if any(path.is_symlink() or (path.exists() and not path.is_file()) for path in paths):
            return CopyBefore.DIFFERENT
        present = {
            path.name: path.read_text(encoding="utf-8", errors="replace")
            for path in paths
            if path.is_file()
        }
        if not present:
            return CopyBefore.NONE
        if present == files:
            return CopyBefore.SAME
        return CopyBefore.DIFFERENT

    @classmethod
    def _write(cls, target: Path, files: dict[str, str]) -> None:
        """Every file staged next to its place first, then each moved over it: an error
        while staging leaves the folder as it was, and a link in the way (the target
        folder or a file) is itself replaced, never written through."""
        if target.is_symlink():
            target.unlink()
        target.mkdir(parents=True, exist_ok=True)
        staged: list[tuple[Path, Path]] = []
        try:
            for name, text in files.items():
                staged.append((cls._staged(target, name, text), target / name))
            for temporary, final in staged:
                os.replace(temporary, final)
        finally:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _staged(target: Path, name: str, text: str) -> Path:
        """``text`` in a new file of ``target`` (exclusive: never an existing file or link)."""
        temporary = target / f".{name}.{secrets.token_hex(6)}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(text)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return temporary
