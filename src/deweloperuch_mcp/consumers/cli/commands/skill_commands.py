"""The agent skill ``deweloperuch-cli`` (how AI agents use this CLI), offline: ``install``,
``show`` and ``path``.

The recommended install is the ``skills`` CLI from GitHub, for any agent; ``install`` is
the way without Node.js. Tooling, not a business operation: each command calls
``tooling.AgentSkillInstaller`` directly (no session, no use case) and hands the outcome
to ``AgentSkillCliPresenter``. Arguments that place the skill nowhere clear, or a copy
that differs without ``--force``, end with 2; files that cannot be read or written with 1.
"""

from collections.abc import Callable
from typing import Annotated, NoReturn, TypeVar

import typer

from deweloperuch_mcp.consumers.cli.presenters.agent_skill_cli_presenter import (
    AgentSkillCliPresenter,
)
from deweloperuch_mcp.consumers.cli.support.common import ExitCode
from deweloperuch_mcp.consumers.shared.text import printable
from deweloperuch_mcp.tooling.agent_skill_installer import (
    AgentSkillInstaller,
    SkillAgent,
    SkillInstallRefusedError,
)

T = TypeVar("T")

skill_app = typer.Typer(
    help=(
        "Skill deweloperuch-cli dla agentów AI (Claude Code, Codex, Cursor i innych): jak "
        "używać tego CLI. Zalecana instalacja: npx skills add MBratkowski/deweloperuch-mcp "
        "(wybierasz agenta); bez Node.js: deweloperuch skill install. Działa offline."
    ),
    no_args_is_help=True,
)


@skill_app.command("install")
def skill_install(
    agent: Annotated[
        SkillAgent | None,
        typer.Option(
            help=(
                "Agent, w którego katalogu skilli zapisać (nazwy jak w npx skills add "
                "--agent); domyślnie claude-code."
            ),
        ),
    ] = None,
    project: Annotated[
        bool,
        typer.Option(
            "--project/--user",
            help=(
                "--project: skille bieżącego projektu (np. ./.claude/skills); --user: skille "
                "użytkownika (np. ~/.claude/skills)."
            ),
        ),
    ] = False,
    folder: Annotated[
        str | None,
        typer.Option(
            "--dir",
            metavar="PATH",
            help="Inny katalog skilli: zapisz do PATH/deweloperuch-cli (bez --agent i --project).",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Zastąp kopię skilla, która różni się od tej z pakietu."),
    ] = False,
) -> None:
    """Zainstaluj skill deweloperuch-cli w katalogu skilli agenta (bez Node.js)."""
    installer = AgentSkillInstaller()
    installation = _run(
        lambda: installer.install(agent=agent, project=project, folder=folder, force=force),
        "nie udało się zainstalować skilla",
    )
    AgentSkillCliPresenter().installed(installation)


@skill_app.command("show")
def skill_show() -> None:
    """Wypisz SKILL.md: instrukcje skilla dla agenta."""
    text = _run(AgentSkillInstaller().show, "nie udało się odczytać skilla z pakietu")
    AgentSkillCliPresenter().instructions(text)


@skill_app.command("path")
def skill_path() -> None:
    """Pokaż katalog skilla w zainstalowanym pakiecie."""
    folder = _run(AgentSkillInstaller().path, "nie udało się odczytać skilla z pakietu")
    AgentSkillCliPresenter().location(folder)


def _run(action: Callable[[], T], failure: str) -> T:
    """``action``'s outcome; a refusal ends the run with 2, a file error with 1."""
    try:
        return action()
    except SkillInstallRefusedError as err:  # it may name a path: escaped like file errors
        _fail(printable(str(err)), ExitCode.INVALID_INPUT)
    except OSError as err:
        _fail(f"{failure}: {printable(str(err))}", ExitCode.UNEXPECTED)


def _fail(message: str, code: ExitCode) -> NoReturn:
    typer.echo(f"Błąd: {message}", err=True)
    raise typer.Exit(code)
