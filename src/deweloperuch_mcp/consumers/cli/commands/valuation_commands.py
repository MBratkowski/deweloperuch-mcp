"""``deweloperuch valuation estimate``: the value of a flat from the RCN transactions nearby.
The command parses its request and executes the use case in a session (``call``: a
package error ends the run with its code), then hands the result to its presenter."""

from typing import Annotated

import typer

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.cli.presenters.estimate_property_value_cli_presenter import (
    EstimatePropertyValueCliPresenter,
)
from deweloperuch_mcp.consumers.cli.support.common import JsonFlag, call
from deweloperuch_mcp.usecases.estimate_property_value import (
    EstimatePropertyValueRequest,
    EstimatePropertyValueResult,
)

valuation_app = typer.Typer(
    help="Wycena mieszkania z cen transakcyjnych (RCN) w okolicy.", no_args_is_help=True
)


@valuation_app.command("estimate")
def valuation_estimate(
    ctx: typer.Context,
    lat: Annotated[
        float,
        typer.Option("--lat", help="Szerokość geograficzna punktu w Polsce, np. 52.2297."),
    ],
    lng: Annotated[
        float,
        typer.Option("--lng", help="Długość geograficzna punktu w Polsce, np. 21.0122."),
    ],
    area: Annotated[
        float, typer.Option("--area", help="Metraż mieszkania w m², 10–500, np. 48.5.")
    ],
    address: Annotated[
        str | None,
        typer.Option(
            "--address", help="Opcjonalny opis adresu; położenie wyznaczają --lat i --lng."
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            help="Najwięcej pokazanych transakcji porównawczych (najbliższe); domyślnie wszystkie."
        ),
    ] = None,
    as_json: JsonFlag = False,
) -> None:
    """Oszacuj wartość mieszkania z transakcji w okolicy punktu (przybliżenie, nie operat)."""

    def estimate(session: Session) -> EstimatePropertyValueResult:
        request = EstimatePropertyValueRequest.parse(
            lat=lat, lng=lng, area_m2=area, address=address, limit=limit
        )
        return session.estimate_property_value.execute(request)

    result = call(ctx, estimate)
    EstimatePropertyValueCliPresenter(as_json=as_json).present(result)
