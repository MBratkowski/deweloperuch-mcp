"""The gate and the safeguards of the live suite (tests/e2e), offline.

The live tests never run in the default suite. These tests make sure they cannot: a
live run needs ``DEWELOPERUCH_LIVE=1`` and ``-m live``, both; every test in tests/e2e
is marked ``live``; in this very session every one of them is skipped before its
fixtures run. The safeguards are checked on a fake server (the real entry point with
the network blocked and mocked) and on faked runs of the CLI and probe: requests are
counted, a STOP ends the session with code 3, a service error with code 4, a counter
that sees nothing with code 1; results with backend details fail, real ones do not.
"""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
import respx
from mcp import Client
from mcp.types import CallToolResult
from pydantic import BaseModel

from deweloperuch_mcp import identity, mcp_results, mcp_server, services
from deweloperuch_mcp.throttle import RequestLimiter
from e2e import live, test_live_cli, test_live_mcp, test_live_recon
from rsc_fixtures import UNKNOWN_CITY
from service_mocks import investment_routes, location_routes, offers_route, unknown_city_route

TESTS = Path(__file__).resolve().parent
E2E = TESTS / "e2e"


class FakeItem:
    def __init__(self, marked_live: bool) -> None:
        self.marked_live = marked_live
        self.added: list[pytest.MarkDecorator] = []

    def get_closest_marker(self, name: str) -> object | None:
        return object() if name == "live" and self.marked_live else None

    def add_marker(self, marker: pytest.MarkDecorator) -> None:
        self.added.append(marker)


def fake_config(markexpr: str) -> Any:
    return SimpleNamespace(option=SimpleNamespace(markexpr=markexpr))


@pytest.mark.parametrize(
    ("env", "markexpr", "enabled"),
    [
        (None, "", False),
        (None, "live", False),
        ("1", "", False),
        ("1", "not slow", False),
        ("1", "lively", False),
        ("0", "live", False),
        ("true", "live", False),
        ("1", "live", True),
        ("1", "live and not slow", True),
    ],
)
def test_live_runs_only_with_the_variable_and_the_marker(
    monkeypatch: pytest.MonkeyPatch, env: str | None, markexpr: str, enabled: bool
) -> None:
    if env is None:
        monkeypatch.delenv(live.LIVE_ENV, raising=False)
    else:
        monkeypatch.setenv(live.LIVE_ENV, env)

    assert live.live_enabled(fake_config(markexpr)) is enabled


@pytest.mark.parametrize(("env", "markexpr"), [(None, "live"), ("1", ""), (None, "")])
def test_without_both_every_live_item_is_skipped(
    monkeypatch: pytest.MonkeyPatch, env: str | None, markexpr: str
) -> None:
    monkeypatch.delenv(live.LIVE_ENV, raising=False)
    if env is not None:
        monkeypatch.setenv(live.LIVE_ENV, env)
    items = [FakeItem(True), FakeItem(False)]

    live.skip_live(fake_config(markexpr), items)  # type: ignore[arg-type]

    assert [len(item.added) for item in items] == [1, 0]
    marker = items[0].added[0]
    assert marker.name == "skip"
    assert marker.kwargs["reason"] == live.SKIP_REASON
    assert "DEWELOPERUCH_LIVE=1" in live.SKIP_REASON and "-m live" in live.SKIP_REASON
    assert "D9" in live.SKIP_REASON


def test_with_both_nothing_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(live.LIVE_ENV, "1")
    items = [FakeItem(True)]

    live.skip_live(fake_config("live"), items)  # type: ignore[arg-type]

    assert items[0].added == []


@pytest.mark.parametrize("module", [test_live_mcp, test_live_cli, test_live_recon])
def test_every_e2e_module_is_marked_live(module: Any) -> None:
    assert module.pytestmark.name == "live"


def test_every_e2e_module_is_listed_here() -> None:
    modules = {path.stem for path in E2E.glob("test_*.py")}

    assert modules == {"test_live_mcp", "test_live_cli", "test_live_recon"}


