"""Tests of ``deweloperuch_mcp.consumers.cli.commands.buildings_commands``."""

import json
from pathlib import Path

import pytest
import respx

from support.builders.buildings import NOT_FOUND, UNKNOWN, trend_with_quarters
from support.providers.cli import buildings_cli
from support.providers.routes.buildings import (
    BUILDING_PAGE,
    SLUG,
    TREND,
    UNKNOWN_BUILDING,
    building_routes,
)

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_the_cli_shows_the_building_for_people(tmp_path: Path, service: respx.MockRouter) -> None:
    building_routes(service)

    run = buildings_cli(tmp_path, SLUG)

    assert (run.exit_code, run.stderr) == (0, "")
    lines = run.stdout.splitlines()
    assert lines[:5] == [
        "23 Marca 79C [23-marca-79c-sopot]",
        "Strona budynku: " + BUILDING_PAGE,
        "Miejsce: Sopot [sopot] · 54.44706, 18.54342",
        "Średnio (wg serwisu): 1 324 115 PLN · 61,6 m² · 21 494,72 PLN/m²",
        "Lokale: 3 · transakcje: 3 (od 2025-09-12 do 2025-11-17) · pokazano 3.",
    ]
    assert lines[5:7] == [
        "piętro 1 · 5 pok. · 122,01 m² · 226401_1.0018.6977_BUD.3_LOK",
        "  2025-11-17  1 900 000,47 PLN · 15 572,5 PLN/m² · rynek pierwotny · zwykła · "
        "kupujący: osoba fizyczna · sprzedający: osoba prawna",
    ]
    assert len(lines) == 11


def test_the_cli_with_the_trend_and_a_limit(tmp_path: Path, service: respx.MockRouter) -> None:
    building_route, trend_route = building_routes(service)

    run = buildings_cli(tmp_path, SLUG, "--trend", "--limit", "1")

    assert run.exit_code == 0, run.stderr
    lines = run.stdout.splitlines()
    assert lines[4].endswith("· pokazano 1 · pominięto 2 (zwiększ --limit).")
    assert lines[-4:] == [
        "Trend w okolicy (promień 1 km): średnia cena za m² i liczba transakcji.",
        "  2006-Q2  5 706 PLN/m² · transakcji: 25",
        "  2006-Q3  6 188 PLN/m² · transakcji: 38",
        "  2006-Q4  6 668 PLN/m² · transakcji: 38",
    ]
    assert (building_route.call_count, trend_route.call_count) == (1, 1)


def test_the_cli_json_is_the_whole_view(tmp_path: Path, service: respx.MockRouter) -> None:
    building_routes(service)
    service.get(TREND).respond(200, json=trend_with_quarters(20))

    run = buildings_cli(tmp_path, SLUG, "--trend", "--json")

    assert run.exit_code == 0, run.stderr
    view = json.loads(run.stdout)
    assert (view["units_total"], view["units_omitted"], len(view["units"])) == (3, 0, 3)
    first = view["units"][0]
    assert (first["unit_id"], first["name"]) == (477553, "226401_1.0018.6977_BUD.3_LOK")
    deed = first["transactions"][0]
    assert (deed["currency"], deed["share"]) == ("PLN", "1/1")
    trend = view["neighbourhood_trend"]
    assert (trend["quarters_total"], trend["quarters_omitted"], len(trend["quarters"])) == (
        20,
        0,
        20,
    )


@pytest.mark.parametrize(
    ("args", "code", "message"),
    [
        ((UNKNOWN_BUILDING,), 7, "Błąd: " + NOT_FOUND),
        (("23 Marca",), 2, "Błąd: building_slug: oczekiwano slug budynku"),
        ((SLUG, "--limit", "-1"), 2, "Błąd: limit musi być liczbą całkowitą z zakresu 0–100000"),
    ],
)
def test_the_cli_errors_and_their_exit_codes(
    tmp_path: Path, service: respx.MockRouter, args: tuple[str, ...], code: int, message: str
) -> None:
    service.get(UNKNOWN).respond(404)
    building_routes(service)

    run = buildings_cli(tmp_path, *args)

    assert (run.exit_code, run.stdout) == (code, "")
    assert run.stderr.startswith(message)
