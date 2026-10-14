"""Tests of ``deweloperuch_mcp.consumers.mcp.server``."""

import json
import logging
import os
import re
import threading
from importlib import metadata
from pathlib import Path
from typing import Any

import anyio
import httpx
import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.consumers.mcp import server as mcp_server
from deweloperuch_mcp.usecases.get_government_statistics import GetGovernmentStatistics
from deweloperuch_mcp.usecases.get_investment import GetInvestment
from deweloperuch_mcp.usecases.get_offer import GetOffer
from deweloperuch_mcp.usecases.search_locations import SearchLocations
from deweloperuch_mcp.usecases.search_offers import SearchOffers
from support.builders.investments import investment_with_offers
from support.builders.offers import offers_page
from support.checks.leaks import BACKEND_NAMES, SIZE_BUDGET, SIZE_BUDGET_50
from support.paths import PROMPTS_SNAPSHOT, SNAPSHOT
from support.providers.mcp import (
    PROMPTS,
    TOOL_NAME,
    TOOLS,
    Sessions,
    call,
    data,
    keys,
    listing,
    prompts,
    properties,
    rendered,
    text,
    tools,
    tools_named,
    with_client,
)
from support.providers.routes.government_statistics import stats_routes
from support.providers.routes.investments import INVESTMENT, investment_routes
from support.providers.routes.locations import location_routes
from support.providers.routes.offers import offers_route
from support.providers.rsc import offers_payload

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


UPDATE_SNAPSHOTS = "DEWELOPERUCH_UPDATE_SNAPSHOTS"


PROMPT_EXAMPLES: tuple[tuple[str, dict[str, str], list[str]], ...] = (
    (
        "znajdz_mieszkanie",
        {
            "miasto": "Kraków",
            "budzet_max": "800000",
            "metraz_min": "40",
            "metraz_max": "60",
            "dzielnica": "Podgórze",
        },
        ["search_locations", "search_offers", "get_offer"],
    ),
    ("znajdz_mieszkanie", {"miasto": "Gdańsk"}, ["search_locations", "search_offers", "get_offer"]),
    (
        "ocen_oferte",
        {"offer_id": "2377", "investment_slug": "smolna"},
        ["get_offer", "get_market_statistics", "get_investment", "estimate_property_value"],
    ),
    (
        "przeswietl_dewelopera",
        {"nazwa": "Atal", "miasto": "Kraków"},
        [
            "search_developers",
            "search_locations",
            "get_developer",
            "search_investments",
            "get_investment",
        ],
    ),
    (
        "przeswietl_dewelopera",
        {"nazwa": "Dom Development"},
        ["search_developers", "get_developer", "search_investments", "get_investment"],
    ),
    (
        "porownaj_miasta",
        {"miasta": "Kraków, Wrocław, Gdańsk"},
        [
            "search_locations",
            "get_market_statistics",
            "get_transaction_statistics",
            "get_government_statistics",
        ],
    ),
)
"""Arguments a person gives each prompt, and the tools its message names, in that order."""


def test_the_server_lists_its_read_only_tools(server: MCPServer[bootstrap.Session]) -> None:
    tools_listed = listing(server)["tools"]

    assert [tool["name"] for tool in tools_listed] == list(TOOLS)
    for tool in tools_listed:
        assert tool["annotations"] == {"readOnlyHint": True, "openWorldHint": True}
        assert tool["title"]
        assert tool["outputSchema"]["type"] == "object"
        for name, field in tool["inputSchema"]["properties"].items():
            assert field.get("description"), (tool["name"], name)
            # Polish titles instead of pydantic's English ones ("Price Min").
            assert field["title"] != name.replace("_", " ").title(), (tool["name"], name)


def test_descriptions_and_schemas_have_no_backend_names(
    server: MCPServer[bootstrap.Session],
) -> None:
    seen = listing(server)
    assert not BACKEND_NAMES.search(seen["server"]["instructions"])
    for tool in seen["tools"]:
        visible = json.dumps(
            [tool["title"], tool["description"], tool["inputSchema"]], ensure_ascii=False
        )
        assert not BACKEND_NAMES.search(visible), (tool["name"], BACKEND_NAMES.findall(visible))
        assert not BACKEND_NAMES.search(" ".join(keys(tool["outputSchema"]))), tool["name"]


