"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.get_government_statistics_tool``."""

from typing import Any

import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.models.government_statistics import Dataset
from support.checks.leaks import LEAKS, SIZE_BUDGET
from support.providers.mcp import call, data, has_null, text, tools, with_client
from support.providers.routes.government_statistics import (
    UNKNOWN_LOCATION,
    stats_routes,
    stats_url,
    unknown_location_route,
)

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_government_statistics_input_schema(server: MCPServer[bootstrap.Session]) -> None:
    schema = tools(server)["get_government_statistics"]["inputSchema"]
    fields = schema["properties"]

    assert schema["required"] == ["location", "dataset"]
    assert fields["location"]["type"] == "string"
    assert "jastrzebie" in fields["location"]["description"]
    assert fields["location"]["description"].endswith(
        "Dane są tylko dla 66 miast na prawach powiatu, a nie dla dzielnic i mniejszych "
        "miejscowości."
    )
    assert "Częstotliwość zwraca pole frequency." in fields["dataset"]["description"]
    assert "ok. 10 tys. znaków" in fields["periods"]["description"]
    assert fields["dataset"]["enum"] == [dataset.value for dataset in Dataset]
    for dataset in Dataset:  # each value explained in Polish
        assert f"{dataset.value}:" in fields["dataset"]["description"]
    periods = fields["periods"]
    assert (periods["default"], periods["minimum"], periods["maximum"]) == (12, 1, 120)
    assert periods["type"] == "integer"


