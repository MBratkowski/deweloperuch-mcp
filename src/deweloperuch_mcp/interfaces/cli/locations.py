"""``deweloperuch locations search``: cities, districts and streets by name."""

from typing import Annotated

import typer

from deweloperuch_mcp.application import arguments
from deweloperuch_mcp.interfaces import views
from deweloperuch_mcp.interfaces.cli.common import JsonFlag, call, show
from deweloperuch_mcp.interfaces.cli.text import format_locations

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
    result = call(
        ctx,
        lambda session: views.location_search(
            session.search_locations(arguments.location_query(query))
        ),
    )
    show(result, as_json, format_locations)
