"""``deweloperuch investments get``: an investment with its developer and offers; the
group also holds ``investments search`` (``cli.commands.investment_search_commands``). The
command parses its request and executes the use case in a session (``call``: a package error
ends the run with its code), then hands the result to its presenter."""

from typing import Annotated

import typer

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.cli.commands.investment_search_commands import investments_search
from deweloperuch_mcp.consumers.cli.presenters.get_investment_cli_presenter import (
    GetInvestmentCliPresenter,
)
from deweloperuch_mcp.consumers.cli.support.common import JsonFlag, call
from deweloperuch_mcp.usecases.get_investment import GetInvestmentRequest, GetInvestmentResult

investments_app = typer.Typer(help="Inwestycje deweloperskie.", no_args_is_help=True)


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

    def get(session: Session) -> GetInvestmentResult:
        request = GetInvestmentRequest.parse(
            investment_slug=slug, include_history=history, limit=limit
        )
        return session.get_investment.execute(request)

    result = call(ctx, get)
    GetInvestmentCliPresenter(as_json=as_json).present(result)


investments_app.command("search")(investments_search)
