"""Tests of ``deweloperuch_mcp.consumers.cli.commands.investments_commands``."""

import json
from collections.abc import Callable
from typing import Any

import pytest
import respx

from support.builders.investments import DEVELOPER_PAGE, SMOLNA_PAGE
from support.providers.cli import Cli, ok
from support.providers.routes.investments import INVESTMENT, investment_routes


def test_investments_get_prints_the_investment_and_its_offers(
    run: Cli, service: respx.MockRouter
) -> None:
    investment_routes(service)

    out = ok(run("investments", "get", "smolna"))

    assert out.splitlines() == [
        "Smolna [smolna] · aktywna",
        f"Strona inwestycji: {SMOLNA_PAGE}",
        "Miejsce: Sopot [sopot], Świemirowo · 54.42736, 18.55839",
        "Deweloper: Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]",
        f"Profil dewelopera: {DEVELOPER_PAGE}",
        "Średnio (aktywne oferty): 1 566 392 PLN · 63,97 m² · 24 487,63 PLN/m²",
        "Oferty: aktywne 3 z 16 · pokazano 3.",
        "[206087] C234 · 1 679 796 PLN · 65,9 m² · 25 490,08 PLN/m² · aktywna",
        "[2377] C224 · 1 620 175 PLN · 69,5 m² · 23 311,87 PLN/m² · aktywna · "
        "od pierwszej ceny +175 PLN (+0,01%)",
        "[2386] C213 · 1 399 205 PLN · 56,5 m² · 24 764,69 PLN/m² · aktywna · "
        "od pierwszej ceny -10 795 PLN (-0,77%)",
    ]


def test_investments_get_with_history_and_limit(run: Cli, service: respx.MockRouter) -> None:
    _, history, _ = investment_routes(service)

    out = ok(run("investments", "get", "smolna", "--history", "--limit", "1"))

    assert history.call_count == 1
    assert "Oferty: aktywne 3 z 16 · pokazano 1 · pominięto 2 (zwiększ --limit)." in out
    assert "  2026-10-03  cena          1 679 796 PLN" in out


def test_investments_get_json_is_the_domain_model(run: Cli, service: respx.MockRouter) -> None:
    investment_routes(service)

    data = json.loads(ok(run("investments", "get", "smolna", "--limit", "2", "--json")))

    assert (data["investment_slug"], data["offers_total"], data["offers_omitted"]) == (
        "smolna",
        16,
        1,
    )
    assert [offer["offer_id"] for offer in data["offers"]] == [206087, 2377]
    assert data["offers"][0]["price_history"] is None


@pytest.mark.usefixtures("unix_sockets_for_the_event_loop")
def test_cli_the_group_lists_both_commands(investments_cli: Callable[..., Any]) -> None:
    result = investments_cli("investments", "--help")

    assert result.exit_code == 0
    assert "get" in result.stdout and "search" in result.stdout
    assert "Szukaj inwestycji w mieście albo po nazwie" in result.stdout


@pytest.mark.usefixtures("unix_sockets_for_the_event_loop")
def test_get_investment_is_unchanged_by_the_new_command(
    investments_cli: Callable[..., Any], service: respx.MockRouter
) -> None:
    investment_routes(service)

    result = investments_cli("investments", "get", "smolna", "--limit", "0")

    assert result.exit_code == 0, result.output
    assert service.calls.last.request.url == INVESTMENT
