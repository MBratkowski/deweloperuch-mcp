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
from support.builders.transactions import (
    karpacz_page,
    month_rows,
    months,
    page_with_months,
    stats_page,
    zero_month,
)
from support.providers.cli import Cli, ok
from support.providers.error_answers import removed_route, unknown_location_page
from support.providers.routes.offers import RSC_HEADERS
from support.providers.routes.transactions import STATS_PAGE, transaction_routes
from support.providers.rsc import OFFERS_WARSZAWA_20261031, raw

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


@pytest.fixture
def run(limiter: RequestLimiter) -> Cli:
    """``deweloperuch stats transactions ARGS`` in-process."""
    return Cli(limiter, prefix=("stats", "transactions"))


def test_cli_prints_months_as_a_table(run: Cli, service: respx.MockRouter) -> None:
    """Three months of the sample page.stats_transactions.v2_view on the real page."""
    transaction_routes(service, monthly=months(3))

    lines = ok(run("warszawa")).splitlines()

    assert lines[0] == "Ceny transakcyjne mieszkań (RCN) · warszawa · miesięcznie"
    assert lines[1] == "Okresy: pokazano 3 z 3 (dane od 2017-01)."
    assert lines[2].startswith("Uwaga: Ostatnie miesiące są niepełne")
    assert lines[3] == f"Strona na deweloperuch.pl: {stats_page('warszawa')}"
    assert lines[4:] == [
        "Okres    Transakcje  Mediana PLN/m²  Średnia PLN/m²  Mediana m²  Mediana ceny PLN",
        "2017-01         890           7 656           7 903        47,9           355 000",
        "2017-02         880           7 528           7 793        49,2           357 000",
        "2017-03       1 086           7 626           7 989          48           360 000",
    ]


def test_cli_shows_a_month_without_transactions_without_prices(
    run: Cli, service: respx.MockRouter
) -> None:
    """[P 2026-10-31] the page sends such a month with every measure 0 (Warsaw 2026-06);
    the text shows a dash, as for missing values of the government statistics."""
    first, _, third = month_rows(3)
    transaction_routes(service, monthly=page_with_months([first, zero_month("2017-02"), third]))

    lines = ok(run("warszawa")).splitlines()

    assert lines[-2] == (
        "2017-02           0               –               –           –                 –"
    )
    assert json.loads(ok(run("warszawa", "--json")))["periods"][1] == {
        "period": "2017-02",
        "transactions": 0,
        "incomplete": False,
        "median_price_per_m2": None,
        "average_price_per_m2": None,
        "median_area_m2": None,
        "average_area_m2": None,
        "median_price": None,
        "average_price": None,
    }


def test_cli_prints_quarters_with_the_median_only(run: Cli, service: respx.MockRouter) -> None:
    """[P 2026-10-30] the price of a quarter is its median: one column, the median's."""
    transaction_routes(service)

    lines = ok(run("warszawa", "--granularity", "quarter", "--periods", "2")).splitlines()

    assert lines[0].endswith("· kwartalnie")
    assert lines[2] == (
        "Wskazówka: Pokazano ostatnie 2 z 3 okresów (dane od 2017-Q1); starsze pokaże większa "
        "wartość periods."
    )
    assert lines[4] == f"Strona na deweloperuch.pl: {stats_page('warszawa')}"
    assert lines[5:] == [
        "Okres    Transakcje  Mediana PLN/m²",
        "2017-Q2       2 854           7 695",
        "2017-Q3       2 893           7 844",
    ]


def test_cli_json_is_the_whole_view(run: Cli, service: respx.MockRouter) -> None:
    transaction_routes(service, monthly=months(3))

    shown = json.loads(ok(run("warszawa", "--periods", "1", "--json")))

    assert list(shown) == list(TransactionStatisticsView.model_fields)
    assert shown["granularity"] == "month"
    assert shown["stats_url"] == stats_page("warszawa")
    # Three months are too little history to judge any of them.
    assert shown["last_complete_period"] is None
    assert shown["periods"] == [
        {
            "period": "2017-03",
            "transactions": 1086,
            "incomplete": False,
            "median_price_per_m2": 7626.0,
            "average_price_per_m2": 7989.0,
            "median_area_m2": 48.0,
            "average_area_m2": 53.0,
            "median_price": 360000.0,
            "average_price": 424490.0,
        }
    ]


def test_cli_json_of_quarters_has_the_median(run: Cli, service: respx.MockRouter) -> None:
    transaction_routes(service)

    shown = json.loads(ok(run("warszawa", "--granularity", "quarter", "--json")))

    assert shown["periods"][0] == {
        "period": "2017-Q1",
        "transactions": 2922,
        "incomplete": False,
        "median_price_per_m2": 7595.0,
        "average_price_per_m2": None,
        "median_area_m2": None,
        "average_area_m2": None,
        "median_price": None,
        "average_price": None,
    }


