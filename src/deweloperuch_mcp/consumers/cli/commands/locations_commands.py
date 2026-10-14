"""``deweloperuch locations search``: cities, districts and streets by name. The command
parses its request and executes the use case in a session (``call``: a package error
ends the run with its code), then hands the result to its presenter."""

from typing import Annotated

import typer

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.cli.presenters.search_locations_cli_presenter import (
    SearchLocationsCliPresenter,
)
from deweloperuch_mcp.consumers.cli.support.common import JsonFlag, call
from deweloperuch_mcp.usecases.search_locations import (
    SearchLocationsRequest,
    SearchLocationsResult,
)

locations_app = typer.Typer(help="Lokalizacje: miasta, dzielnice, ulice.", no_args_is_help=True)


@locations_app.command("search")
def locations_search(
    ctx: typer.Context,
    query: Annotated[
        str,
        typer.Argument(
            metavar="QUERY",
            help="Fragment nazwy miasta, dzielnicy lub ulicy (2–100 znaków), np. krak.",
        ),
    ],
    as_json: JsonFlag = False,
) -> None:
    """Znajdź miasta, dzielnice i ulice; podaje slug miasta do `offers search`."""

    def search(session: Session) -> SearchLocationsResult:
        request = SearchLocationsRequest.parse(query=query)
        return session.search_locations.execute(request)

    result = call(ctx, search)
    SearchLocationsCliPresenter(as_json=as_json).present(result)
