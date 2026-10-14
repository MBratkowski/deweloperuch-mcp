"""``deweloperuch buildings get``: a building of the price register with its units and
their transactions; ``--trend`` adds the price trend around it. The command parses its
request and executes the use case in a session (``call``: a package error ends the run
with its code), then hands the result to its presenter."""

from typing import Annotated

import typer

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.cli.presenters.get_building_cli_presenter import (
    GetBuildingCliPresenter,
)
from deweloperuch_mcp.consumers.cli.support.common import JsonFlag, call
from deweloperuch_mcp.usecases.get_building import GetBuildingRequest, GetBuildingResult

buildings_app = typer.Typer(
    help="Budynki z rejestru cen transakcyjnych (RCN): lokale i ich transakcje.",
    no_args_is_help=True,
)


@buildings_app.command("get")
def buildings_get(
    ctx: typer.Context,
    slug: Annotated[
        str,
        typer.Argument(
            metavar="SLUG",
            help=(
                "Slug budynku, np. 23-marca-79c-sopot: ostatni człon adresu strony budynku z "
                "cenami transakcyjnymi na deweloperuch.pl."
            ),
        ),
    ],
    limit: Annotated[
        int | None,
        typer.Option(
            help="Najwięcej pokazanych lokali (tych z najnowszymi transakcjami); domyślnie "
            "wszystkie."
        ),
    ] = None,
    trend: Annotated[
        bool,
        typer.Option(
            "--trend",
            help="Dołącz średnią cenę za m² transakcji w okolicy budynku, kwartał po kwartale "
            "(jedno zapytanie więcej).",
        ),
    ] = False,
    as_json: JsonFlag = False,
) -> None:
    """Pokaż budynek z lokalami i ich transakcjami (ceny transakcyjne, nie ofertowe).

    Lokale od tego z najnowszą transakcją, transakcje każdego lokalu od najstarszej.
    """

    def get(session: Session) -> GetBuildingResult:
        request = GetBuildingRequest.parse(building_slug=slug, limit=limit, include_trend=trend)
        return session.get_building.execute(request)

    result = call(ctx, get)
    GetBuildingCliPresenter(as_json=as_json).present(result)