def test_descriptions_say_when_to_use_the_tool_and_its_limits(
    server: MCPServer[bootstrap.Session],
) -> None:
    described = {name: tool["description"] for name, tool in tools(server).items()}

    assert "city_slug" in described["search_locations"]
    assert "total jest null, gdy wyników jest więcej" in described["search_locations"]
    assert "offer_count=0 nie mają ofert" in described["search_locations"]
    assert "rynek pierwotny" in described["search_offers"]
    assert "20 stron" in described["search_offers"]
    assert "truncated" in described["search_offers"]
    assert (
        "Pozycje są skrócone; szczegóły oferty i historię ceny daje get_offer"
        in (described["search_offers"])
    )
    assert "investment_slug" in described["get_offer"]
    assert "offers_omitted > 0 znaczy, że lista jest niepełna" in described["get_investment"]
    assert "offers_total to liczba z serwisu" in described["get_investment"]
    stats = described["get_government_statistics"]
    assert "GUS i NBP" in stats and "search_offers" in stats
    assert "domyślnie ostatnie 12 okresów" in stats and "najwyżej 120" in stats
    assert "nbp_prices: tylko 17 dużych miast i 3 agregaty, nie polska" in stats
    assert "note" in stats and "stats_url" in stats
    assert "Nie każdy zestaw jest dostępny dla każdej lokalizacji" in stats
    assert "z opóźnieniem" in stats
    market = described["get_market_statistics"]
    assert "tylko aktywne oferty" in market and "polska nie działa" in market
    assert "mogą się nieco różnić od total w search_offers" in market
    assert "developer_slug weź z search_developers (po nazwie)" in described["get_developer"]
    assert "cities zawsze obejmuje całą Polskę" in described["get_developer"]
    assert "suspicious_reduction" in described["get_offer"]
    assert "lowest_price_30d" in described["get_offer"]
    assert "Nie filtruje po dzielnicy" not in described["search_offers"]
    assert "ani po deweloperze" in described["search_offers"]
    for description in described.values():
        assert len(description) <= 1_200


def test_the_other_input_schemas(server: MCPServer[bootstrap.Session]) -> None:
    schemas = {name: tool["inputSchema"] for name, tool in tools(server).items()}

    assert schemas["search_locations"]["required"] == ["query"]
    assert schemas["get_offer"]["required"] == ["offer_id", "investment_slug"]
    assert schemas["get_offer"]["properties"]["offer_id"]["minimum"] == 1
    investment = schemas["get_investment"]
    assert investment["required"] == ["investment_slug"]
    history = investment["properties"]["include_history"]
    assert (history["type"], history["default"]) == ("boolean", False)
    limit = investment["properties"]["limit"]
    assert (limit["default"], limit["minimum"], limit["maximum"]) == (20, 0, 200)
    assert limit["description"].startswith(
        "Najwięcej ofert w wyniku (najpierw aktywne), domyślnie 20, 0 = tylko podsumowanie"
    )
    assert limit["description"].endswith(
        "Maksimum 200 daje ok. 60 tys. znaków; zwykle wystarcza domyślne 20."
    )


def test_output_schemas_describe_what_names_do_not_say(
    server: MCPServer[bootstrap.Session],
) -> None:
    described = {
        "price",
        "area_m2",
        "price_per_m2",
        "status",
        "price_change_since_start",
        "price_change_since_start_pct",
        "last_price_change_kind",
        "last_price_change_pct",
        "offers_total",
        "offer_count",
        "kind",
        "source",
        "frequency",
        "unit",
        "values",
        "note",
        "stats_url",
        "periods",
    }
    seen: set[str] = set()
    for tool in tools(server).values():
        for name, field in properties(tool["outputSchema"]):
            if name in described:
                seen.add(name)
                assert field.get("description"), (tool["name"], name)
                # Value sets the backend may extend stay strings: no enum to break on.
                assert "enum" not in json.dumps(field), (tool["name"], name)
    assert seen == described


