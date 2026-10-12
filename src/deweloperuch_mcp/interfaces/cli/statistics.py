"""``deweloperuch stats government``: GUS and NBP statistics of a location; ``--json``
prints the view's dataclasses as JSON."""

import dataclasses
import json
from typing import Annotated

import typer

from deweloperuch_mcp.application import arguments
from deweloperuch_mcp.domain.statistics import DEFAULT_PERIODS, Dataset
from deweloperuch_mcp.interfaces import views
from deweloperuch_mcp.interfaces.cli.common import JsonFlag, call
from deweloperuch_mcp.interfaces.cli.text import format_government_statistics

stats_app = typer.Typer(help="Statystyki rządowe: GUS i NBP.", no_args_is_help=True)


@stats_app.command("government")
def stats_government(
    ctx: typer.Context,
    location: Annotated[
        str,
        typer.Argument(
            metavar="LOCATION",
            help=(
                "polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo miasto na "
                "prawach powiatu bez polskich znaków, np. warszawa, bielsko-biala."
            ),
        ),
    ],
    dataset: Annotated[Dataset, typer.Argument(metavar="DATASET", help="Zestaw danych.")],
    periods: Annotated[
        int,
        typer.Option("--periods", help="Ile ostatnich okresów pokazać (lat, kwartałów, miesięcy)."),
    ] = DEFAULT_PERIODS,
    as_json: JsonFlag = False,
) -> None:
    """Pokaż statystyki GUS i NBP lokalizacji jako tabelę okresów i wartości."""
    result = call(
        ctx,
        lambda session: views.government_statistics(
            session.get_government_statistics(
                *arguments.government_statistics(location, dataset, periods=periods)
            )
        ),
    )
    if as_json:
        typer.echo(json.dumps(dataclasses.asdict(result), ensure_ascii=False, indent=2))
    else:
        typer.echo(format_government_statistics(result))