def test_in_this_session_every_e2e_test_is_skipped(request: pytest.FixtureRequest) -> None:
    """The default run (no variable, no ``-m live``) collects the live tests and skips
    each one before its fixtures run: no server, no CLI, no probe is started."""
    if live.live_enabled(request.config):
        pytest.skip("sesja z włączonym zestawem live")
    e2e_items = [item for item in request.session.items if E2E in Path(item.path).parents]

    for item in e2e_items:
        assert item.get_closest_marker("live") is not None, item.nodeid
        skips = [mark for mark in item.iter_markers("skip")]
        assert any(mark.kwargs.get("reason") == live.SKIP_REASON for mark in skips), item.nodeid


# --- the helpers ---------------------------------------------------------------------------


def test_budget_ends_the_session_past_its_limit() -> None:
    budget = live.Budget(limit=3)
    budget.spend(2, "pierwsze")
    budget.spend(0, "bez zapytań")

    with pytest.raises(pytest.exit.Exception) as caught:
        budget.spend(2, "drugie")

    assert caught.value.returncode == 1
    assert "4 > 3" in str(caught.value)
    assert budget.summary().splitlines() == [
        "Żywe zapytania: 4 (limit 3).",
        "  2 × pierwsze",
        "  2 × drugie",
    ]


def test_a_stop_ends_the_session() -> None:
    live.stop_on("Wynik bez blokady.", "MCP search_offers")

    with pytest.raises(pytest.exit.Exception) as caught:
        live.stop_on("STOP: HTTP 403. Przerwij...", "MCP search_offers")

    assert caught.value.returncode == live.EXIT_STOP == 3
    assert "zgłoś to użytkownikowi" in str(caught.value)


# --- leaks ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "/api/cities?q=krak",
        "brak propsa initialData",
        "?_rsc=1234",
        '{"invest_id": 1}',
        '{"sale_id": 1}',
        "/ceny-ofertowe/warszawa/mieszkania",
        "https://" + live.HOST + "/x",
        "<!DOCTYPE html><html>",
        "strona zgłasza NEXT_HTTP_ERROR_FALLBACK;404",
        '{"digest":"2417303245"}',
        "Next-Action: 7f3a",
        '{"buildId":"KD_IOP6G"}',
        "Traceback (most recent call last):",
        'File "/srv/app.py", line 1',
        "httpx.ConnectError: [Errno 61]",
        "For further information visit https://errors.pydantic.dev/2.14/v/literal_error",
    ],
)
def test_backend_details_in_text_are_leaks(text: str) -> None:
    assert live.leaks(text)


@pytest.mark.parametrize(
    "value",
    [
        {"sale": {}},
        {"items": [{"sale_id": 1}]},
        {"invest_id": 1},
        {"invest_rcn_id": 1},
        {"rcn": []},
        {"amount": 1},
        {"Invest": 1},
    ],
)
def test_backend_names_as_field_names_are_leaks(value: dict[str, Any]) -> None:
    assert live.leaks("", value)


def domain_field_names() -> set[str]:
    """Every field name of the MCP results (mcp_results), nested models included."""
    models = [
        model
        for model in vars(mcp_results).values()
        if isinstance(model, type) and issubclass(model, BaseModel)
    ]
    return {name for model in models for name in model.model_fields}


def test_domain_field_names_are_no_leaks() -> None:
    names = domain_field_names()

    assert {"investment_slug", "investment_name", "offers_total", "offers_omitted"} <= names
    assert live.leaks("", {name: 1 for name in names}) == []


@pytest.mark.parametrize(
    "text",
    [
        "Invest Komfort Spółka Akcyjna Sp.K.",  # a real developer (sample api.map_inv_visible)
        "invest-komfort-spolka-akcyjna",
        "Inwestycja 'invest-park' nie ma oferty 1.",
        "STOP: seria zapytań do deweloperuch.pl jest już przerwana",
        "Wyprzedaż: sale konferencyjne",
    ],
)
def test_values_are_not_checked_for_backend_names(text: str) -> None:
    """Field names only: real data (names, slugs echoed in messages) may contain them."""
    assert live.leaks(text, {"developer_name": text, "name": text}) == []


# --- links to public pages (D12, 2026-10-11) ------------------------------------------------

