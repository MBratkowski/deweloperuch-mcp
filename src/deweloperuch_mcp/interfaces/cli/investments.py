"""``deweloperuch investments get``: an investment with its developer and offers."""

from typing import Annotated

import typer

from deweloperuch_mcp.application import arguments
from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.interfaces import views
from deweloperuch_mcp.interfaces.cli.common import JsonFlag, call, show
from deweloperuch_mcp.interfaces.cli.text import format_investment

investments_app = typer.Typer(help="Inwestycje deweloperskie.", no_args_is_help=True)


def _investment(session: Session, slug: str, history: bool, limit: int | None) -> views.Investment:
    given = arguments.investment(slug, include_history=history, limit=limit)
    found = session.get_investment(
        given.investment, include_history=given.include_history, limit=given.limit
    )
    return views.investment(found)


@investments_app.command("get")
def investments_get(
    ctx: typer.Context,
    slug: Annotated[
        str,
        typer.Argument(metavar="SLUG", help="Slug inwestycji (investment_slug z `offers search`)."),
    ],
    history: Annotated[
        bool, typer.Option("--history", help="Dołącz historię ceny każdej oferty (wolniej).")
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option(help="Najwięcej pokazanych ofert (najpierw aktywne); domyślnie wszystkie."),
    ] = None,
    as_json: JsonFlag = False,
) -> None:
    """Pokaż inwestycję z deweloperem i ofertami."""
    result = call(ctx, lambda session: _investment(session, slug, history, limit))
    show(result, as_json, format_investment)
