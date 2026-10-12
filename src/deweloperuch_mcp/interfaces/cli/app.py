"""``deweloperuch``: the command line over the use cases (D13)::

    deweloperuch locations search QUERY [--json]
    deweloperuch offers search CITY [--price-min N] [--price-max N] [--area-min N]
        [--area-max N] [--sort price_asc|price_desc] [--page N] [--per-page 10|50|100] [--json]
    deweloperuch offers get OFFER_ID --investment SLUG [--json]
    deweloperuch investments get SLUG [--history] [--limit N] [--json]
    deweloperuch stats government LOCATION DATASET [--periods N] [--json]
    deweloperuch stop status [--json]
    deweloperuch stop clear

A thin layer: typer checks types and enums, the application checks everything else
(``application.arguments``: its messages say what to fix). Each run opens one session
(``bootstrap.new_session``) and closes it. Text for people by default (Polish); ``--json``
prints the result's view (``interfaces.views``). Errors of the package go to stderr
without a traceback and end the run with the codes of ``ExitCode``. Commands live in one
module per capability; ``stop`` works offline and opens no session.
"""

import typer

from deweloperuch_mcp.interfaces.cli.investments import investments_app
from deweloperuch_mcp.interfaces.cli.locations import locations_app
from deweloperuch_mcp.interfaces.cli.offers import offers_app
from deweloperuch_mcp.interfaces.cli.statistics import stats_app
from deweloperuch_mcp.interfaces.cli.stop import stop_app

app = typer.Typer(
    name="deweloperuch",
    help=(
        "Ceny ofertowe mieszkań od deweloperów (rynek pierwotny) z deweloperuch.pl. "
        "Tylko odczyt; zapytania idą przez wspólny limiter (najwyżej 1 na sekundę)."
    ),
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)
app.add_typer(locations_app, name="locations")
app.add_typer(offers_app, name="offers")
app.add_typer(investments_app, name="investments")
app.add_typer(stats_app, name="stats")
app.add_typer(stop_app, name="stop")


def main() -> None:
    """Entry point of the ``deweloperuch`` script."""
    app()
