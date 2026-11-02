"""``deweloperuch stats cities``: cities or powiats ranked by their RCN transactions, or
cities by an official indicator. The
command parses its request and executes the use case in a session (``call``: a package
error ends the run with its code), then hands the result to its presenter. Registered in
the ``stats`` group by ``consumers.cli.app``."""

from typing import Annotated

import typer

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.cli.presenters.rank_locations_cli_presenter import (
    RankLocationsCliPresenter,
)
from deweloperuch_mcp.consumers.cli.support.common import JsonFlag, call
from deweloperuch_mcp.consumers.shared.ranking_views import (
    IndicatorChoice,
    RankingLevelChoice,
    RankingMarketChoice,
    RankingSortChoice,
)
from deweloperuch_mcp.models.location_ranking import DEFAULT_RANKING_LIMIT
from deweloperuch_mcp.usecases.rank_locations import RankLocationsRequest, RankLocationsResult


def stats_cities(
    ctx: typer.Context,
    level: Annotated[
        RankingLevelChoice,
        typer.Option(help="city: miejscowości (także małe); powiat: powiaty."),
    ] = "city",
    sort: Annotated[
        RankingSortChoice | None,
        typer.Option(
            help="Najwięcej transakcji (domyślnie), po cenie za m² (malejąco, rosnąco) albo, "
            "z --indicator, po wartości wskaźnika (value_desc domyślnie, value_asc).",
            show_default=False,
        ),
    ] = None,
    limit: Annotated[
        int, typer.Option(help="Ile pierwszych pozycji pokazać, 1–100.")
    ] = DEFAULT_RANKING_LIMIT,
    min_transactions: Annotated[
        int | None,
        typer.Option(
            "--min-transactions",
            help="Pomiń miejsca z mniejszą liczbą transakcji; domyślnie 20 przy sortowaniu po "
            "cenie, 0 po liczbie transakcji (0: wszystkie miejsca).",
        ),
    ] = None,
    market: Annotated[
        RankingMarketChoice | None,
        typer.Option(
            help="Tylko --level powiat: secondary (rynek wtórny, domyślnie), primary "
            "(pierwotny) albo all (oba rynki w zestawieniu serwisu).",
            show_default=False,
        ),
    ] = None,
    indicator: Annotated[
        IndicatorChoice | None,
        typer.Option(
            help="Ranking 66 miast na prawach powiatu według wskaźnika GUS albo NBP zamiast "
            "transakcji (bez --level powiat, --min-transactions i --market); average_wage to "
            "przeciętne miesięczne wynagrodzenie brutto, średnia za rok.",
            show_default=False,
        ),
    ] = None,
    as_json: JsonFlag = False,
) -> None:
    """Pokaż ranking miejscowości albo powiatów według transakcji RCN albo miast według
    wskaźnika GUS lub NBP."""

    def rank(session: Session) -> RankLocationsResult:
        request = RankLocationsRequest.parse(
            level=level,
            sort=sort,
            limit=limit,
            min_transactions=min_transactions,
            market=market,
            indicator=indicator,
        )
        return session.rank_locations.execute(request)

    result = call(ctx, rank)
    RankLocationsCliPresenter(as_json=as_json).present(result)
