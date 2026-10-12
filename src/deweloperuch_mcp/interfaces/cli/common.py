"""What every command of ``deweloperuch`` shares: running an operation in a session, the
exit codes (public API), and printing a result as text or as JSON (``--json``)."""

from collections.abc import Callable
from enum import IntEnum
from typing import Annotated, TypeVar

import typer
from pydantic import BaseModel

from deweloperuch_mcp.bootstrap import Session, new_session
from deweloperuch_mcp.domain.errors import (
    DeweloperuchError,
    InvalidInputError,
    LimiterWaitError,
    NotFoundError,
    ServiceBlockedError,
    ServiceError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.interfaces.text import printable


class ExitCode(IntEnum):
    """Exit codes of ``deweloperuch`` (public API)."""

    OK = 0
    UNEXPECTED = 1
    """Any other error, e.g. ``SessionClosedError`` or a bug (with a traceback)."""
    INVALID_INPUT = 2
    """``InvalidInputError``, and wrong types or enum values (typer's usage errors)."""
    STOP = 3
    """``ServiceBlockedError`` and ``RateLimitedError``: stop and tell the user."""
    SERVICE_ERROR = 4
    LIMITER_WAIT = 5
    UNEXPECTED_RESPONSE = 6
    NOT_FOUND = 7


# Subclasses before their bases: UnexpectedResponseError is a ServiceError.
_EXIT_CODES: tuple[tuple[type[DeweloperuchError], ExitCode], ...] = (
    (InvalidInputError, ExitCode.INVALID_INPUT),
    (ServiceBlockedError, ExitCode.STOP),
    (UnexpectedResponseError, ExitCode.UNEXPECTED_RESPONSE),
    (ServiceError, ExitCode.SERVICE_ERROR),
    (LimiterWaitError, ExitCode.LIMITER_WAIT),
    (NotFoundError, ExitCode.NOT_FOUND),
)


# The STOP is recorded for every process (CLI, MCP server, recon), so a shell loop stops
# too; the advice still says it, and never how to remove the record (that is for people).
STOP_ADVICE = (
    "Nie uruchamiaj kolejnych poleceń deweloperuch ani pętli: przerwij i zgłoś to "
    "użytkownikowi. Blokada obejmuje też inne procesy."
)


def exit_code(error: DeweloperuchError) -> ExitCode:
    return next(
        (code for kind, code in _EXIT_CODES if isinstance(error, kind)), ExitCode.UNEXPECTED
    )


JsonFlag = Annotated[bool, typer.Option("--json", help="Wypisz wynik jako JSON (model domenowy).")]
R = TypeVar("R", bound=BaseModel)
T = TypeVar("T")


def call(ctx: typer.Context, operation: Callable[[Session], T]) -> T:
    """Run ``operation`` in a new session; a package error ends the run with its code.

    The session comes from ``bootstrap.new_session``; ``ctx.obj`` may be a session
    factory instead (tests pass one with a fast limiter).
    """
    open_session: Callable[[], Session] = ctx.obj if callable(ctx.obj) else new_session
    try:
        with open_session() as session:
            return operation(session)
    except DeweloperuchError as err:
        code = exit_code(err)
        typer.echo(f"Błąd: {err}", err=True)
        if err.detail:
            typer.echo(f"Szczegóły: {printable(err.detail)}", err=True)
        if code is ExitCode.STOP:
            typer.echo(STOP_ADVICE, err=True)
        raise typer.Exit(code) from None


def show(result: R, as_json: bool, text: Callable[[R], str]) -> None:
    typer.echo(result.model_dump_json(indent=2) if as_json else text(result))