def test_the_listing_matches_the_snapshot(server: MCPServer[bootstrap.Session]) -> None:
    """Server name, instructions and tools as a client sees them. After an intended
    change: DEWELOPERUCH_UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/consumers/mcp/"""
    seen = json.dumps(listing(server), ensure_ascii=False, indent=2) + "\n"
    if os.environ.get(UPDATE_SNAPSHOTS) == "1":
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(seen, encoding="utf-8")

    assert seen == SNAPSHOT.read_text(encoding="utf-8")


def test_the_server_lists_its_prompts_with_their_arguments(
    server: MCPServer[bootstrap.Session],
) -> None:
    listed = {prompt["name"]: prompt for prompt in prompts(server)}

    assert list(listed) == list(PROMPTS)
    assert {
        name: [(argument["name"], argument["required"]) for argument in prompt["arguments"]]
        for name, prompt in listed.items()
    } == {
        "znajdz_mieszkanie": [
            ("miasto", True),
            ("budzet_max", False),
            ("metraz_min", False),
            ("metraz_max", False),
            ("dzielnica", False),
        ],
        "ocen_oferte": [("offer_id", True), ("investment_slug", True)],
        "przeswietl_dewelopera": [("nazwa", True), ("miasto", False)],
        "porownaj_miasta": [("miasta", True)],
    }
    for prompt in listed.values():
        assert prompt["title"] and prompt["description"], prompt["name"]
        assert all(argument.get("description") for argument in prompt["arguments"])
        assert not BACKEND_NAMES.search(json.dumps(prompt, ensure_ascii=False)), prompt["name"]


@pytest.mark.parametrize(("prompt", "arguments", "named"), PROMPT_EXAMPLES)
def test_a_prompt_is_one_user_message_naming_its_tools_in_order(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    prompt: str,
    arguments: dict[str, str],
    named: list[str],
) -> None:
    """A prompt is text that starts a conversation: it calls no tool and sends nothing."""
    messages = rendered(server, prompt, arguments)["messages"]

    assert len(messages) == 1
    assert (messages[0]["role"], messages[0]["content"]["type"]) == ("user", "text")
    said = messages[0]["content"]["text"]
    assert tools_named(said) == named
    assert set(named) <= set(TOOLS)
    assert not BACKEND_NAMES.search(said), BACKEND_NAMES.findall(said)
    assert service.calls.call_count == 0


def test_the_prompts_match_the_snapshot(server: MCPServer[bootstrap.Session]) -> None:
    """The prompts as a client lists them and their messages for ``PROMPT_EXAMPLES``.
    After an intended change: DEWELOPERUCH_UPDATE_SNAPSHOTS=1 uv run pytest
    tests/unit/consumers/mcp/test_server.py"""
    seen = {
        "prompts": prompts(server),
        "rendered": [
            {"prompt": prompt, "arguments": arguments, **rendered(server, prompt, arguments)}
            for prompt, arguments, _ in PROMPT_EXAMPLES
        ],
    }
    written = json.dumps(seen, ensure_ascii=False, indent=2) + "\n"
    if os.environ.get(UPDATE_SNAPSHOTS) == "1":
        PROMPTS_SNAPSHOT.write_text(written, encoding="utf-8")

    assert written == PROMPTS_SNAPSHOT.read_text(encoding="utf-8")


def test_server_info_and_instructions(server: MCPServer[bootstrap.Session]) -> None:
    async def info(client: Client) -> tuple[str | None, str | None, str | None]:
        server_info = client.server_info
        if server_info is None:
            return None, None, client.instructions
        return server_info.name, server_info.version, client.instructions

    name, version, instructions = with_client(server, info)

    assert (name, version) == ("deweloperuch", metadata.version("deweloperuch-mcp"))
    assert instructions is not None
    assert "search_locations" in instructions and "STOP" in instructions
    assert (
        "Gdy błąd narzędzia zawiera STOP, przestań używać tych narzędzi, niczego nie "
        "ponawiaj, nie szukaj obejścia i powiedz o tym użytkownikowi, podając powód z "
        "komunikatu. Dalsze kroki należą do użytkownika; sam niczego nie odblokowuj ani nie "
        "uruchamiaj ponownie." in instructions
    )
    # Nothing that reads as "the STOP can be lifted" or "restart the server and go on".
    assert not re.search(r"zdejm|zdjęci|restart|dopóki", instructions, re.I)
    assert "Gdy narzędzie odrzuci argumenty, popraw wskazane pola" in instructions
    assert "po angielsku" not in instructions