PAGES = identity.BASE_URL + "/ceny-ofertowe"
SMOLNA = PAGES + "/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna"
LIST = PAGES + "/krakow/mieszkania?filterPrice=0-700000&sortBy=amount&sortOrder=asc&page=1"


def as_result(value: dict[str, Any]) -> list[str]:
    """``live.leaks`` of a tool result: its text is its structured content as JSON."""
    return live.leaks(json.dumps(value, ensure_ascii=False, separators=(",", ":")), value)


@pytest.mark.parametrize(
    "value",
    [
        {"investment_url": SMOLNA},
        {"list_url": LIST, "items": [{"investment_url": SMOLNA}]},
        {"investment_url": SMOLNA, "developer_url": PAGES + "/sopot/deweloperzy/invest-komfort"},
        {"investment_url": PAGES + "/krak%C3%B3w/deweloperzy/a%2Fb/x"},
    ],
)
def test_page_links_in_link_fields_pass(value: dict[str, Any]) -> None:
    assert as_result(value) == []


@pytest.mark.parametrize(
    "value",
    [
        {"name": SMOLNA},  # a link in another field
        {"hint": f"Zobacz {LIST}"},
        {"investment_url": SMOLNA, "name": SMOLNA},  # the same link outside its field too
        {"curl": SMOLNA},  # a name that merely ends in "url"
        {"list_url": PAGES + "/warszawa/mieszkania?page=1&_rsc=abcd1234"},
        {"list_url": identity.BASE_URL + "/api/cities?q=krak"},
        {"list_url": identity.BASE_URL + "/ceny-ofertowe/../api/cities"},
        {"list_url": identity.BASE_URL + "/statystyki/ceny-transakcyjne/mieszkania/krakow"},
        {"investment_url": "https://example.com/ceny-ofertowe/sopot/deweloperzy/x/smolna"},
        {"investment_url": "/ceny-ofertowe/sopot/deweloperzy/x/smolna"},
        {"investment_url": SMOLNA + " " + SMOLNA},
        {"url": SMOLNA},  # fields are named after what they point to: *_url only
        # only the three routes links.py builds [P], each segment a plain slug
        {"list_url": identity.BASE_URL + "/ceny-ofertowe/../statystyki/x"},
        {"investment_url": identity.BASE_URL + "/ceny-ofertowe/%2e%2e/statystyki"},
        {"investment_url": PAGES + "/%2E%2E/deweloperzy/atal/smolna"},
        {"investment_url": PAGES + "/sopot/deweloperzy/atal/smolna%2e"},
        {"investment_url": PAGES + "/./deweloperzy/atal/smolna"},
        {"investment_url": PAGES + "/sopot/deweloperzy/atal/smolna/raport-inwestycji"},
        {"list_url": PAGES + "/x/y/z/w/v?q=1"},
        {"list_url": PAGES + "/warszawa/inwestycje"},
        {"developer_url": PAGES + "/sopot/deweloperzy"},
        {"developer_url": PAGES + "/sopot/deweloperzy/"},
    ],
)
def test_links_elsewhere_or_of_another_kind_are_leaks(value: dict[str, Any]) -> None:
    assert as_result(value)


def test_a_link_in_an_error_message_is_a_leak() -> None:
    assert live.leaks(f"Nie znaleziono inwestycji 'smolna'. Zobacz {SMOLNA}")


def test_the_tool_listing_has_no_leaks() -> None:
    snapshot = json.loads((TESTS / "snapshots" / "mcp_tools.json").read_text(encoding="utf-8"))

    live.assert_listing_clean(snapshot["tools"])
    with pytest.raises(AssertionError, match="invest_id"):
        live.assert_listing_clean([{"inputSchema": {"properties": {"invest_id": {}}}}])


@pytest.fixture
def unix_sockets() -> None:
    """The SDK's in-memory client needs an event loop: Unix sockets only."""
    live.unix_sockets_only()


