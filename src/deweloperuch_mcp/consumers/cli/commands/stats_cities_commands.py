"""``deweloperuch stats cities``: cities or powiats ranked by their RCN transactions. The
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
from deweloperuch_mcp.consumers.shared.ranking_views import RankingLevelChoice, RankingSortChoice
from deweloperuch_mcp.models.location_ranking import DEFAULT_RANKING_LIMIT
from deweloperuch_mcp.usecases.rank_locations import RankLocationsRequest, RankLocationsResult


def stats_cities(
    ctx: typer.Context,
    level: Annotated[
        RankingLevelChoice,
        typer.Option(help="city: miejscowości (także małe); powiat: powiaty."),
    ] = "city",
    sort: Annotated[
        RankingSortChoice,
        typer.Option(help="Najwięcej transakcji albo po cenie za m² (malejąco, rosnąco)."),
    ] = "transactions_desc",
    limit: Annotated[
        int, typer.Option(help="Ile pierwszych pozycji pokazać, 1–100.")
    ] = DEFAULT_RANKING_LIMIT,
    min_transactions: Annotated[
        int,
        typer.Option(
            "--min-transactions",
            help="Pomiń miejsca z mniejszą liczbą transakcji (przy sortowaniu po cenie).",
        ),
    ] = 0,
    as_json: JsonFlag = False,
) -> None:
    """Pokaż ranking miejscowości albo powiatów według transakcji RCN."""

    def rank(session: Session) -> RankLocationsResult:
        request = RankLocationsRequest.parse(
            level=level, sort=sort, limit=limit, min_transactions=min_transactions
        )
        return session.rank_locations.execute(request)

    result = call(ctx, rank)
    RankLocationsCliPresenter(as_json=as_json).present(result)
