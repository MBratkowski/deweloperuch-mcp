"""Tests of ``deweloperuch_mcp.consumers.cli.commands.stats_cities_commands``."""

import json

import pytest
import respx

from deweloperuch_mcp.consumers.cli.support.common import ExitCode
from deweloperuch_mcp.throttle import RequestLimiter
from support.builders.rankings import INJECTED, LEAKS, RANKING_PAGE, ranking_with_places
from support.providers.cli import run_cli
from support.providers.routes.rankings import CITY_RANKING, ranking_routes

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


CAVEAT = "Serwis nie podaje okresu ani tego, czy ceny i metraż to średnie, czy mediany."


def test_stats_cities_as_text(limiter: RequestLimiter, service: respx.MockRouter) -> None:
    ranking_routes(service)

    result = run_cli(limiter, "stats", "cities")

    assert result.exit_code == ExitCode.OK, result.output
    assert result.stdout.splitlines() == [
        "Ranking miejscowości wg liczby transakcji: pokazano 3 z 3.",
        f"Ranking miast na deweloperuch.pl: {RANKING_PAGE}",
        "1. Warszawa [warszawa] · transakcji: 3 606 · 16 413 PLN/m² · 48,8 m² · 780 000 PLN",
        "2. Kraków [krakow] · transakcji: 1 492 · 14 606 PLN/m² · 47,4 m² · 675 000 PLN",
        "3. Wrocław [wroclaw] · transakcji: 1 443 · 12 437 PLN/m² · 50,3 m² · 617 000 PLN",
        CAVEAT,
    ]


def test_stats_cities_of_powiats_from_the_cheapest(
    limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    ranking_routes(service)

    result = run_cli(
        limiter,
        "stats",
        "cities",
        "--level",
        "powiat",
        "--sort",
        "price_per_m2_asc",
        "--limit",
        "2",
        "--min-transactions",
        "200000",
    )

    assert result.exit_code == ExitCode.OK, result.output
    assert result.stdout.splitlines() == [
        "Ranking powiatów od najniższej ceny za m²: pokazano 2 z 2 (co najmniej 200 000 "
        "transakcji).",
        "1. powiat Kraków [id 14] · transakcji: 225 694 · 14 899 PLN/m² · 47,7 m² · 695 000 PLN",
        "2. powiat Warszawa [id 302] · transakcji: 351 314 · 16 367 PLN/m² · 48,6 m² · 780 000 PLN",
        CAVEAT,
    ]


def test_stats_cities_as_json_is_the_view(
    limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    ranking_routes(service)

    result = run_cli(limiter, "stats", "cities", "--limit", "1", "--json")

    assert result.exit_code == ExitCode.OK, result.output
    assert json.loads(result.stdout) == {
        "level": "city",
        "sort": "transactions_desc",
        "min_transactions": 0,
        "total": 3,
        "returned": 1,
        "truncated": True,
        "hint": "Pokazano pierwsze 1 z 3 miejscowości; kolejne pokaże większy limit "
        "(najwyżej 100).",
        "ranking_url": RANKING_PAGE,
        "items": [
            {
                "name": "Warszawa",
                "city_slug": "warszawa",
                "powiat_id": None,
                "transaction_count": 3606,
                "price_per_m2": 16413.0,
                "area_m2": 48.8,
                "price": 780000.0,
            }
        ],
    }


def test_names_from_the_service_are_escaped(
    limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    rows = ranking_with_places("api.city_tx_stats", 1)
    rows[0]["city"] = "Warszawa\x1b[2J"
    ranking_routes(service, cities=rows)

    result = run_cli(limiter, "stats", "cities")

    assert result.exit_code == ExitCode.OK, result.output
    assert "Warszawa\\x1b[2J [warszawa]" in result.stdout
    assert "\x1b" not in result.stdout


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ("--limit", "0"),
            "Błąd: limit musi być liczbą całkowitą z zakresu 1–100 (liczba pozycji "
            "rankingu), podano 0.",
        ),
        (
            ("--min-transactions", "-1"),
            "Błąd: min_transactions musi być liczbą całkowitą z zakresu 0–10000000 "
            "(najmniejsza liczba transakcji miejsca w rankingu), podano -1.",
        ),
    ],
)
def test_wrong_numbers_are_refused_before_a_request(
    limiter: RequestLimiter, service: respx.MockRouter, args: tuple[str, ...], message: str
) -> None:
    ranking_routes(service)

    result = run_cli(limiter, "stats", "cities", *args)

    assert result.exit_code == ExitCode.INVALID_INPUT
    assert result.stderr.strip() == message
    assert service.calls.call_count == 0


@pytest.mark.parametrize("args", [("--level", "gmina"), ("--sort", "price_desc")])
def test_unknown_choices_are_usage_errors(
    limiter: RequestLimiter, service: respx.MockRouter, args: tuple[str, ...]
) -> None:
    ranking_routes(service)

    result = run_cli(limiter, "stats", "cities", *args)

    assert result.exit_code == ExitCode.INVALID_INPUT
    assert service.calls.call_count == 0


@pytest.mark.parametrize(("status", "code"), [(500, ExitCode.SERVICE_ERROR), (403, ExitCode.STOP)])
def test_failures_of_the_service_end_with_their_codes(
    limiter: RequestLimiter, service: respx.MockRouter, status: int, code: ExitCode
) -> None:
    service.get(CITY_RANKING).respond(status, text=INJECTED)

    result = run_cli(limiter, "stats", "cities")

    assert result.exit_code == code
    assert result.stdout == ""
    first = result.stderr.splitlines()[0]
    assert first.startswith("Błąd: ")
    assert not LEAKS.search(first), first
