"""``deweloperuch developers get`` and ``developers search``: each command parses its request
and executes the use case in a session (``call``: a package error ends the run with its
code), then hands the result to its presenter."""

from typing import Annotated

import typer

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.cli.presenters.get_developer_cli_presenter import (
    GetDeveloperCliPresenter,
)
from deweloperuch_mcp.consumers.cli.presenters.search_developers_cli_presenter import (
    SearchDevelopersCliPresenter,
)
from deweloperuch_mcp.consumers.cli.support.common import JsonFlag, call
from deweloperuch_mcp.models.developer_match import DEFAULT_MATCHES
from deweloperuch_mcp.models.developer_profile import DEFAULT_INVESTMENTS_LIMIT
from deweloperuch_mcp.models.values import WHOLE_COUNTRY
from deweloperuch_mcp.usecases.get_developer import GetDeveloperRequest, GetDeveloperResult
from deweloperuch_mcp.usecases.search_developers import (
    SearchDevelopersRequest,
    SearchDevelopersResult,
)

developers_app = typer.Typer(help="Deweloperzy.", no_args_is_help=True)


@developers_app.command("get")
def developers_get(
    ctx: typer.Context,
    slug: Annotated[
        str,
        typer.Argument(
            metavar="SLUG",
            help=(
                "Slug dewelopera (z `developers search` albo pole developer_slug "
                "z `offers search`)."
            ),
        ),
    ],
    city: Annotated[
        str,
        typer.Option("--city", help="Slug miasta (np. krakow) albo polska, czyli cała Polska."),
    ] = WHOLE_COUNTRY,
    limit: Annotated[
        int,
        typer.Option(help="Najwięcej pokazanych inwestycji (najpierw z największą liczbą ofert)."),
    ] = DEFAULT_INVESTMENTS_LIMIT,
    as_json: JsonFlag = False,
) -> None:
    """Pokaż dewelopera z jego inwestycjami i miastami."""

    def get(session: Session) -> GetDeveloperResult:
        request = GetDeveloperRequest.parse(developer_slug=slug, city=city, limit=limit)
        return session.get_developer.execute(request)

    result = call(ctx, get)
    GetDeveloperCliPresenter(as_json=as_json).present(result)


@developers_app.command("search")
def developers_search(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(metavar="NAME", help="Fragment nazwy dewelopera (2–100 znaków), np. atal."),
    ],
    limit: Annotated[
        int, typer.Option(help="Najwięcej pokazanych deweloperów (1–20).")
    ] = DEFAULT_MATCHES,
    as_json: JsonFlag = False,
) -> None:
    """Znajdź deweloperów po nazwie; podaje slug dewelopera do `developers get`."""

    def search(session: Session) -> SearchDevelopersResult:
        request = SearchDevelopersRequest.parse(name=name, limit=limit)
        return session.search_developers.execute(request)

    result = call(ctx, search)
    SearchDevelopersCliPresenter(as_json=as_json).present(result)
