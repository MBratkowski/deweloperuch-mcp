"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.rank_locations_tool``."""

import json
import re
from typing import Any

import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.models.errors import SERVICE_CHANGED
from deweloperuch_mcp.models.location_ranking import PRICE_ORDER_MIN_TRANSACTIONS, RankingOrder
from support.builders.rankings import INJECTED, LEAKS, RANKING_PAGE, ranking_with_places
from support.providers.mcp import call, data, keys, text, with_client
from support.providers.routes.rankings import (
    CITIES_2026_10_15,
    CITY_RANKING,
    POWIAT_RANKING,
    captured,
    captured_ranking_routes,
    ranking_routes,
)

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


TOOL = "rank_locations"


SIZE_BUDGET = 8_000
"""Characters of a result that fit the model's context comfortably (tests/test_mcp_server)."""


# D3: backend names never reach the model (RCN, the registry, may be named in text; not
# in keys); errors carry no paths or answers of the service.
BACKEND_NAMES = re.compile(r"sale|invest(?!ment)|amount|nazwa|avg|sqm|_rsc|/api/", re.I)


KEY_NAMES = re.compile(BACKEND_NAMES.pattern + "|rcn", re.I)


WARSZAWA = {
    "name": "Warszawa",
    "city_slug": "warszawa",
    "transaction_count": 3606,
    "price_per_m2": 16413,
    "area_m2": 48.8,
    "price": 780000,
}


POWIAT_WARSZAWA = {
    "name": "powiat Warszawa",
    "powiat_id": 302,
    "transaction_count": 351314,
    "price_per_m2": 16367,
    "area_m2": 48.6,
    "price": 780000,
}


LEFT_OUT = (
    "Przy sortowaniu po cenie pominięto miejsca z mniej niż 20 transakcjami (domyślny próg); "
    "wszystkie miejsca pokaże min_transactions=0."
)
"""The hint's word on the price orders' default threshold."""


def listed(server: MCPServer[bootstrap.Session]) -> dict[str, Any]:
    async def read(client: Client) -> dict[str, Any]:
        tools = await client.list_tools()
        found = [t for t in tools.tools if t.name == TOOL]
        return found[0].model_dump(mode="json", by_alias=True, exclude_none=True)

    return with_client(server, read)


def test_the_tool_is_read_only_and_says_what_it_cannot(
    server: MCPServer[bootstrap.Session],
) -> None:
    seen = listed(server)
    description = seen["description"]

    assert seen["annotations"] == {"readOnlyHint": True, "openWorldHint": True}
    assert seen["title"] == "Ranking miast i powiatów"
    assert seen["inputSchema"].get("required", []) == []
    assert len(description) <= 1_200
    for said in (
        "Rejestru Cen Nieruchomości (RCN)",
        "To ceny transakcyjne, nie ofertowe",
        "serwis nie podaje okresu",
        "czy ceny i metraż to średnie, czy mediany",
        "Liczby transakcji powiatów obejmują wiele lat: służą tylko do uporządkowania",
        "nie porównuj ich z liczbami miejscowości",
        "dla trendu jednego miasta w czasie: get_transaction_statistics",
        "Zwraca min_transactions (zastosowany próg)",
        "Sortowanie po cenie domyślnie pomija miejsca poniżej "
        f"{PRICE_ORDER_MIN_TRANSACTIONS} transakcji (cena bywa przypadkowa)",
        "min_transactions=0 pokazuje wszystkie, np. 50 daje stabilniejsze ceny",
        "powiat_id jest informacyjny: żadne narzędzie go nie przyjmuje",
    ):
        assert said in description, said
    level = seen["inputSchema"]["properties"]["level"]["description"]
    assert "bez ranking_url i bez odpowiednika w search_locations" in level
    visible = json.dumps([seen["description"], seen["inputSchema"]], ensure_ascii=False)
    assert not BACKEND_NAMES.search(visible), BACKEND_NAMES.findall(visible)
    assert not [key for key in keys(seen["outputSchema"]) if KEY_NAMES.search(key)]


