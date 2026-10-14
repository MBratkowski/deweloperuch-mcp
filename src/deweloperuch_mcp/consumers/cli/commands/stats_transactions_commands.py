"""``deweloperuch stats transactions``: RCN transaction prices of flats in a city over time.
The command parses its request and executes the use case in a session (``call``: a package
error ends the run with its code), then hands the result to its presenter. Registered in
the ``stats`` group by ``consumers.cli.app``."""

from typing import Annotated

import typer

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.cli.presenters.get_transaction_statistics_cli_presenter import (
    GetTransactionStatisticsCliPresenter,
)
from deweloperuch_mcp.consumers.cli.support.common import JsonFlag, call
from deweloperuch_mcp.models.government_statistics import DEFAULT_PERIODS
from deweloperuch_mcp.models.transaction_series import Granularity
from deweloperuch_mcp.usecases.get_transaction_statistics import (
    GetTransactionStatisticsRequest,
    GetTransactionStatisticsResult,
)


def stats_transactions(
    ctx: typer.Context,
    city: Annotated[
        str,
        typer.Argument(
            metavar="CITY",
            help=(
                "Slug miasta bez polskich znaków, np. warszawa, krakow (podaje go "
                "deweloperuch locations search). Bez dzielnic, ulic i całej Polski."
            ),
        ),
    ],
    granularity: Annotated[
        Granularity,
        typer.Option(
            "--granularity",
            help=(
                "month: miesiące (mediany i średnie); quarter: kwartały (średnia cena za m², "
                "dłuższa historia)."
            ),
        ),
    ] = Granularity.MONTH,
    periods: Annotated[
        int, typer.Option("--periods", help="Ile ostatnich okresów pokazać (miesięcy, kwartałów).")
    ] = DEFAULT_PERIODS,
    as_json: JsonFlag = False,
) -> None:
    """Pokaż ceny transakcyjne mieszkań (RCN) w mieście, miesiąc po miesiącu albo kwartałami."""

    def get(session: Session) -> GetTransactionStatisticsResult:
        request = GetTransactionStatisticsRequest.parse(
            city=city, granularity=granularity, periods=periods
        )
        return session.get_transaction_statistics.execute(request)

    result = call(ctx, get)
    GetTransactionStatisticsCliPresenter(as_json=as_json).present(result)
