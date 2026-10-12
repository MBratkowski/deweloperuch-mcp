"""Live: the ``deweloperuch`` CLI, one process per command (no shared cache: sparingly).

Commands that send requests run the CLI's entry point with httpx's request log in a file,
so the suite can count them (``live.run_cli``); offline ones also run the installed
script. Exit codes are public API (D11): 0, 2 input, 3 STOP and 4 service error (both
end the session), 7 not found. Output is text for people: no tracebacks, no control
characters.
"""

import json
from collections.abc import Callable
from typing import Any

import pytest

from deweloperuch_mcp.identity import BASE_URL
from e2e.live import SERVICE_CHANGED, Budget, Run, run_cli, run_script

pytestmark = pytest.mark.live

UNKNOWN_CITY = "nieistniejace-miasto"
PAGES = BASE_URL + "/ceny-ofertowe"
FILTERS = ("--price-max", "900000", "--area-min", "30", "--sort", "price_asc")

Cli = Callable[..., Run]


@pytest.fixture(scope="module")
def cli(budget: Budget, tmp_path_factory: pytest.TempPathFactory) -> Cli:
    logs = tmp_path_factory.mktemp("cli")

    def run(*args: str) -> Run:
        return run_cli(budget, logs, *args)

    return run


def ok(run: Run) -> str:
    assert run.code == 0, (run.code, run.stderr)
    assert run.stderr == ""
    run.readable()
    return run.stdout


@pytest.fixture(scope="module")
def offers(cli: Cli) -> dict[str, Any]:
    """``offers search krakow`` with filters, as JSON (the domain model)."""
    run = cli("offers", "search", "krakow", *FILTERS, "--json")
    data: dict[str, Any] = json.loads(ok(run))
    assert run.sent == 1
    return data


@pytest.fixture(scope="module")
def offer(offers: dict[str, Any]) -> dict[str, Any]:
    assert offers["items"], "brak ofert dla filtrów e2e"
    found: dict[str, Any] = offers["items"][0]
    return found


def test_locations_search_as_text(cli: Cli) -> None:
    run = cli("locations", "search", "Kraków")

    lines = ok(run).splitlines()
    assert lines[0].startswith("Lokalizacje: ")
    assert any(line.startswith("miasto") and "Kraków [krakow]" in line for line in lines)
    assert lines[-1] == "W nawiasach [] slug miasta dla: deweloperuch offers search CITY_SLUG"
    assert run.sent == 2


def test_locations_search_as_json(cli: Cli) -> None:
    run = cli("locations", "search", "Gdańsk", "--json")

    data = json.loads(ok(run))
    assert {"total", "returned", "truncated", "hint", "items"} <= set(data)
    assert any(i["kind"] == "city" and i["name"] == "Gdańsk" for i in data["items"])
    assert run.sent == 2


def test_offers_search_with_filters_as_json(offers: dict[str, Any]) -> None:
    items = offers["items"]
    assert (offers["page"], offers["per_page"], offers["returned"]) == (1, 10, len(items))
    values = [item["price"] for item in items if item["price"] is not None]
    assert values == sorted(values) and all(price <= 900_000 for price in values)
    assert all(item["area_m2"] >= 30 for item in items if item["area_m2"] is not None)
    assert all(item["offer_id"] > 0 and item["investment_slug"] for item in items)
    # Links (D12): the list with the filters as sent, each offer's investment page.
    assert offers["list_url"] == (
        f"{PAGES}/krakow/mieszkania?filterPrice=0-900000&filterSize=30-9999"
        "&sortBy=amount&sortOrder=asc&page=1&perPage=10"
    )
    for item in items:
        assert item["investment_url"] == (
            f"{PAGES}/{item['city_slug']}/deweloperzy/{item['developer_slug']}/"
            f"{item['investment_slug']}"
        )


def test_offers_search_with_filters_as_text(cli: Cli) -> None:
    run = cli("offers", "search", "krakow", *FILTERS)

    lines = ok(run).splitlines()
    assert lines[0].startswith("Pasujące oferty: ")
    assert any(line.startswith("[") and " PLN" in line for line in lines)
    assert f"Ta lista na deweloperuch.pl: {PAGES}/krakow/mieszkania?" in run.stdout
    assert any(line.startswith(f"    {PAGES}/") and "/deweloperzy/" in line for line in lines)
    assert lines[-1] == (
        "Szczegóły oferty: deweloperuch offers get OFFER_ID --investment INVESTMENT_SLUG"
    )
    assert run.sent == 1


def test_offers_get(cli: Cli, offer: dict[str, Any]) -> None:
    run = cli("offers", "get", str(offer["offer_id"]), "--investment", offer["investment_slug"])

    lines = ok(run).splitlines()
    assert lines[0].startswith(f"[{offer['offer_id']}] ")
    assert any(line.startswith("Historia ceny (") for line in lines)
    assert f"Strona inwestycji: {offer['investment_url']}" in lines
    assert any(line.startswith(f"Profil dewelopera: {PAGES}/") for line in lines)
    assert run.sent == 2  # the investment and the price history


def test_investments_get_with_a_limit(cli: Cli, offer: dict[str, Any]) -> None:
    run = cli("investments", "get", offer["investment_slug"], "--limit", "2")

    lines = ok(run).splitlines()
    assert f"[{offer['investment_slug']}]" in lines[0]
    assert lines[1] == f"Strona inwestycji: {offer['investment_url']}"
    assert any(line.startswith("Oferty: aktywne ") for line in lines)
    assert sum(line.startswith("[") for line in lines) <= 2
    assert run.sent == 1


def test_offers_search_of_an_unknown_city(cli: Cli) -> None:
    run = cli("offers", "search", UNKNOWN_CITY)

    assert run.code == 7, (run.code, run.stderr)
    assert run.stdout == ""
    run.readable()
    lines = run.stderr.splitlines()
    assert lines[0].startswith(f"Błąd: Serwis nie zna miasta '{UNKNOWN_CITY}'.")
    assert "search_locations" in lines[0] and "polska" in lines[0]
    assert SERVICE_CHANGED not in run.stderr
    assert lines[1].startswith("Szczegóły: ")
    assert "<html" not in run.stderr.lower() and "<!doctype" not in run.stderr.lower()
    assert run.sent == 1


def test_offers_search_with_a_wrong_page_size_sends_nothing(cli: Cli) -> None:
    run = cli("offers", "search", "krakow", "--per-page", "7")

    assert run.code == 2, (run.code, run.stderr)
    assert "per-page" in run.stderr
    assert "Traceback" not in run.stderr
    assert run.sent == 0


def test_stop_status_is_offline(cli: Cli) -> None:
    """A STOP that holds ends the session (exit 3, ``live.run_cli``); none: exit 0."""
    run = cli("stop", "status")

    assert ok(run).splitlines()[0].startswith(("Brak STOP", "STOP wygasł"))
    assert run.sent == 0


def test_the_installed_script_runs_offline() -> None:
    """The ``deweloperuch`` script itself (the other tests run its entry point)."""
    run = run_script("deweloperuch", "stop", "status")

    assert run.code == 0, (run.code, run.stderr)
    run.readable()