def test_cli_marks_the_incomplete_months_and_explains_the_mark(
    run: Cli, service: respx.MockRouter
) -> None:
    """tests/fixtures/rsc/stats_tx_warszawa_20261031.rsc: 2026-05, 2026-06 and 2026-07 have
    fewer than half the usual transactions; 2026-04 is the last complete month. The table
    ends with 2026-07, the newest month with transactions (the page's empty months after it
    are its padding)."""
    transaction_routes(service)

    lines = ok(run("warszawa", "--periods", "7")).splitlines()

    assert lines[1] == "Okresy: pokazano 7 z 115 (dane od 2017-01)."
    assert lines[2] == (
        "Wskazówka: Pokazano ostatnie 7 z 115 okresów (dane od 2017-01); starsze pokaże "
        "większa wartość periods. Okresy 2026-05, 2026-06 i 2026-07 mają mniej niż połowę "
        "zwykłej liczby transakcji (dane RCN jeszcze niepełne): nie wyciągaj wniosków z ich "
        "cen ani liczby transakcji. Ostatni okres ze zwykłą liczbą transakcji: 2026-04 (jego "
        "dane też mogą się jeszcze zmienić)."
    )
    assert lines[5:] == [
        "Okres      Transakcje  Mediana PLN/m²  Średnia PLN/m²  Mediana m²  Mediana ceny PLN",
        "2026-01         1 073          16 542          17 185        49,4           800 000",
        "2026-02         1 180          16 323          16 894        48,8           799 500",
        "2026-03         1 388          16 389          16 864        48,4           770 000",
        "2026-04           986          16 558          16 989        48,6           772 500",
        "2026-05 *          22          15 495          16 285        52,2           754 750",
        "2026-06 *           0               –               –           –                 –",
        "2026-07 *          35          33 176          31 187        53,4         1 360 209",
        "* okres niepełny: mniej niż połowa zwykłej liczby transakcji (dane RCN jeszcze niepełne).",
    ]


def test_cli_json_carries_the_incomplete_months(run: Cli, service: respx.MockRouter) -> None:
    transaction_routes(service)

    shown = json.loads(ok(run("warszawa", "--periods", "4", "--json")))

    assert shown["last_complete_period"] == "2026-04"
    assert [(item["period"], item["incomplete"]) for item in shown["periods"]] == [
        ("2026-04", False),
        ("2026-05", True),
        ("2026-06", True),
        ("2026-07", True),
    ]


@pytest.mark.parametrize(
    ("args", "code", "said"),
    [
        (["polska"], ExitCode.INVALID_INPUT, "nie polska"),
        (["7-miast"], ExitCode.INVALID_INPUT, "get_government_statistics"),
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
        # [P 2026-10-31] a city the page does not know: a 404 with a flight stream
        ({"status_code": 404, **unknown_location_page()}, ExitCode.NOT_FOUND),
        # D21: a removed page or a redirect is a changed service, never an unknown city
        ({"status_code": 404, **removed_route()}, ExitCode.UNEXPECTED_RESPONSE),
        (
            {"status_code": 308, "headers": {"Location": "/statystyki"}},
            ExitCode.UNEXPECTED_RESPONSE,
        ),
        (
            {"status_code": 200, "content": page_with_months([]), "headers": RSC_HEADERS},
            ExitCode.NOT_FOUND,
        ),
        (
            {
                "status_code": 200,
                "content": page_with_months([{**month_rows(1)[0], "secondary_count": 1}]),
                "headers": RSC_HEADERS,
            },
            ExitCode.UNEXPECTED_RESPONSE,
        ),
        (
            {"status_code": 200, "content": raw(OFFERS_WARSZAWA_20261031), "headers": RSC_HEADERS},
            ExitCode.UNEXPECTED_RESPONSE,
        ),
        ({"status_code": 503, "headers": {"Retry-After": "10"}}, ExitCode.SERVICE_ERROR),
        ({"status_code": 403}, ExitCode.STOP),
    ],
)
def test_cli_service_answers_map_to_exit_codes(
    run: Cli, service: respx.MockRouter, answer: dict[str, Any], code: ExitCode
) -> None:
    rest = dict(answer)
    service.get(path__regex=STATS_PAGE).respond(rest.pop("status_code"), **rest)

    result = run("warszawa")

    assert result.exit_code == code
    assert result.stderr.startswith("Błąd: ")
    assert "Traceback" not in result.stderr


def test_cli_help_lists_the_options_offline(run: Cli, service: respx.MockRouter) -> None:
    out = ok(run("--help"))

    for option in ("CITY", "--granularity", "month", "quarter", "--periods", "--json"):
        assert option in out
    assert "od 2017 r." in out and "rynek wtórny" in out and "agregatów" in out
    assert run.sessions == []


def test_cli_says_when_a_small_town_has_too_few_transactions(
    run: Cli, service: respx.MockRouter
) -> None:
    """tests/fixtures/rsc/stats_tx_karpacz_20261031.rsc: nothing is marked, and the hint
    says why."""
    transaction_routes(service, monthly=karpacz_page())

    out = ok(run("karpacz", "--periods", "3"))

    assert "Okresy: pokazano 3 z 108 (dane od 2017-01)." in out
    assert out.splitlines()[-1].startswith("2025-12 ")
    assert "Transakcji jest za mało, by ocenić, które najnowsze okresy są niepełne" in out
    assert " *" not in out
    assert json.loads(ok(run("karpacz", "--json")))["last_complete_period"] is None
