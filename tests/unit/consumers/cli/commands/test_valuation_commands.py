"""Tests of ``deweloperuch_mcp.consumers.cli.commands.valuation_commands``."""

import json

import pytest
import respx

from deweloperuch_mcp.consumers.shared.valuation_views import (
    ValuationView,
)
from deweloperuch_mcp.throttle import RequestLimiter
from support.builders.valuation import WITHOUT_ADDRESS
from support.providers.cli import run_cli
from support.providers.routes.valuation import VALUATION, VALUATION_PATH, valuation_route
from support.providers.samples import body

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


ESTIMATE = ("valuation", "estimate", "--lat", "52.2297", "--lng", "21.0122", "--area", "50")


def test_cli_prints_the_valuation_and_every_comparable(
    limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    route = valuation_route(service)

    result = run_cli(limiter, *ESTIMATE)

    assert result.exit_code == 0, result.stderr
    assert [str(c.request.url) for c in route.calls] == [WITHOUT_ADDRESS]
    lines = result.stdout.splitlines()
    assert lines[:5] == [
        "Wycena mieszkania 50 m² · 52.22970, 21.01220",
        "Szacowana wartość: 1 063 300 PLN · 21 266 PLN/m²",
        "Na podstawie transakcji z Rejestru Cen Nieruchomości (RCN) w promieniu 200 m z "
        "ostatnich 24 miesięcy; to przybliżenie, nie operat szacunkowy.",
        "Statystyki cen za m² podane przez serwis (liczba: 9): mediana 23 830 · średnia "
        "22 195 · min 13 187 · max 31 492 PLN/m²",
        "Transakcje porównawcze: 3 · pokazano 3.",
    ]
    assert lines[5] == (
        "  2025-04-17   ok. 150 m  Ulica Nowogrodzka 38 · 43,57 m² · 765 002 PLN · 17 558 "
        "PLN/m² · piętro 6 · rynek wtórny [ulica-nowogrodzka-38-warszawa]"
    )
    assert len(lines) == 8


def test_cli_with_an_address_and_a_limit(
    limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    route = valuation_route(service)

    result = run_cli(limiter, *ESTIMATE, "--address", "Marszałkowska 100, Warszawa", "--limit", "1")

    assert result.exit_code == 0, result.stderr
    assert [str(c.request.url) for c in route.calls] == [VALUATION]
    assert "Adres (opis): Marszałkowska 100, Warszawa" in result.stdout
    assert "Transakcje porównawcze: 3 · pokazano 1 · pominięto 2 (zwiększ --limit)." in (
        result.stdout
    )


def test_cli_json_is_the_view(limiter: RequestLimiter, service: respx.MockRouter) -> None:
    valuation_route(service)

    result = run_cli(limiter, *ESTIMATE, "--json")

    assert result.exit_code == 0, result.stderr
    shown = json.loads(result.stdout)
    assert set(shown) == set(ValuationView.model_fields)
    assert shown["comparables"][0]["city_slug"] == "warszawa"
    assert (shown["comparables_total"], shown["comparables_omitted"]) == (3, 0)


@pytest.mark.parametrize("limit", [3, 1])
def test_cli_shows_the_fractional_area_caution_with_any_comparable_limit(
    limiter: RequestLimiter, service: respx.MockRouter, limit: int
) -> None:
    valuation_route(service)

    result = run_cli(limiter, *ESTIMATE, "--area", "41.37", "--limit", str(limit))

    assert result.exit_code == 0, result.stderr
    assert (
        "Wskazówka: Serwis może nie uwzględnić części ułamkowej powierzchni w wycenie."
        in result.stdout
    )
    assert "Wycena mieszkania 41,37 m²" in result.stdout
    assert "Szacowana wartość: 1 063 300 PLN · 21 266 PLN/m²" in result.stdout
    if limit == 1:
        assert "pominięto 2 (zwiększ --limit)" in result.stdout


def test_cli_json_retains_the_fractional_request_with_the_service_estimate(
    limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    answer = body("api.standalone_val")
    answer.update(estimatedValue=558_666, estimatedPricePerSqm=13_626)
    route = valuation_route(service, answer)

    result = run_cli(limiter, *ESTIMATE, "--area", "41.37", "--json")

    assert result.exit_code == 0, result.stderr
    assert route.calls[0].request.url.params["area"] == "41.37"
    shown = json.loads(result.stdout)
    assert shown["area_m2"] == 41.37
    assert shown["estimated_value"] == 558_666
    assert shown["price_per_m2"] == 13_626
    assert shown["hint"] == ("Serwis może nie uwzględnić części ułamkowej powierzchni w wycenie.")


def test_cli_keeps_no_estimate_guidance_with_a_fractional_area_and_limited_comparables(
    limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    answer = body("api.standalone_val")
    answer.update(estimatedValue=None, estimatedPricePerSqm=None)
    valuation_route(service, answer)

    result = run_cli(limiter, *ESTIMATE, "--area", "41.37", "--limit", "1")

    assert result.exit_code == 0, result.stderr
    assert "Szacowana wartość: brak." in result.stdout
    assert "Serwis nie podał wyceny dla tego miejsca;" in result.stdout
    assert "Serwis może nie uwzględnić części ułamkowej powierzchni w wycenie." in result.stdout
    assert "pominięto 2 (zwiększ --limit)" in result.stdout


@pytest.mark.parametrize(
    ("args", "said"),
    [
        (("--lat", "60"), "Błąd: lat musi być liczbą z zakresu 49–54.9"),
        (("--area", "5"), "Błąd: area_m2 musi być liczbą z zakresu 10–500 m², podano 5.0."),
        (("--limit", "-1"), "Błąd: limit musi być liczbą całkowitą z zakresu 0–100000"),
        (("--lat", "nan"), "Błąd: lat musi być liczbą z zakresu 49–54.9"),
    ],
)
def test_cli_input_checked_before_any_request(
    limiter: RequestLimiter, service: respx.MockRouter, args: tuple[str, ...], said: str
) -> None:
    route = valuation_route(service)

    result = run_cli(limiter, *ESTIMATE, *args)

    assert result.exit_code == 2
    assert result.stderr.startswith(said)
    assert route.call_count == 0


def test_cli_not_found_has_its_exit_code(
    limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    service.get(path=VALUATION_PATH).respond(404)

    result = run_cli(limiter, *ESTIMATE)

    assert result.exit_code == 7
    assert result.stderr.startswith("Błąd: Serwis nie podał wyceny dla tego miejsca;")


def test_cli_without_an_estimate_says_nothing_about_its_source(
    limiter: RequestLimiter, service: respx.MockRouter
) -> None:
    answer = body("api.standalone_val")
    answer.update(estimatedValue=None, estimatedPricePerSqm=None, stats=None, transactions=[])
    valuation_route(service, answer)

    result = run_cli(limiter, *ESTIMATE)

    assert result.exit_code == 0, result.stderr
    assert result.stdout.splitlines() == [
        "Wycena mieszkania 50 m² · 52.22970, 21.01220",
        "Szacowana wartość: brak.",
        "Wskazówka: Serwis nie podał wyceny dla tego miejsca; w promieniu może nie być transakcji.",
        "Transakcje porównawcze: 0 · pokazano 0.",
    ]
