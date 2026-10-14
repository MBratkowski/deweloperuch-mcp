"""``AgentSkillCliPresenter``: the ``skill`` commands for people: where ``install`` put
the skill and how an agent gets to use it, ``show`` (``SKILL.md`` as it is) and ``path``
(one line, for scripts)."""

from pathlib import Path

import typer

from deweloperuch_mcp.consumers.shared.text import printable
from deweloperuch_mcp.tooling.agent_skill_installer import (
    SKILL,
    CopyBefore,
    SkillInstallation,
)

USAGE = (
    "Agent wczyta go w nowej sesji i sam użyje przy pytaniach o ceny mieszkań, oferty "
    "deweloperów albo ceny transakcyjne.\n"
    "Treść skilla: deweloperuch skill show · polecenia CLI bez instalacji: "
    "uvx --from deweloperuch-mcp deweloperuch --help"
)


class AgentSkillCliPresenter:
    """The agent skill's commands as Polish text."""

    def installed(self, installation: SkillInstallation) -> None:
        typer.echo(f"{self._outcome(installation)}\n{USAGE}")

    def instructions(self, text: str) -> None:
        typer.echo(text, nl=False)

    def location(self, folder: Path) -> None:
        typer.echo(str(folder))

    @staticmethod
    def _outcome(installation: SkillInstallation) -> str:
        folder, files = printable(str(installation.folder)), ", ".join(installation.files)
        match installation.before:
            case CopyBefore.SAME:
                return f"Skill {SKILL} w {folder} jest już aktualny; nic nie zapisano."
            case CopyBefore.DIFFERENT:
                return f"Zastąpiono skill {SKILL} w {folder} wersją z pakietu (pliki: {files})."
            case CopyBefore.NONE:
                return f"Zainstalowano skill {SKILL} w {folder} (pliki: {files})."
