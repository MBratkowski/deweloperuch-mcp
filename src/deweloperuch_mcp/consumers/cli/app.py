"""``deweloperuch``: the command line over the use cases (D13)::

    deweloperuch locations search QUERY [--json]
    deweloperuch offers search CITY [--price-min N] [--price-max N] [--area-min N]
        [--area-max N] [--price-per-m2-min N] [--price-per-m2-max N] [--district NAME]
        [--price-dropped] [--status active|archived|all] [--sort SORT] [--page N]
        [--per-page 10|50|100] [--json]
    deweloperuch offers get OFFER_ID --investment SLUG [--json]
    deweloperuch investments get SLUG [--history] [--limit N] [--json]
    deweloperuch investments search [CITY] [--name TEXT] [--developer SLUG] [--sort ORDER]
        [--limit N] [--json]
    deweloperuch developers get SLUG [--city CITY] [--limit N] [--json]
    deweloperuch developers search NAME [--limit N] [--json]
    deweloperuch buildings get SLUG [--limit N] [--trend] [--json]
    deweloperuch valuation estimate --lat LAT --lng LNG --area M2 [--address TEXT]
        [--limit N] [--json]
    deweloperuch stats market CITY [--price-min N] [--price-max N] [--area-min N]
        [--area-max N] [--top N] [--json]
    deweloperuch stats transactions CITY [--granularity month|quarter] [--periods N] [--json]
    deweloperuch stats cities [--level city|powiat] [--sort transactions_desc|
        price_per_m2_desc|price_per_m2_asc] [--limit N] [--min-transactions N] [--json]
    deweloperuch stats government LOCATION DATASET [--periods N] [--json]
    deweloperuch stop status [--json]
    deweloperuch stop clear
    deweloperuch skill install [--agent AGENT] [--project | --user] [--dir PATH] [--force]
    deweloperuch skill show
    deweloperuch skill path

A thin layer: typer checks types and enums, the application checks everything else
(``<Op>Request.parse`` with ``usecases.support.arguments``: its messages say what to fix).
Each run opens one session (``bootstrap.new_session``) and closes it. Text for people by
default (Polish); ``--json`` prints the result's view (``consumers/shared/*_views``).
Errors of the package go to stderr without a traceback and end the run with the codes of
``ExitCode``. Commands live in one module per command group (``commands/``); ``stop`` and
``skill`` work offline and open no session.
"""

import typer

from deweloperuch_mcp.consumers.cli.commands.buildings_commands import buildings_app
from deweloperuch_mcp.consumers.cli.commands.developers_commands import developers_app
from deweloperuch_mcp.consumers.cli.commands.investments_commands import investments_app
from deweloperuch_mcp.consumers.cli.commands.locations_commands import locations_app
from deweloperuch_mcp.consumers.cli.commands.offers_commands import offers_app
from deweloperuch_mcp.consumers.cli.commands.skill_commands import skill_app
from deweloperuch_mcp.consumers.cli.commands.stats_cities_commands import stats_cities
from deweloperuch_mcp.consumers.cli.commands.stats_commands import stats_app
from deweloperuch_mcp.consumers.cli.commands.stats_transactions_commands import stats_transactions
from deweloperuch_mcp.consumers.cli.commands.stop_commands import stop_app
from deweloperuch_mcp.consumers.cli.commands.valuation_commands import valuation_app

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
stats_app.command("transactions")(stats_transactions)
stats_app.command("cities")(stats_cities)
app.add_typer(locations_app, name="locations")
app.add_typer(offers_app, name="offers")
app.add_typer(investments_app, name="investments")
app.add_typer(developers_app, name="developers")
app.add_typer(buildings_app, name="buildings")
app.add_typer(valuation_app, name="valuation")
app.add_typer(stats_app, name="stats")
app.add_typer(stop_app, name="stop")
app.add_typer(skill_app, name="skill")


def main() -> None:
    """Entry point of the ``deweloperuch`` script."""
    app()