CALLS: list[tuple[str, dict[str, Any]]] = [
    ("search_locations", {"query": "krak"}),
    ("search_offers", {"city": "warszawa"}),
    ("search_offers", {"city": "polska"}),
    ("search_offers", {"city": UNKNOWN_CITY}),
    ("search_offers", {"city": "Kraków"}),
    ("search_offers", {"city": "warszawa", "per_page": 100}),
    ("get_investment", {"investment_slug": "smolna", "include_history": True}),
    ("get_offer", {"offer_id": 2377, "investment_slug": "smolna"}),
    ("get_offer", {"offer_id": 999, "investment_slug": "smolna"}),
]


def test_real_results_pass_the_leak_check(tmp_path: Path, unix_sockets: None) -> None:
    """Every tool on the samples and the real RSC payloads, errors included: no false
    alarms, though the results carry a developer called "Invest Komfort"."""
    limiter = RequestLimiter(tmp_path, min_interval=0, testing_only_allow_fast_interval=True)
    server = mcp_server.build_server(lambda: services.Session(limiter=limiter))

    async def every_call() -> list[CallToolResult]:
        async with Client(server) as client:
            return [await client.call_tool(tool, arguments) for tool, arguments in CALLS]

    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        location_routes(router)
        unknown_city_route(router)
        offers_route(router)
        investment_routes(router)
        results = anyio.run(every_call)

    calls = [live.Call(t, a, r, 0) for (t, a), r in zip(CALLS, results, strict=True)]
    for call in calls:
        live.assert_no_leaks(call)
    assert [call.error for call in calls] == [False, False, False, True, True, True] + [
        False,
        False,
        True,
    ]
    assert "Invest Komfort" in calls[6].text
    # Links (D12) in their fields pass: the list, its investments, the offer's pages.
    assert calls[1].text.count('"investment_url":"' + PAGES) == 10
    assert '"list_url":"' + PAGES + "/warszawa/mieszkania?" in calls[1].text
    assert '"developer_url":"' + PAGES in calls[7].text
    # The SDK's validation error: the field and the rule, no link to pydantic's docs.
    assert "per_page" in calls[5].text and "Input should be 10 or 50" in calls[5].text


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [("ok\n", "Traceback (most recent call last):\n"), ("\x1b[31mczerwony\n", "")],
)
def test_cli_output_must_be_readable(stdout: str, stderr: str) -> None:
    with pytest.raises(AssertionError):
        live.Run(("offers",), 0, stdout, stderr, 0).readable()

    live.Run(("offers",), 0, "Pasujące oferty: 13 324 · zł\n", "", 0).readable()


# --- the safeguards on a fake server ---------------------------------------------------------

# The real entry point with the network blocked and mocked: the offers list answers with
# the real RSC responses, "awaria" with a 500, the cities with a 403 (a STOP, recorded
# in this test's private XDG_CACHE_HOME).
FAKE_SERVER = """\
import pytest_socket
pytest_socket.disable_socket(allow_unix_socket=True)
import sys
sys.path[:0] = [{tests!r}]
import respx
from service_mocks import offers_route, unknown_city_route
with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
    router.get(path="/api/cities").respond(403)
    router.route(method="GET", path="/ceny-ofertowe/awaria/mieszkania").respond(500)
    unknown_city_route(router)
    offers_route(router)
    from deweloperuch_mcp.mcp_server import main
    main()
"""


