"""Tests of ``deweloperuch_mcp.consumers.cli.commands.stats_transactions_commands``."""

import json
from typing import Any

import pytest
import respx

from deweloperuch_mcp.consumers.cli.support.common import ExitCode
from deweloperuch_mcp.consumers.shared.transaction_views import (
    TransactionStatisticsView,
)
from deweloperuch_mcp.throttle import RequestLimiter
from support.builders.transactions import STATS_PAGE, ZERO_MONTH, months
from support.providers.cli import Cli, ok
from support.providers.routes.transactions import (
    MONTHLY_PATH,
    transaction_routes,
)

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


@pytest.fixture
def run(limiter: RequestLimiter) -> Cli:
    """``deweloperuch stats transactions ARGS`` in-process."""
    return Cli(limiter, prefix=("stats", "transactions"))


def test_cli_prints_months_as_a_table(run: Cli, service: respx.MockRouter) -> None:
    transaction_routes(service)

    lines = ok(run("warszawa")).splitlines()

    assert lines[0] == "Ceny transakcyjne mieszkań (RCN) · warszawa · miesięcznie"
    assert lines[1] == "Okresy: pokazano 3 z 3 (dane od 2021-01)."
    assert lines[2].startswith("Uwaga: Ostatnie miesiące są niepełne")
    assert lines[3] == f"Strona na deweloperuch.pl: {STATS_PAGE}/warszawa"
    assert lines[4:] == [
        "Okres    Transakcje  Mediana PLN/m²  Średnia PLN/m²  Mediana m²  Mediana ceny PLN",
        "2021-01         963          10 651          10 876        49,4           502 000",
        "2021-02       1 165          10 575          10 854        48,8           495 000",
        "2021-03       1 327          10 858          10 981        48,5           510 000",
    ]


def test_cli_shows_a_month_without_transactions_without_prices(
    run: Cli, service: respx.MockRouter
) -> None:
    """[P 2026-10-13] live: Warsaw 2026-05 and 2026-06 came with every measure as 0;
    the text shows a dash, as for missing values of the government statistics."""
    data_with_zeros = months(3)
    data_with_zeros["data"][1].update(ZERO_MONTH)
    transaction_routes(service, monthly=data_with_zeros)

    lines = ok(run("warszawa")).splitlines()

    assert lines[-2] == (
        "2021-02           0               –               –           –                 –"
    )
    assert json.loads(ok(run("warszawa", "--json")))["periods"][1] == {
        "period": "2021-02",
        "transactions": 0,
        "median_price_per_m2": None,
        "average_price_per_m2": None,
        "median_area_m2": None,
        "average_area_m2": None,
        "median_price": None,
        "average_price": None,
    }


def test_cli_prints_quarters_with_their_columns_only(run: Cli, service: respx.MockRouter) -> None:
    transaction_routes(service)

    lines = ok(run("warszawa", "--granularity", "quarter", "--periods", "2")).splitlines()

    assert lines[0].endswith("· kwartalnie")
    assert lines[2] == (
        "Wskazówka: Pokazano ostatnie 2 z 3 okresów (dane od 2017-Q1); starsze pokaże większa "
        "wartość periods."
    )
    assert lines[4] == f"Strona na deweloperuch.pl: {STATS_PAGE}/warszawa"
    assert lines[5:] == [
        "Okres    Transakcje  Średnia PLN/m²",
        "2017-Q2       2 854           7 695",
        "2017-Q3       2 893           7 844",
    ]


def test_cli_json_is_the_whole_view(run: Cli, service: respx.MockRouter) -> None:
    transaction_routes(service)

    shown = json.loads(ok(run("warszawa", "--periods", "1", "--json")))

    assert list(shown) == list(TransactionStatisticsView.model_fields)
    assert shown["granularity"] == "month"
    assert shown["stats_url"] == STATS_PAGE + "/warszawa"
    assert shown["periods"] == [
        {
            "period": "2021-03",
            "transactions": 1327,
            "median_price_per_m2": 10858.0,
            "average_price_per_m2": 10981.0,
            "median_area_m2": 48.5,
            "average_area_m2": 53.7,
            "median_price": 510000.0,
            "average_price": 584959.0,
        }
    ]


@pytest.mark.parametrize(
    ("args", "code", "said"),
    [
        (["polska"], ExitCode.INVALID_INPUT, "nie polska"),
        (["warszawa", "--periods", "0"], ExitCode.INVALID_INPUT, "periods musi być"),
        (["warszawa", "--granularity", "year"], ExitCode.INVALID_INPUT, "--granularity"),
        (["warszawa", "--periods", "x"], ExitCode.INVALID_INPUT, "--periods"),
    ],
)
def test_cli_input_errors_exit_with_2_without_a_request(
    run: Cli, service: respx.MockRouter, args: list[str], code: ExitCode, said: str
) -> None:
    routes = transaction_routes(service)

    result = run(*args)

    assert result.exit_code == code
    assert said in result.stderr
    assert all(route.call_count == 0 for route in routes)


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        ({"status_code": 404}, ExitCode.NOT_FOUND),
        (
            {"status_code": 200, "json": {"scope": {"label": "city"}, "data": []}},
            ExitCode.NOT_FOUND,
        ),
        (
            {"status_code": 200, "json": {"scope": {"label": "powiat"}, "data": []}},
            ExitCode.UNEXPECTED_RESPONSE,
        ),
        ({"status_code": 503, "headers": {"Retry-After": "10"}}, ExitCode.SERVICE_ERROR),
        ({"status_code": 403}, ExitCode.STOP),
        ({"status_code": 200, "json": {"rows": []}}, ExitCode.UNEXPECTED_RESPONSE),
    ],
)
def test_cli_service_answers_map_to_exit_codes(
    run: Cli, service: respx.MockRouter, answer: dict[str, Any], code: ExitCode
) -> None:
    status = answer.pop("status_code")
    service.get(path=MONTHLY_PATH).respond(status, **answer)

    result = run("warszawa")

    assert result.exit_code == code
    assert result.stderr.startswith("Błąd: ")
    assert "Traceback" not in result.stderr


def test_cli_help_lists_the_options_offline(run: Cli, service: respx.MockRouter) -> None:
    out = ok(run("--help"))

    for option in ("CITY", "--granularity", "month", "quarter", "--periods", "--json"):
        assert option in out
    assert run.sessions == []
