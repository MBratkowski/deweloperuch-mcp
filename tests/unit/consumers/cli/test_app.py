"""Tests of ``deweloperuch_mcp.consumers.cli.app``."""

import pytest
import respx
from typer.testing import CliRunner

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.consumers.cli import app as cli_app
from deweloperuch_mcp.consumers.cli.support.common import ExitCode
from deweloperuch_mcp.errors import InvalidInputError
from deweloperuch_mcp.usecases.search_locations import SearchLocations
from support.providers.cli import Cli, ok


@pytest.mark.parametrize(
    ("args", "option"),
    [
        (["offers", "search", "warszawa", "--sort", "rooms_asc"], "--sort"),
        (["offers", "search", "warszawa", "--per-page", "20"], "--per-page"),
        (["offers", "search", "warszawa", "--page", "two"], "--page"),
        (["offers", "search", "warszawa", "--price-max", "1.5"], "--price-max"),
        (["offers", "get", "abc", "--investment", "smolna"], "OFFER_ID"),
        (["investments", "get", "smolna", "--limit", "x"], "--limit"),
    ],
)
def test_types_and_enums_are_checked_before_a_session_opens(
    run: Cli, service: respx.MockRouter, args: list[str], option: str
) -> None:
    result = run(*args)

    assert result.exit_code == ExitCode.INVALID_INPUT
    assert option in result.stderr
    assert result.stdout == ""
    assert run.sessions == []
    assert service.calls.call_count == 0


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["offers", "search", "warszawa", "--page", "21"], "page musi być liczbą całkowitą"),
        (["offers", "search", "Kraków"], "city: oczekiwano slug miasta"),
        (["offers", "search", "warszawa", "--price-min", "7", "--price-max", "5"], "price_min"),
        (["offers", "search", "warszawa", "--area-min", "-1"], "area_min"),
        (["offers", "get", "0", "--investment", "smolna"], "offer_id"),
        (["investments", "get", "Smolna"], "investment_slug"),
        (["locations", "search", "k"], "query"),
    ],
)
def test_the_application_checks_the_rest_and_says_what_to_fix(
    run: Cli, service: respx.MockRouter, args: list[str], message: str
) -> None:
    result = run(*args)

    assert result.exit_code == ExitCode.INVALID_INPUT
    assert result.stderr.startswith("Błąd: ")
    assert message in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""
    assert service.calls.call_count == 0


def test_the_default_session_is_the_bootstraps_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``obj`` (the real ``deweloperuch``) a command opens ``bootstrap.Session()``
    through ``bootstrap.new_session``."""
    opened: list[str] = []

    class Recorded(bootstrap.Session):
        def __init__(self) -> None:
            opened.append("session")
            super().__init__()

    def fail(use_case: object, query: object) -> None:
        raise InvalidInputError("stop here")

    monkeypatch.setattr(bootstrap, "Session", Recorded)
    monkeypatch.setattr(SearchLocations, "execute", fail)

    result = CliRunner().invoke(cli_app.app, ["locations", "search", "krak"])

    assert result.exit_code == ExitCode.INVALID_INPUT
    assert opened == ["session"]


def test_help_lists_the_command_groups(run: Cli) -> None:
    out = ok(run("--help"))

    for group in ("locations", "offers", "investments", "stats", "stop"):
        assert group in out
    assert "--install-completion" not in out
    assert run.sessions == []


@pytest.mark.parametrize(
    ("args", "options"),
    [
        (
            ["offers", "search", "--help"],
            ["--price-min", "--price-max", "--area-min", "--area-max", "--sort", "--page"],
        ),
        (["offers", "get", "--help"], ["--investment", "--json"]),
        (["investments", "get", "--help"], ["--history", "--limit", "--json"]),
        (["locations", "search", "--help"], ["QUERY", "--json"]),
        (["stats", "--help"], ["government"]),
        (
            ["stats", "government", "--help"],
            ["LOCATION", "DATASET", "--periods", "--json", "nbp_prices"],
        ),
        (["stop", "--help"], ["status", "clear"]),
        (["stop", "status", "--help"], ["--json"]),
        (["stop", "clear", "--help"], ["STOP"]),
    ],
)
def test_command_help_works_offline(run: Cli, args: list[str], options: list[str]) -> None:
    out = ok(run(*args))

    for option in options:
        assert option in out
    assert run.sessions == []


def test_no_command_shows_the_help(run: Cli) -> None:
    result = run()

    assert "locations" in result.stdout + result.stderr
    assert run.sessions == []


def test_main_runs_the_app(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(cli_app, "app", lambda: called.append("app"))

    cli_app.main()

    assert called == ["app"]