@pytest.mark.parametrize(
    ("arguments", "field"),
    [
        ({"city": "warszawa", "per_page": 20}, "per_page"),
        ({"city": "warszawa", "page": 21}, "page"),
        ({"city": "warszawa", "sort": "rooms_asc"}, "sort"),
        ({"city": "warszawa", "price_max": -1}, "price_max"),
        ({}, "city"),
    ],
)
def test_arguments_off_the_schema_are_tool_errors(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    arguments: dict[str, Any],
    field: str,
) -> None:
    result = call(server, "search_offers", **arguments)

    assert result.is_error is True
    assert field in text(result)
    assert service.calls.call_count == 0


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        (
            "search_offers",
            {"city": "warszawa", "per_page": 100},
            "Błędny argument narzędzia search_offers: per_page musi być jedną z wartości 10, "
            "50, podano 100.",
        ),
        (
            "search_offers",
            {"city": "warszawa", "page": 21, "sort": "rooms_asc"},
            "Błędne argumenty narzędzia search_offers: sort musi być jedną z wartości "
            "price_asc, price_desc, price_per_m2_asc, price_per_m2_desc, area_asc, area_desc, "
            'biggest_drop albo pusty, podano "rooms_asc"; page musi być liczbą całkowitą z '
            "zakresu 1–20, podano 21.",
        ),
        (
            "search_offers",
            {"city": "warszawa", "price_min": "10.5", "price_dropped": "x"},
            "Błędne argumenty narzędzia search_offers: price_min musi być liczbą całkowitą z "
            'zakresu 0–99999999 albo pusty, podano "10.5"; price_dropped musi być true albo '
            'false, podano "x".',
        ),
        (
            "search_offers",
            {"per_page": 10},
            "Błędny argument narzędzia search_offers: city: brak wymaganego argumentu.",
        ),
        (
            "get_developer",
            {"developer_slug": "atal", "limit": 0},
            "Błędny argument narzędzia get_developer: limit musi być liczbą całkowitą z "
            "zakresu 1–100, podano 0.",
        ),
        (
            "get_market_statistics",
            {"city": "sopot", "top_developers": 31},
            "Błędny argument narzędzia get_market_statistics: top_developers musi być liczbą "
            "całkowitą z zakresu 1–30, podano 31.",
        ),
        (
            "get_offer",
            {"offer_id": "\x1b[31m", "investment_slug": "smolna"},
            "Błędny argument narzędzia get_offer: offer_id musi być liczbą całkowitą nie "
            'mniejszą niż 1, podano "\\u001b[31m".',
        ),
    ],
)
def test_schema_errors_say_in_polish_what_each_field_allows(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    tool: str,
    arguments: dict[str, Any],
    message: str,
) -> None:
    """D12: the field, what its schema allows and what was given (escaped), instead of
    pydantic's English text with links to its docs."""
    result = call(server, tool, **arguments)

    assert result.is_error is True
    assert text(result) == message + " Popraw i ponów; nic nie zostało wysłane."
    assert "pydantic.dev" not in text(result) and "\x1b" not in text(result)
    assert service.calls.call_count == 0