def test_government_statistics_as_a_table(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    stats_routes(service)

    result = data(
        call(
            server,
            "get_government_statistics",
            location="warszawa",
            dataset="nbp_prices",
            periods=2,
        )
    )

    assert result == {
        "location_slug": "warszawa",
        "location_name": "Warszawa",
        "dataset": "nbp_prices",
        "title": "Średnie ceny mieszkań za m² według NBP",
        "source": "NBP",
        "frequency": "quarter",
        "total": 80,
        "returned": 2,
        "truncated": True,
        "available_from": "2006-Q3",
        "hint": (
            "Pokazano ostatnie 2 z 80 okresów (dane od 2006-Q3); starsze pokaże większe "
            "periods (najwyżej 120)."
        ),
        "stats_url": stats_url("warszawa", "#nbp"),
        "periods": ["2026-Q1", "2026-Q2"],
        "series": [
            {
                "series_id": "primary_asking",
                "label": "Rynek pierwotny: cena ofertowa",
                "unit": "PLN/m²",
                "values": [18056, 18488],
            },
            {
                "series_id": "primary_transaction",
                "label": "Rynek pierwotny: cena transakcyjna",
                "unit": "PLN/m²",
                "values": [16471, 16783],
            },
            {
                "series_id": "secondary_asking",
                "label": "Rynek wtórny: cena ofertowa",
                "unit": "PLN/m²",
                "values": [18914, 19059],
            },
            {
                "series_id": "secondary_transaction",
                "label": "Rynek wtórny: cena transakcyjna",
                "unit": "PLN/m²",
                "values": [16523, 16723],
            },
        ],
    }


def test_government_statistics_with_the_defaults(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    stats_routes(service)

    result = data(
        call(server, "get_government_statistics", location="polska", dataset="average_area")
    )

    assert (result["total"], result["returned"], result["truncated"]) == (22, 12, True)
    assert result["periods"] == [str(year) for year in range(2015, 2027)]
    assert result["series"][0]["values"][-1] == 62.5
    assert result["stats_url"] == stats_url("polska", "#gus-srednia-powierzchnia")
    assert "note" not in result  # no null fields
    assert not has_null(result)


def test_government_statistics_keep_null_values_in_place(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """A period without data stays in the list as null, so values match periods."""
    stats_routes(service)

    result = data(
        call(
            server,
            "get_government_statistics",
            location="polska",
            dataset="dwellings_quarterly",
            periods=120,
        )
    )

    assert result["returned"] == result["total"] == 87
    rent = next(s for s in result["series"] if s["series_id"] == "started_for_rent")
    assert len(rent["values"]) == len(result["periods"])
    assert rent["values"][0] is None and rent["values"][-1] == 22
    assert result["note"].startswith("Ostatni kwartał (2026-Q3) obejmuje tylko 2 z 3")


@pytest.mark.parametrize(
    ("arguments", "returned"),
    [
        ({"periods": "3"}, 3),
        ({"periods": " 5 "}, 5),
        ({"periods": None}, 12),
        ({"dataset": " wages "}, 12),
        ({"location": " polska "}, 12),
    ],
)
def test_government_statistics_arguments_as_models_send_them(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    arguments: dict[str, Any],
    returned: int,
) -> None:
    stats_routes(service)

    result = data(
        call(
            server,
            "get_government_statistics",
            **{"location": "polska", "dataset": "wages", **arguments},
        )
    )

    assert result["returned"] == returned


@pytest.mark.parametrize(
    ("arguments", "field"),
    [
        ({"periods": 0}, "periods"),
        ({"periods": 121}, "periods"),
        ({"periods": True}, "periods"),
        ({"periods": "3.0"}, "periods"),
        ({"dataset": "prices"}, "dataset"),
        ({"dataset": None}, "dataset"),
        ({"location": None}, "location"),
    ],
)
def test_government_statistics_arguments_off_the_schema_are_refused(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    arguments: dict[str, Any],
    field: str,
) -> None:
    result = call(
        server,
        "get_government_statistics",
        **{"location": "polska", "dataset": "wages", **arguments},
    )

    assert result.is_error is True
    assert field in text(result) and "pydantic.dev" not in text(result)
    assert service.calls.call_count == 0


@pytest.mark.parametrize("location", ["Kraków", "kraków", "", "a/b", "KRAKÓW"])
def test_government_statistics_location_that_is_not_a_slug_says_what_to_give(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter, location: str
) -> None:
    result = call(server, "get_government_statistics", location=location, dataset="wages")

    assert result.is_error is True
    assert text(result).startswith("location: oczekiwano polska, agregat (7-miast")
    assert service.calls.call_count == 0


def test_government_statistics_nbp_prices_of_poland_point_to_cities(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    stats_routes(service)

    result = call(server, "get_government_statistics", location="polska", dataset="nbp_prices")

    assert result.is_error is True
    assert text(result).startswith("NBP nie podaje jednej ceny dla całej Polski")
    assert "warszawa, krakow" in text(result) and "sopot" not in text(result)
    assert not LEAKS.search(text(result))


def test_government_statistics_of_an_unknown_location(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    unknown_location_route(service)

    result = call(server, "get_government_statistics", location=UNKNOWN_LOCATION, dataset="wages")

    assert result.is_error is True
    assert text(result) == (
        f"Serwis nie ma statystyk rządowych dla lokalizacji {UNKNOWN_LOCATION!r}. Podaj "
        "polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo slug miasta na "
        "prawach powiatu bez polskich znaków, np. warszawa, krakow. Jeśli nie znasz sluga "
        "miasta, spróbuj city_slug z search_locations (zwykle jest taki sam, ale nie "
        "zawsze, np. dla Jastrzębia-Zdroju użyj jastrzebie). Statystyki są tylko dla miast "
        "na prawach powiatu."
    )
    assert not LEAKS.search(text(result))


@pytest.mark.parametrize("location", ["Warszawa", " WARSZAWA ", "WarSzawa"])
def test_government_statistics_location_in_capitals_is_the_slug(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter, location: str
) -> None:
    """Models write names with capitals: lowercased, without touching Polish letters."""
    routes = stats_routes(service)

    result = data(call(server, "get_government_statistics", location=location, dataset="wages"))

    assert (result["location_slug"], routes["warszawa"].call_count) == ("warszawa", 1)
    assert result["stats_url"] == stats_url("warszawa", "#gus-wynagrodzenia")


@pytest.mark.parametrize(
    ("location", "dataset", "periods", "hint"),
    [
        (
            "polska",
            "dwellings_monthly",
            120,
            "Pokazano ostatnie 120 z 260 okresów (dane od 2005-01). To maksimum w jednym "
            "wywołaniu; starszych okresów tym narzędziem nie pobierzesz.",
        ),
        (
            "polska",
            "unemployment",
            119,
            "Pokazano ostatnie 119 z 188 okresów (dane od 2011-01); starsze pokaże większe "
            "periods (najwyżej 120).",
        ),
        ("polska", "dwellings_quarterly", 120, None),  # 87 periods: nothing older
    ],
)
def test_government_statistics_hint_at_the_cap_of_periods(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    location: str,
    dataset: str,
    periods: int,
    hint: str | None,
) -> None:
    """At the cap of 120 a larger periods is no way to older data: the hint says so
    instead of asking for it (the CLI, without that cap, keeps the domain's hint)."""
    stats_routes(service)

    result = data(
        call(
            server,
            "get_government_statistics",
            location=location,
            dataset=dataset,
            periods=periods,
        )
    )

    assert result.get("hint") == hint
    assert result["truncated"] is (hint is not None)


def test_government_statistics_results_fit_the_size_budget(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """Every dataset of both pages: the default (12 periods) < 8000 characters; the most
    (120) within what the description of periods promises (about 11k)."""
    stats_routes(service)

    async def sizes(client: Client) -> dict[tuple[str, str, int], int]:
        measured: dict[tuple[str, str, int], int] = {}
        for location in ("polska", "warszawa"):
            for dataset in Dataset:
                if location == "polska" and dataset is Dataset.NBP_PRICES:
                    continue
                for periods in (12, 120):
                    result = await client.call_tool(
                        "get_government_statistics",
                        {"location": location, "dataset": dataset.value, "periods": periods},
                    )
                    measured[(location, dataset.value, periods)] = len(text(result))
        return measured

    measured = with_client(server, sizes)

    assert max(size for key, size in measured.items() if key[2] == 12) < SIZE_BUDGET
    assert max(size for key, size in measured.items() if key[2] == 12) < 3_500
    assert max(measured.values()) <= 11_000
    assert max(measured, key=lambda key: measured[key]) == ("polska", "dwellings_monthly", 120)
