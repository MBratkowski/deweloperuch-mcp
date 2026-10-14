"""Tests of ``deweloperuch_mcp.consumers.cli.commands.investment_search_commands``."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
import respx

from deweloperuch_mcp.consumers.shared import investment_search_views as views
from support.builders.investment_search import (
    INJECTED,
    KOMFORT,
    city_with_investments,
)
from support.providers.routes.investment_search import CITY_INVESTMENTS, investment_search_routes
from support.providers.samples import body
from support.providers.service import PAGES

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_cli_a_city_as_text(investments_cli: Callable[..., Any], service: respx.MockRouter) -> None:
    investment_search_routes(service)

    result = investments_cli("investments", "search", "sopot", "--sort", "price_per_m2_asc")

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [
        "Inwestycje: 2 · pokazano 2.",
        "Smolna [smolna] · aktywna · Sopot, Świemirowo",
        "    oferty: aktywne 3 z 16 · średnio 1 566 392 PLN · 63,97 m² · 24 522,21 PLN/m²",
        "    Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]",
        f"    {PAGES}/sopot/deweloperzy/{KOMFORT}/smolna",
        "Nowe Kolibki etap 4 [nowe-kolibki-etap-4] · aktywna · Sopot",
        "    oferty: aktywne 3 z 27 · średnio 1 615 878 PLN · 65,55 m² · 24 756,49 PLN/m²",
        "    Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]",
        f"    {PAGES}/sopot/deweloperzy/{KOMFORT}/nowe-kolibki-etap-4",
        "Oferty inwestycji: deweloperuch investments get INVESTMENT_SLUG",
    ]


def test_cli_a_name_as_text_and_a_cut_city(
    investments_cli: Callable[..., Any], service: respx.MockRouter
) -> None:
    investment_search_routes(service, city=city_with_investments(3))

    by_name = investments_cli("investments", "search", "--name", "nowy targ")
    cut = investments_cli("investments", "search", "sopot", "--limit", "1", "--developer", KOMFORT)

    assert by_name.exit_code == 0, by_name.output
    assert by_name.stdout.splitlines()[:3] == [
        "Inwestycje: 2 · pokazano 2.",
        "Nowy Targówek VI [nowy-targowek-vi]",
        "    oferty: aktywne 27",
    ]
    assert cut.exit_code == 0, cut.output
    assert cut.stdout.splitlines()[:2] == [
        "Inwestycje: 3 · pokazano 1 (zwiększ --limit albo zawęź wyniki).",
        "Wskazówka: Pasujących inwestycji jest 3, pokazano pierwsze 1 (sort=active_offers). "
        "Zawęź wyniki przez name lub developer_slug albo zmień sort.",
    ]


@pytest.mark.parametrize(
    ("limit", "head"),
    [
        ("3", "Inwestycje: 120 · pokazano 2 (zwiększ --limit albo zawęź wyniki)."),
        # A search by name never shows more than 50: no larger --limit to suggest.
        ("50", "Inwestycje: 120 · pokazano 2 (zawęź wyniki)."),
        ("500", "Inwestycje: 120 · pokazano 2 (zawęź wyniki)."),
    ],
)
def test_cli_a_name_suggests_a_larger_limit_only_below_50(
    investments_cli: Callable[..., Any], service: respx.MockRouter, limit: str, head: str
) -> None:
    _, names = investment_search_routes(
        service, names=dict(body("api.investments_q"), hasMore=True, total=120)
    )

    result = investments_cli("investments", "search", "--name", "nowy", "--limit", limit)

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[0] == head
    assert names.calls.last.request.url.params["limit"] == str(min(int(limit), 50))


def test_cli_json_is_the_view(
    investments_cli: Callable[..., Any], service: respx.MockRouter
) -> None:
    investment_search_routes(service)

    result = investments_cli("investments", "search", "sopot", "--json")

    assert result.exit_code == 0, result.output
    found = json.loads(result.stdout)
    assert list(found) == ["total", "returned", "truncated", "hint", "items"]
    assert found["items"][1]["city"] == "Sopot" and found["items"][1]["lat"] == 54.42735985
    assert set(found["items"][1]) == set(views.InvestmentSummaryView.model_fields)


@pytest.mark.parametrize(
    ("args", "answer", "code", "message"),
    [
        ((), None, 2, "Błąd: Podaj city (slug miasta z search_locations"),
        (("polska",), None, 2, "Błąd: city=polska nie działa"),
        (
            ("sopot", "--limit", "0"),
            None,
            2,
            "Błąd: limit musi być liczbą całkowitą z zakresu 1–500",
        ),
        (("sopot", "--sort", "cheap"), None, 2, ""),
        (("sopot",), httpx.Response(404), 7, "Błąd: Serwis nie zna miasta 'sopot'."),
        (
            ("sopot",),
            httpx.Response(500, text=INJECTED),
            4,
            "Błąd: Wyszukiwanie inwestycji w 'sopot'",
        ),
        (
            ("sopot",),
            httpx.Response(200, json={"x": 1}),
            6,
            "Błąd: Wyszukiwanie inwestycji w 'sopot'",
        ),
        (("sopot",), httpx.Response(403), 3, "Błąd: STOP"),
    ],
)
def test_cli_exit_codes(
    investments_cli: Callable[..., Any],
    service: respx.MockRouter,
    args: tuple[str, ...],
    answer: httpx.Response | None,
    code: int,
    message: str,
) -> None:
    route = service.get(path=CITY_INVESTMENTS)
    if answer is not None:
        route.mock(return_value=answer)

    result = investments_cli("investments", "search", *args)

    assert result.exit_code == code, result.output
    assert result.stderr.startswith(message), result.stderr
    assert route.call_count == (0 if answer is None else 1)