def test_schema_errors_are_logged_by_field_name_only(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The cause of the rewritten error stays pydantic's, so the SDK logs only the names
    of the rejected fields: the values are the caller's data."""
    caplog.set_level(logging.INFO)

    call(server, "search_offers", city="warszawa", per_page=100)

    sdk = [r.getMessage() for r in caplog.records if r.name.startswith("mcp.server")]
    assert "Tool 'search_offers' rejected arguments: ['per_page']" in sdk
    assert not any("100" in line for line in sdk)


def test_unknown_arguments_are_refused_with_the_allowed_names(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """A model's typo (max_price) is a tool error naming it and the tool's arguments; the
    SDK alone would drop it and search without the limit. Nothing is sent."""
    result = call(server, "search_offers", city="warszawa", max_price=500_000)

    assert result.is_error is True
    assert text(result) == (
        "Nieznany argument narzędzia search_offers: 'max_price'. Dozwolone argumenty: city, "
        "price_min, price_max, area_min, area_max, price_per_m2_min, price_per_m2_max, "
        "district, price_dropped, status, sort, page, per_page. Popraw nazwy i ponów; nic "
        "nie zostało wysłane."
    )
    assert service.calls.call_count == 0


def test_unknown_argument_names_are_escaped_cut_and_counted(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """Names come from the caller: control characters escaped, long names cut, at most
    ten listed."""
    given = {f"x{index:02}": 1 for index in range(11)} | {"\x1b]0;evil\x07" + "y" * 80: 1}

    result = call(server, "get_offer", offer_id=1, investment_slug="smolna", **given)

    message = text(result)
    assert result.is_error is True
    assert message.startswith(
        "Nieznane argumenty narzędzia get_offer: '\\x1b]0;evil\\x07" + "y" * 51 + "', 'x00', "
    )
    assert "'x08' (i 2 innych). Dozwolone argumenty: offer_id, investment_slug." in message
    assert "\x1b" not in message
    assert service.calls.call_count == 0


def test_every_input_schema_is_closed(server: MCPServer[bootstrap.Session]) -> None:
    for name, tool in tools(server).items():
        assert tool["inputSchema"]["additionalProperties"] is False, name


def test_one_session_for_the_server_closed_when_it_stops(
    server: MCPServer[bootstrap.Session], sessions: Sessions, service: respx.MockRouter
) -> None:
    location_routes(service)
    investment_routes(service)

    async def calls(client: Client) -> None:
        data(await client.call_tool("search_locations", {"query": "krak"}))
        data(await client.call_tool("get_investment", {"investment_slug": "smolna"}))
        data(await client.call_tool("get_offer", {"offer_id": 2377, "investment_slug": "smolna"}))
        assert [session.closed for session in sessions.opened] == [False]

    with_client(server, calls)

    assert len(sessions.opened) == 1
    assert sessions.opened[0].closed
    assert service.calls.call_count == 4  # the investment of get_offer comes from the cache


def test_the_default_server_opens_one_services_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, service: respx.MockRouter
) -> None:
    """``build_server()`` as ``main()`` builds it: ``bootstrap.Session()`` once per run."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    opened: list[bootstrap.Session] = []

    class Recorded(bootstrap.Session):
        def __init__(self) -> None:
            super().__init__()
            opened.append(self)

    monkeypatch.setattr(bootstrap, "Session", Recorded)

    result = call(
        mcp_server.build_server(), "search_offers", city="warszawa", price_min=7, price_max=5
    )

    assert result.is_error is True and "price_min" in text(result)
    assert len(opened) == 1
    assert opened[0].closed
    assert service.calls.call_count == 0


def test_parallel_calls_run_in_worker_threads(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The services are synchronous: each call runs in a worker thread, so parallel calls
    do not block the event loop; the limiter still sends one request at a time."""
    location_routes(service)
    offers_route(service)
    investment_routes(service)
    stats_routes(service)
    threads: list[str] = []
    for use_case, method in (
        (SearchLocations, "execute"),
        (SearchOffers, "execute"),
        (GetOffer, "execute"),
        (GetInvestment, "execute"),
        (GetGovernmentStatistics, "execute"),
    ):
        original = getattr(use_case, method)

        def recorded(*args: Any, original: Any = original, **kwargs: Any) -> Any:
            threads.append(threading.current_thread().name)
            return original(*args, **kwargs)

        monkeypatch.setattr(use_case, method, recorded)

    async def parallel(client: Client) -> list[CallToolResult]:
        results: list[CallToolResult] = []

        async def one(tool: str, arguments: dict[str, Any]) -> None:
            results.append(await client.call_tool(tool, arguments))

        async with anyio.create_task_group() as group:
            group.start_soon(one, "search_locations", {"query": "krak"})
            group.start_soon(one, "search_offers", {"city": "warszawa"})
            group.start_soon(one, "get_offer", {"offer_id": 2377, "investment_slug": "smolna"})
            group.start_soon(one, "get_investment", {"investment_slug": "smolna"})
            group.start_soon(
                one, "get_government_statistics", {"location": "polska", "dataset": "wages"}
            )
        return results

    results = with_client(server, parallel)

    assert [result.is_error for result in results] == [False] * 5
    assert len(threads) == 5
    assert threading.main_thread().name not in threads


def test_tools_write_nothing_to_stdout(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """stdout is the protocol channel of stdio: results, errors and crashes stay off it."""
    location_routes(service)
    service.get(INVESTMENT).respond(403)

    def crash(*args: object, **kwargs: object) -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(GetOffer, "execute", crash)

    async def calls(client: Client) -> list[bool]:
        return [
            (await client.call_tool("search_locations", {"query": "krak"})).is_error,
            (
                await client.call_tool(
                    "search_offers", {"city": "warszawa", "price_min": 7, "price_max": 5}
                )
            ).is_error,
            (
                await client.call_tool("get_offer", {"offer_id": 2377, "investment_slug": "x"})
            ).is_error,
            (await client.call_tool("get_investment", {"investment_slug": "smolna"})).is_error,
        ]

    assert with_client(server, calls) == [False, True, True, True]
    assert capfd.readouterr().out == ""


def test_result_sizes_on_the_samples(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """Sizes of the text content (compact JSON) on full pages built from the samples.

    The defaults fit the budget; the per-item sizes in the descriptions of per_page and
    limit hold ("ok. 450" and "ok. 300" characters), so results do not grow unnoticed.
    With the links (D12, 2026-10-11) and the developer's slug (2026-10-13) an offer of a
    page is about 450 characters, 490 with its city (more for a long developer slug): 10
    offers about 4.7k, 50 about 22-25k."""

    def full_page(request: httpx.Request) -> httpx.Response:
        page = offers_page(count=int(request.url.params["perPage"]))
        return httpx.Response(
            200,
            content=offers_payload(page),
            headers={"Content-Type": "text/x-component"},
        )

    service.route(method="GET", path__startswith="/ceny-ofertowe/").mock(side_effect=full_page)
    investment_routes(service, investment_with_offers(200))

    async def sizes(client: Client) -> dict[str, int]:
        calls: dict[str, tuple[str, dict[str, Any]]] = {
            "page_10": ("search_offers", {"city": "warszawa"}),
            "page_50": ("search_offers", {"city": "warszawa", "per_page": 50}),
            "page_50_country": ("search_offers", {"city": "polska", "per_page": 50}),
            "investment_20": ("get_investment", {"investment_slug": "smolna"}),
            "investment_200": ("get_investment", {"investment_slug": "smolna", "limit": 200}),
        }
        return {
            name: len(text(await client.call_tool(tool, arguments)))
            for name, (tool, arguments) in calls.items()
        }

    measured = with_client(server, sizes)

    assert measured["page_10"] <= SIZE_BUDGET
    assert measured["investment_20"] <= SIZE_BUDGET
    assert measured["page_50"] <= 50 * 470 < SIZE_BUDGET_50
    assert measured["page_50_country"] <= 50 * 500 < SIZE_BUDGET_50
    assert measured["investment_200"] <= 200 * 320


def test_every_tool_named_in_a_description_or_the_instructions_exists(
    server: MCPServer[bootstrap.Session],
) -> None:
    """A description pointing the model to a tool that does not exist (renamed, merged
    away) sends it nowhere: every tool name in the texts the model reads is a tool."""
    seen = listing(server)
    texts = [seen["server"]["instructions"]] + [
        json.dumps(
            [tool["description"], tool["inputSchema"], tool["outputSchema"]], ensure_ascii=False
        )
        for tool in seen["tools"]
    ]
    named = {name for text in texts for name in TOOL_NAME.findall(text)}

    assert named - set(TOOLS) == set()
    assert {"search_developers", "estimate_property_value"} <= named  # the check sees them
