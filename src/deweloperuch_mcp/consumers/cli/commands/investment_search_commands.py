"""``deweloperuch investments search``: the investments of a city, or by a part of the name
across the country. The command parses its request and executes the use case in a session
(``call``: a package error ends the run with its code), then hands the result to its
presenter. It is registered in the ``investments`` group, with ``investments get``."""

from typing import Annotated

import typer

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.cli.presenters.search_investments_cli_presenter import (
    SearchInvestmentsCliPresenter,
)
from deweloperuch_mcp.consumers.cli.support.common import JsonFlag, call
from deweloperuch_mcp.consumers.shared.choices import InvestmentSortChoice
from deweloperuch_mcp.models.investment_summary import DEFAULT_INVESTMENTS_LIMIT
from deweloperuch_mcp.usecases.search_investments import (
    SearchInvestmentsRequest,
    SearchInvestmentsResult,
)


def investments_search(
    ctx: typer.Context,
    city: Annotated[
        str | None,
        typer.Argument(
            metavar="[CITY]",
            help="Slug miasta (np. sopot; podaje go `locations search`). Bez CITY podaj --name.",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name", help="Fragment nazwy inwestycji (2–100 znaków); bez CITY w całej Polsce."
        ),
    ] = None,
    developer: Annotated[
        str | None,
        typer.Option("--developer", metavar="SLUG", help="Slug dewelopera; tylko z CITY."),
    ] = None,
    sort: Annotated[
        InvestmentSortChoice | None,
        typer.Option(help="Kolejność; tylko z CITY. Domyślnie najwięcej aktywnych ofert."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(help="Najwięcej pokazanych inwestycji, 1–500 (po samej nazwie do 50)."),
    ] = DEFAULT_INVESTMENTS_LIMIT,
    as_json: JsonFlag = False,
) -> None:
    """Szukaj inwestycji w mieście albo po nazwie (w całej Polsce)."""

    def search(session: Session) -> SearchInvestmentsResult:
        request = SearchInvestmentsRequest.parse(
            city=city, name=name, developer_slug=developer, sort=sort, limit=limit
        )
        return session.search_investments.execute(request)

    result = call(ctx, search)
    SearchInvestmentsCliPresenter(as_json=as_json).present(result)