def test_the_output_schema_describes_every_field(server: MCPServer[bootstrap.Session]) -> None:
    """Averages or medians: said once in the description, not in each field; prices are
    numbers or null; powiat_id says no tool takes it."""
    schema = listed(server)["outputSchema"]
    result = schema["properties"]
    item = schema["$defs"]["RankedLocationItem"]["properties"]

    for name, field in [*result.items(), *item.items()]:
        assert name == "items" or field.get("description"), name
    for name in ("price_per_m2", "area_m2", "price"):
        assert item[name]["anyOf"] == [{"type": "number"}, {"type": "null"}], name
        assert "mediana" not in item[name]["description"]
    assert item["area_m2"]["description"] == "Metraż w m², podany przez serwis."
    assert "żadne narzędzie go nie przyjmuje" in item["powiat_id"]["description"]
    assert "domyślny: 20 przy sortowaniu po cenie" in result["min_transactions"]["description"]
    assert "pominięto małe miejsca" in result["hint"]["description"]


def test_the_input_schema(server: MCPServer[bootstrap.Session]) -> None:
    fields = listed(server)["inputSchema"]["properties"]

    assert list(fields) == ["level", "sort", "limit", "min_transactions"]
    assert (fields["level"]["enum"], fields["level"]["default"]) == (["city", "powiat"], "city")
    assert fields["sort"]["enum"] == [order.value for order in RankingOrder]
    assert fields["sort"]["default"] == "transactions_desc"
    limit = fields["limit"]
    assert (limit["minimum"], limit["maximum"], limit["default"]) == (1, 100, 20)
    least = fields["min_transactions"]
    assert least["anyOf"] == [
        {"type": "integer", "minimum": 0, "maximum": 10_000_000},
        {"type": "null"},
    ]
    assert least["default"] is None
    assert least["description"].startswith(
        f"Brak = próg domyślny: {PRICE_ORDER_MIN_TRANSACTIONS} przy sortowaniu po cenie, 0 przy "
        "transactions_desc. 0 = wszystkie miejsca."
    )
    for name, field in fields.items():
        assert field["description"] and field["title"] != name.replace("_", " ").title()


