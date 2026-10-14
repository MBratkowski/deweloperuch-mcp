"""Tests of ``deweloperuch_mcp.consumers.cli.commands.developers_commands``."""

import json

import pytest
import respx

from support.builders.developer_search import (
    ATAL_ROW,
    INJECTED,
    LEAKS,
    NOTHING_HINT,
    PROFILES,
    TRUNCATED_HINT,
    developers_found,
)
from support.providers.cli import Cli, ok
from support.providers.routes.developer_search import DEVELOPERS, developer_search_route

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_cli_prints_the_developers_with_their_slugs_and_profiles(
    run: Cli, service: respx.MockRouter
) -> None:
    route = developer_search_route(service)

    out = ok(run("developers", "search", "atal"))

    assert out.splitlines() == [
        "Deweloperzy: 1.",
        "ATAL S.A. [atal] · ofert: 4 265",
        "    " + PROFILES + "atal",
        "W nawiasach [] slug dewelopera dla: deweloperuch developers get SLUG",
    ]
    assert [str(c.request.url) for c in route.calls] == [DEVELOPERS]
    assert len(run.sessions) == 1 and run.sessions[0].closed


def test_cli_json_is_the_view(run: Cli, service: respx.MockRouter) -> None:
    developer_search_route(service)

    shown = json.loads(ok(run("developers", "search", "atal", "--json")))

    assert shown == {
        "total": 1,
        "returned": 1,
        "truncated": False,
        "hint": None,
        "items": [ATAL_ROW],
    }


def test_cli_limit_reaches_the_service(run: Cli, service: respx.MockRouter) -> None:
    route = developer_search_route(service)

    ok(run("developers", "search", "dom development", "--limit", "20"))

    assert route.calls[0].request.url.params["limit"] == "20"
    assert route.calls[0].request.url.params["q"] == "dom development"


def test_cli_truncated_and_empty_results_say_what_to_do(
    run: Cli, service: respx.MockRouter
) -> None:
    developer_search_route(service, developers_found(5, total=12, more=True))
    lines = ok(run("developers", "search", "atal")).splitlines()

    assert lines[0] == "Deweloperzy: 12 · pokazano 5."
    assert "Wskazówka: " + TRUNCATED_HINT in lines

    developer_search_route(service, developers_found(5, total=5, more=True))
    lines = ok(run("developers", "search", "atal")).splitlines()

    assert lines[0] == "Deweloperzy: pokazano 5, może być więcej."

    developer_search_route(service, developers_found(0, total=0, more=False))
    lines = ok(run("developers", "search", "xyzzy")).splitlines()

    assert lines == ["Deweloperzy: 0.", "Wskazówka: " + NOTHING_HINT]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("a",), "Błąd: name: podaj od 2 do 100 znaków nazwy dewelopera, podano 'a'."),
        (
            ("atal", "--limit", "0"),
            "Błąd: limit musi być liczbą całkowitą z zakresu 1–20 (liczba deweloperów w "
            "wyniku), podano 0.",
        ),
        (
            ("atal", "--limit", "21"),
            "Błąd: limit musi być liczbą całkowitą z zakresu 1–20 (liczba deweloperów w "
            "wyniku), podano 21.",
        ),
    ],
)
def test_cli_invalid_input_exits_with_2_without_a_request(
    run: Cli, service: respx.MockRouter, args: tuple[str, ...], message: str
) -> None:
    developer_search_route(service)

    result = run("developers", "search", *args)

    assert result.exit_code == 2
    assert result.stderr.splitlines() == [message]
    assert service.calls.call_count == 0


def test_cli_limit_that_is_not_a_number_is_a_usage_error(
    run: Cli, service: respx.MockRouter
) -> None:
    result = run("developers", "search", "atal", "--limit", "x")

    assert result.exit_code == 2
    assert run.sessions == [] and service.calls.call_count == 0


@pytest.mark.parametrize(("status", "code"), [(500, 4), (403, 3), (429, 3)])
def test_cli_service_answers_map_to_exit_codes(
    run: Cli, service: respx.MockRouter, status: int, code: int
) -> None:
    service.get(path="/api/developers").respond(status, text=INJECTED)

    result = run("developers", "search", "atal")

    assert result.exit_code == code
    first = result.stderr.splitlines()[0]
    assert first.startswith("Błąd: ")
    assert not LEAKS.search(first)


def test_cli_help_works_offline(run: Cli) -> None:
    assert "search" in ok(run("developers", "--help"))
    out = ok(run("developers", "search", "--help"))

    for shown in ("NAME", "--limit", "--json", "developers get"):
        assert shown in out
    assert "developers" in ok(run("--help"))
    assert run.sessions == []