@pytest.fixture
def fake_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``live.server_script`` replaced by a script that starts the fake server."""
    code = tmp_path / "fake_server.py"
    code.write_text(FAKE_SERVER.format(tests=str(TESTS)), encoding="utf-8")
    script = tmp_path / "deweloperuch-mcp"
    script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{code}"\n', encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setattr(live, "server_script", lambda: script)
    return script


def test_the_harness_counts_paces_and_ends_the_session(fake_server: Path, tmp_path: Path) -> None:
    budget = live.Budget(limit=10)

    with live.mcp_server(tmp_path / "server-stderr.log", budget) as mcp:
        first = mcp.call_network("search_offers", city="warszawa")
        again = mcp.call("search_offers", city="warszawa")
        with pytest.raises(pytest.exit.Exception) as blind:
            mcp.call_network("search_offers", city="warszawa")  # cached: nothing logged
        calls, logged = mcp.parallel(
            ("search_offers", {"city": "warszawa", "page": 2}),
            ("search_offers", {"city": "polska"}),
        )
        with pytest.raises(pytest.exit.Exception) as unavailable:  # checked in parallel too
            mcp.parallel(
                ("search_offers", {"city": "awaria"}),
                ("search_offers", {"city": "warszawa", "page": 3}),
            )
        with pytest.raises(pytest.exit.Exception) as stopped:
            mcp.call("search_locations", query="krak")

    assert (first.sent, again.sent) == (1, 0)
    assert blind.value.returncode == 1 and "Licznik zapytań nie działa" in str(blind.value)
    assert [call.error for call in calls] == [False, False] and calls[0].sent == 2
    assert len(logged) == 2 and logged[1] - logged[0] >= 0.9
    assert unavailable.value.returncode == live.EXIT_UNAVAILABLE == 4
    assert stopped.value.returncode == live.EXIT_STOP == 3
    assert "STOP: MCP search_locations" in str(stopped.value)
    assert budget.total == 6  # 1 + 2 + the 500 with page 3 + the 403


# --- the safeguards of the CLI, probe and scripts --------------------------------------------


def completed(code: int, stdout: str = "", stderr: str = "") -> Any:
    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, code, stdout, stderr)

    return run


def test_run_cli_counts_the_requests_in_its_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def cli(command: list[str]) -> subprocess.CompletedProcess[str]:
        log = Path(command[3])  # [python, -c, CLI, log, *args]
        log.write_text("INFO HTTP Request: GET a\nINFO HTTP Request: GET b\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "Lokalizacje: 1.\n", "")

    monkeypatch.setattr(live, "_run", cli)
    budget = live.Budget(limit=10)

    run = live.run_cli(budget, tmp_path, "locations", "search", "Kraków")

    assert (run.code, run.sent, budget.total) == (0, 2, 2)
    assert run.args == ("locations", "search", "Kraków")


@pytest.mark.parametrize(
    ("code", "stderr", "ends_with"),
    [
        (3, "Błąd: STOP: HTTP 403.", live.EXIT_STOP),
        (1, "Błąd: STOP: seria zapytań jest już przerwana.", live.EXIT_STOP),
        (4, "Błąd: Serwis odpowiedział błędem HTTP 503. Nic nie ponawiam; spróbuj później.", 4),
    ],
)
def test_run_cli_ends_the_session_on_a_stop_or_a_service_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int, stderr: str, ends_with: int
) -> None:
    monkeypatch.setattr(live, "_run", completed(code, stderr=stderr))

    with pytest.raises(pytest.exit.Exception) as ended:
        live.run_cli(live.Budget(limit=10), tmp_path, "offers", "search", "krakow")

    assert ended.value.returncode == ends_with


@pytest.mark.parametrize(("code", "sent"), [(0, 1), (6, 1), (2, 0), (5, 0)])
def test_run_probe_counts_one_request_unless_nothing_was_sent(
    monkeypatch: pytest.MonkeyPatch, code: int, sent: int
) -> None:
    monkeypatch.setattr(live, "_run", completed(code))
    budget = live.Budget(limit=10)

    run = live.run_probe(budget, "api", "/api/cities?q=krak")

    assert (run.sent, budget.total) == (sent, sent)


@pytest.mark.parametrize("code", [live.EXIT_STOP, live.EXIT_UNAVAILABLE])
def test_run_probe_ends_the_session_on_a_stop_or_a_service_error(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    monkeypatch.setattr(live, "_run", completed(code, stderr="HTTP 403, text/html"))
    budget = live.Budget(limit=10)

    with pytest.raises(pytest.exit.Exception) as ended:
        live.run_probe(budget, "api", "/api/cities?q=krak")

    assert ended.value.returncode == code
    assert budget.total == 1  # counted before the session ends


def test_run_script_ends_the_session_on_a_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live, "_run", completed(3, stdout="STOP aktywny: HTTP 403."))

    with pytest.raises(pytest.exit.Exception) as ended:
        live.run_script("deweloperuch", "stop", "status")

    assert ended.value.returncode == live.EXIT_STOP