def test_cities_by_transactions_with_the_link_of_the_ranking(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    cities, powiats = ranking_routes(service)

    result = data(call(server, TOOL))

    assert result == {
        "level": "city",
        "sort": "transactions_desc",
        "min_transactions": 0,
        "total": 3,
        "returned": 3,
        "truncated": False,
        "ranking_url": RANKING_PAGE,
        "items": [
            WARSZAWA,
            {
                "name": "Kraków",
                "city_slug": "krakow",
                "transaction_count": 1492,
                "price_per_m2": 14606,
                "area_m2": 47.4,
                "price": 675000,
            },
            {
                "name": "Wrocław",
                "city_slug": "wroclaw",
                "transaction_count": 1443,
                "price_per_m2": 12437,
                "area_m2": 50.3,
                "price": 617000,
            },
        ],
    }
    assert (cities.call_count, powiats.call_count) == (1, 0)


def test_powiats_carry_their_id_and_no_link(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """By price the default threshold (20) applies, but it leaves none of the sample's
    powiats out, so the hint says nothing of it."""
    cities, powiats = ranking_routes(service)

    result = data(call(server, TOOL, level="powiat", sort="price_per_m2_desc", limit=1))

    assert result == {
        "level": "powiat",
        "sort": "price_per_m2_desc",
        "min_transactions": 20,
        "total": 3,
        "returned": 1,
        "truncated": True,
        "hint": "Pokazano pierwsze 1 z 3 powiatów; kolejne pokaże większy limit (najwyżej 100).",
        "items": [POWIAT_WARSZAWA],
    }
    assert (cities.call_count, powiats.call_count) == (0, 1)


def test_min_transactions_and_the_cheapest_first(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    ranking_routes(service)

    result = data(call(server, TOOL, sort="price_per_m2_asc", min_transactions=1450))

    assert [item["name"] for item in result["items"]] == ["Kraków", "Warszawa"]
    assert (result["total"], result["returned"], result["truncated"]) == (2, 2, False)


def test_by_price_places_under_20_transactions_are_left_out_unless_asked(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """The complete answer of 2026-10-15: by default the cheapest place has 37
    transactions; every place (min_transactions=0) starts with one of a single transaction
    at a tenth of that price. One request: the second call comes from the cache."""
    cities, _ = captured_ranking_routes(service)

    async def both(client: Client) -> list[CallToolResult]:
        return [
            await client.call_tool(TOOL, {"sort": "price_per_m2_asc"}),
            await client.call_tool(TOOL, {"sort": "price_per_m2_asc", "min_transactions": 0}),
        ]

    by_default, every = (data(result) for result in with_client(server, both))

    assert (by_default["min_transactions"], by_default["total"]) == (20, 258)
    assert (by_default["returned"], by_default["truncated"]) == (20, True)
    assert by_default["hint"] == (
        f"{LEFT_OUT} Pokazano pierwsze 20 z 258 miejscowości; kolejne pokaże większy limit "
        "(najwyżej 100)."
    )
    assert by_default["items"][0] == {
        "name": "Kamienna Góra",
        "city_slug": "kamienna-gora",
        "transaction_count": 37,
        "price_per_m2": 3394,
        "area_m2": 46.6,
        "price": 150000,
    }
    assert all(item["transaction_count"] >= 20 for item in by_default["items"])
    assert (every["min_transactions"], every["total"]) == (0, 2529)
    assert every["items"][0]["name"] == "Miejsce Piastowe"
    assert every["items"][0]["transaction_count"] == 1
    assert LEFT_OUT not in every["hint"]
    assert cities.call_count == 1


def test_a_place_of_zeros_shows_no_price_area_or_price(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """The one row of the complete answer of 2026-10-15 with 0 for all three (a real row,
    served alone): D11 leaves out what has no value."""
    rows = [row for row in captured(CITIES_2026_10_15) if row["city"] == "Ignatki-osiedle"]
    ranking_routes(service, cities=rows)

    result = data(call(server, TOOL, sort="price_per_m2_asc", min_transactions=0))

    assert result["items"] == [
        {"name": "Ignatki-osiedle", "city_slug": "ignatki-osiedle", "transaction_count": 8}
    ]


def test_nothing_left_says_what_to_change(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    ranking_routes(service)

    result = data(call(server, TOOL, min_transactions=1_000_000))

    assert (result["total"], result["returned"], result["items"]) == (0, 0, [])
    assert result["hint"] == (
        "Żadne miejsce nie ma co najmniej 1000000 transakcji: zmniejsz min_transactions."
    )


@pytest.mark.parametrize(
    ("arguments", "level", "sort", "limit", "least"),
    [
        (
            {"level": None, "sort": None, "limit": None, "min_transactions": None},
            "city",
            "transactions_desc",
            20,
            0,
        ),
        ({"level": "", "sort": ""}, "city", "transactions_desc", 20, 0),
        ({"level": " powiat ", "sort": " price_per_m2_asc"}, "powiat", "price_per_m2_asc", 20, 20),
        ({"limit": "2", "min_transactions": " 5 "}, "city", "transactions_desc", 2, 5),
        (
            {"sort": "price_per_m2_desc", "min_transactions": None},
            "city",
            "price_per_m2_desc",
            20,
            20,
        ),
        (
            {"sort": "price_per_m2_desc", "min_transactions": ""},
            "city",
            "price_per_m2_desc",
            20,
            20,
        ),
        ({"sort": "price_per_m2_asc", "min_transactions": "0"}, "city", "price_per_m2_asc", 20, 0),
        ({"sort": "price_per_m2_asc", "min_transactions": 0}, "city", "price_per_m2_asc", 20, 0),
    ],
)
def test_arguments_as_models_send_them(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    arguments: dict[str, Any],
    level: str,
    sort: str,
    limit: int,
    least: int,
) -> None:
    ranking_routes(service)

    result = data(call(server, TOOL, **arguments))

    assert (result["level"], result["sort"], result["min_transactions"]) == (level, sort, least)
    assert result["returned"] == min(limit, result["total"])


@pytest.mark.parametrize(
    ("arguments", "field"),
    [
        ({"level": "gmina"}, "level"),
        ({"level": "miasto"}, "level"),
        ({"sort": "price_desc"}, "sort"),
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"limit": True}, "limit"),
        ({"limit": "5.0"}, "limit"),
        ({"min_transactions": -1}, "min_transactions"),
        ({"min_transactions": "dużo"}, "min_transactions"),
        ({"min_transactions": True}, "min_transactions"),
        ({"min_transactions": "5.0"}, "min_transactions"),
    ],
)
def test_arguments_off_the_schema_are_refused_before_a_request(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    arguments: dict[str, Any],
    field: str,
) -> None:
    ranking_routes(service)

    result = call(server, TOOL, **arguments)

    assert result.is_error is True
    assert field in text(result)
    assert service.calls.call_count == 0


def test_a_failure_of_the_service_says_which_ranking_and_nothing_of_the_answer(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    service.get(CITY_RANKING).respond(500, text=INJECTED)
    service.get(POWIAT_RANKING).respond(200, json={INJECTED: True})

    async def both(client: Client) -> list[CallToolResult]:
        return [
            await client.call_tool(TOOL, {}),
            await client.call_tool(TOOL, {"level": "powiat"}),
        ]

    cities, powiats = with_client(server, both)

    assert cities.is_error is True and text(cities).startswith("Ranking miejscowości: ")
    assert powiats.is_error is True and text(powiats).startswith("Ranking powiatów: ")
    assert text(powiats).endswith(SERVICE_CHANGED)
    for result in (cities, powiats):
        assert not LEAKS.search(text(result)), text(result)


def test_a_stop_ends_the_series(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    service.get(CITY_RANKING).respond(403)
    powiats = service.get(POWIAT_RANKING).respond(200, json=[])

    async def two(client: Client) -> list[CallToolResult]:
        return [
            await client.call_tool(TOOL, {}),
            await client.call_tool(TOOL, {"level": "powiat"}),
        ]

    first, second = with_client(server, two)

    assert first.is_error is True and text(first).startswith("STOP: ")
    assert second.is_error is True and "STOP" in text(second)
    assert powiats.call_count == 0


def test_result_sizes_on_every_place_of_the_service(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """As many places as the samples report (2448 cities, 369 powiats): the default (20)
    fits the budget, the most (100) what the description of limit promises (about 12k)."""
    ranking_routes(
        service,
        cities=ranking_with_places("api.city_tx_stats", 2448),
        powiats=ranking_with_places("api.powiat_stats", 369),
    )

    async def sizes(client: Client) -> dict[tuple[str, int], int]:
        measured: dict[tuple[str, int], int] = {}
        for level in ("city", "powiat"):
            for limit in (20, 100):
                result = await client.call_tool(TOOL, {"level": level, "limit": limit})
                measured[(level, limit)] = len(text(result))
        return measured

    measured = with_client(server, sizes)

    assert max(measured[("city", 20)], measured[("powiat", 20)]) <= 3_500 <= SIZE_BUDGET
    # The copies' names ("Warszawa (kopia 2447)", "warszawa-kopia-2447") are about 20
    # characters longer than real ones; a real item is 118-124 (goldens rank_cities,
    # rank_powiats), as "ok. 120 znaków" in the description of limit says.
    assert max(measured[("city", 100)], measured[("powiat", 100)]) <= 100 * 145


def test_a_truncated_ranking_says_how_to_see_more(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    ranking_routes(service, cities=ranking_with_places("api.city_tx_stats", 2448))

    result = data(call(server, TOOL, limit=100))

    assert (result["total"], result["returned"], result["truncated"]) == (2448, 100, True)
    assert result["hint"] == (
        "Pokazano pierwsze 100 z 2448 miejscowości; to najwięcej w jednym wywołaniu. Pomiń "
        "małe miejsca przez min_transactions albo zmień sort."
    )
    counts = [item["transaction_count"] for item in result["items"]]
    assert counts == sorted(counts, reverse=True)


def test_results_have_no_backend_names(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    ranking_routes(service)

    async def both(client: Client) -> list[CallToolResult]:
        return [
            await client.call_tool(TOOL, {}),
            await client.call_tool(TOOL, {"level": "powiat"}),
        ]

    for result in with_client(server, both):
        assert not [key for key in keys(data(result)) if KEY_NAMES.search(key)]
