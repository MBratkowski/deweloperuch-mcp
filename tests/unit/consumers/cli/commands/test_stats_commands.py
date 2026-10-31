"""Tests of ``deweloperuch_mcp.consumers.cli.commands.stats_commands``."""

import json
from collections.abc import Callable
from typing import Any

import pytest
import respx

from deweloperuch_mcp.consumers.cli.support.common import ExitCode
from support.providers.cli import Cli, ok
from support.providers.routes.government_statistics import (
    UNKNOWN_LOCATION,
    stats_path,
    stats_routes,
    stats_url,
    unknown_location_route,
)
from support.providers.rsc import STATS_POLSKA, raw


def test_stats_government_prints_a_table_of_periods_and_values(
    run: Cli, service: respx.MockRouter
) -> None:
    stats_routes(service)

    out = ok(run("stats", "government", "warszawa", "nbp_prices", "--periods", "2"))

    assert out.splitlines() == [
        "Średnie ceny mieszkań za m² według NBP · Warszawa [warszawa]",
        "Źródło: NBP · kwartalnie · okresy: pokazano 2 z 80 (dane od 2006-Q3).",
        "Wskazówka: Pokazano ostatnie 2 z 80 okresów (dane od 2006-Q3); starsze pokaże "
        "większa wartość periods.",
        f"Strona na deweloperuch.pl: {stats_url('warszawa')}#nbp",
        "Kolumny:",
        "  [1] Rynek pierwotny: cena ofertowa (PLN/m²)",
        "  [2] Rynek pierwotny: cena transakcyjna (PLN/m²)",
        "  [3] Rynek wtórny: cena ofertowa (PLN/m²)",
        "  [4] Rynek wtórny: cena transakcyjna (PLN/m²)",
        "Okres       [1]     [2]     [3]     [4]",
        "2026-Q1  18 056  16 471  18 914  16 523",
        "2026-Q2  18 488  16 783  19 059  16 723",
    ]


def test_stats_government_shows_the_note_decimals_and_missing_values(
    run: Cli, service: respx.MockRouter
) -> None:
    stats_routes(service)

    dwellings = ok(run("stats", "government", "polska", "dwellings_quarterly", "--periods", "87"))
    area = ok(run("stats", "government", "polska", "average_area"))

    lines = dwellings.splitlines()
    assert "Uwaga: Ostatni kwartał (2026-Q3) obejmuje tylko 2 z 3 miesięcy" in lines[2]
    assert "Wskazówka" not in dwellings  # all 87 periods
    assert lines[-87].startswith("2005-Q1") and lines[-87].endswith("–")  # no data for rent
    assert lines[-1].startswith("2026-Q3") and lines[-1].endswith(" 22")
    assert area.splitlines()[-1] == "2026   62,5"
    assert len(area.splitlines()) == 7 + 12  # default: 12 periods


def test_stats_government_json_is_the_domain_model(run: Cli, service: respx.MockRouter) -> None:
    stats_routes(service)

    data = json.loads(
        ok(run("stats", "government", "polska", "unemployment", "--periods", "2", "--json"))
    )

    assert data == {
        "location_slug": "polska",
        "location_name": "Polska",
        "dataset": "unemployment",
        "title": "Stopa bezrobocia rejestrowanego",
        "source": "GUS",
        "frequency": "month",
        "total": 188,
        "returned": 2,
        "truncated": True,
        "available_from": "2011-01",
        "hint": (
            "Pokazano ostatnie 2 z 188 okresów (dane od 2011-01); starsze pokaże większa "
            "wartość periods."
        ),
        "note": None,
        "stats_url": f"{stats_url('polska')}#gus-bezrobocie",
        "series": [
            {
                "series_id": "rate",
                "label": "Stopa bezrobocia",
                "unit": "%",
                "points": [
                    {"period": "2026-07", "value": 5.8},
                    {"period": "2026-08", "value": 5.8},
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    ("args", "answer", "code", "message"),
    [
        (
            ["polska", "nbp_prices"],
            stats_routes,
            7,
            "Błąd: NBP nie podaje jednej ceny dla całej Polski",
        ),
        (
            [UNKNOWN_LOCATION, "wages"],
            unknown_location_route,
            7,
            f"Błąd: Serwis nie ma statystyk rządowych dla lokalizacji {UNKNOWN_LOCATION!r}.",
        ),
        (
            ["krakow", "wages"],
            lambda r: r.get(path=stats_path("krakow")).respond(200, content=raw(STATS_POLSKA)),
            6,
            "Błąd: Statystyki rządowe dla 'krakow': Serwis zwrócił statystyki innej lokalizacji",
        ),
    ],
)
def test_stats_government_errors_have_their_exit_codes(
    run: Cli,
    service: respx.MockRouter,
    args: list[str],
    answer: Callable[[respx.MockRouter], Any],
    code: int,
    message: str,
) -> None:
    answer(service)

    result = run("stats", "government", *args)

    assert result.exit_code == code
    assert result.stdout == ""
    assert result.stderr.startswith(message)
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["Kraków", "wages"], "location: oczekiwano polska"),
        (["warszawa", "wages", "--periods", "0"], "periods musi być liczbą całkowitą"),
        (["warszawa", "wages", "--periods", "1001"], "periods"),
    ],
)
def test_stats_government_input_checked_by_the_domain(
    run: Cli, service: respx.MockRouter, args: list[str], message: str
) -> None:
    result = run("stats", "government", *args)

    assert result.exit_code == ExitCode.INVALID_INPUT
    assert result.stderr.startswith("Błąd: ") and message in result.stderr
    assert service.calls.call_count == 0


def test_stats_government_location_in_capitals_is_the_slug(
    run: Cli, service: respx.MockRouter
) -> None:
    routes = stats_routes(service)

    out = ok(run("stats", "government", "Warszawa", "unemployment", "--periods", "1"))

    assert out.splitlines()[0] == "Stopa bezrobocia rejestrowanego · Warszawa [warszawa]"
    assert routes["warszawa"].call_count == 1


@pytest.mark.parametrize(
    ("args", "option"),
    [
        (["warszawa", "prices"], "DATASET"),
        (["warszawa", "wages", "--periods", "x"], "--periods"),
        (["warszawa"], "DATASET"),
    ],
)
def test_stats_government_types_and_choices_are_checked_before_a_session_opens(
    run: Cli, service: respx.MockRouter, args: list[str], option: str
) -> None:
    result = run("stats", "government", *args)

    assert result.exit_code == ExitCode.INVALID_INPUT
    assert option in result.stderr
    assert run.sessions == []
    assert service.calls.call_count == 0
