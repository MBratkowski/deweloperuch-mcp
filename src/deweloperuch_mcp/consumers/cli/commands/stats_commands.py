"""The ``deweloperuch stats`` group (``stats_app``) with ``stats government``, GUS and NBP
statistics of a location, and ``stats market``, the offer market of one city in numbers
(D15): each command parses its request and executes the use case in a session (``call``:
a package error ends the run with its code), then hands the result to its presenter."""

from typing import Annotated

import typer

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.cli.presenters.get_government_statistics_cli_presenter import (
    GetGovernmentStatisticsCliPresenter,
)
from deweloperuch_mcp.consumers.cli.presenters.get_market_statistics_cli_presenter import (
    GetMarketStatisticsCliPresenter,
)
from deweloperuch_mcp.consumers.cli.support.common import JsonFlag, call
from deweloperuch_mcp.models.government_statistics import DEFAULT_PERIODS, Dataset
from deweloperuch_mcp.models.market_statistics import DEFAULT_TOP_DEVELOPERS
from deweloperuch_mcp.usecases.get_government_statistics import (
    GetGovernmentStatisticsRequest,
    GetGovernmentStatisticsResult,
)
from deweloperuch_mcp.usecases.get_market_statistics import (
    GetMarketStatisticsRequest,
    GetMarketStatisticsResult,
)

stats_app = typer.Typer(
    help=(
        "Statystyki: rynek ofert miasta, ceny transakcyjne (RCN) miasta, ranking miast i "
        "powiatów oraz statystyki rządowe GUS i NBP."
    ),
    no_args_is_help=True,
)


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

    def get(session: Session) -> GetGovernmentStatisticsResult:
        request = GetGovernmentStatisticsRequest.parse(
            location=location, dataset=dataset, periods=periods
        )
        return session.get_government_statistics.execute(request)

    result = call(ctx, get)
    GetGovernmentStatisticsCliPresenter(as_json=as_json).present(result)


@stats_app.command("market")
def stats_market(
    ctx: typer.Context,
    city: Annotated[
        str,
        typer.Argument(
            metavar="CITY",
            help="Slug jednego miasta (np. krakow; podaje go `locations search`), nie polska.",
        ),
    ],
    price_min: Annotated[
        int | None, typer.Option("--price-min", help="Najniższa cena w PLN.")
    ] = None,
    price_max: Annotated[
        int | None, typer.Option("--price-max", help="Najwyższa cena w PLN.")
    ] = None,
    area_min: Annotated[
        int | None, typer.Option("--area-min", help="Najmniejszy metraż w m².")
    ] = None,
    area_max: Annotated[
        int | None, typer.Option("--area-max", help="Największy metraż w m².")
    ] = None,
    top: Annotated[
        int, typer.Option("--top", help="Ilu największych deweloperów pokazać (1–30).")
    ] = DEFAULT_TOP_DEVELOPERS,
    as_json: JsonFlag = False,
) -> None:
    """Pokaż statystyki aktywnych ofert miasta: ceny, metraże, największych deweloperów."""

    def get(session: Session) -> GetMarketStatisticsResult:
        request = GetMarketStatisticsRequest.parse(
            city=city,
            price_min=price_min,
            price_max=price_max,
            area_min=area_min,
            area_max=area_max,
            top_developers=top,
        )
        return session.get_market_statistics.execute(request)

    result = call(ctx, get)
    GetMarketStatisticsCliPresenter(as_json=as_json).present(result)
