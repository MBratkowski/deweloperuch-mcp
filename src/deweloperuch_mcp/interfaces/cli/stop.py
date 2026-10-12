"""The STOP record of the shared limiter, offline: ``status`` and ``clear``.

``status`` answers at once, without the limiter's lock: it exits with 3 while the
record holds requests back (also one that will end, and an unreadable one), else 0.
``clear`` waits for the lock (a note on stderr after ``STOP_LOCK_NOTICE`` s), removes
the record (for people, after checking the cause) and exits with 0, also when there was
nothing to remove; with 1 when the lock does not come within ``STOP_LOCK_WAIT`` s or
the record cannot be removed (nothing removed). The texts may show times, sources and
how to lift the STOP: they are for people; what a model reads elsewhere never says
that."""

import json
from typing import Annotated

import typer

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.interfaces.cli.common import ExitCode
from deweloperuch_mcp.interfaces.cli.text import format_stop_clear, format_stop_status
from deweloperuch_mcp.interfaces.text import printable

stop_app = typer.Typer(
    help=(
        "Blokada STOP: po 401, 403, 429 albo challenge Cloudflare żaden proces (CLI, serwer "
        "MCP, recon) nie wysyła zapytań. Działa offline."
    ),
    no_args_is_help=True,
)


STOP_LOCK_WAIT = 300.0
"""Longest wait of ``stop clear`` for the limiter's lock; then exit 1, nothing removed."""

STOP_LOCK_NOTICE = 2.0
"""Wait of ``stop clear`` for the lock after which it says on stderr that it waits."""

STOP_LOCK_WAITING = (
    "Czekam na zamek limitera: inny proces wysyła zapytanie albo czeka na swoją kolej."
)


@stop_app.command("status")
def stop_status(
    as_json: Annotated[bool, typer.Option("--json", help="Wypisz stan blokady jako JSON.")] = False,
) -> None:
    """Pokaż blokadę STOP; kod 3, gdy wstrzymuje zapytania (także wygasająca), 0, gdy nie."""
    state = bootstrap.stop_status()  # never waits; an unreadable record is a STOP (3)
    if as_json:
        typer.echo(json.dumps(state.to_json(), ensure_ascii=False, indent=2))
    else:
        typer.echo(format_stop_status(state))
    if state.active:
        raise typer.Exit(ExitCode.STOP)


@stop_app.command("clear")
def stop_clear() -> None:
    """Zdejmij blokadę STOP. Tylko człowiek, po sprawdzeniu przyczyny (`stop status`)."""
    try:
        before = bootstrap.clear_stop(
            wait_limit=STOP_LOCK_WAIT,
            notice_after=STOP_LOCK_NOTICE,
            on_wait=lambda: typer.echo(STOP_LOCK_WAITING, err=True),
        )
    except bootstrap.LockWaitTimeout as err:
        typer.echo(f"Błąd: {err}", err=True)
        raise typer.Exit(ExitCode.UNEXPECTED) from None
    except OSError as err:
        typer.echo(f"Błąd: nie udało się zdjąć zapisu STOP: {printable(str(err))}", err=True)
        raise typer.Exit(ExitCode.UNEXPECTED) from None
    typer.echo(format_stop_clear(before))
