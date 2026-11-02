"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.get_developer_tool``."""

import pytest
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.consumers.mcp.presenters.get_developer_mcp_presenter import DeveloperResult
from deweloperuch_mcp.consumers.mcp.tools.get_developer_tool import GetDeveloperTool
from deweloperuch_mcp.usecases.get_developer import CHECK_THE_DEVELOPER
from support.providers.error_answers import removed_route
from support.providers.mcp import call, data, text, with_client
from support.providers.routes.city_lookup import (
    UNKNOWN_PLACE_MESSAGE,
    city_lookup_routes,
    failed_lookup_route,
)
from support.providers.routes.developer_profiles import (
    DEVELOPERS_PATH,
    developer_routes,
    known_place_without_offers_route,
    with_cities_reversed,
    without_cities_chart,
)
from support.providers.routes.offers import RSC_HEADERS
from support.providers.rsc import (
    DEVELOPER_DOM_DEVELOPMENT_WARSZAWA_20261031,
    DEVELOPER_POLSKA_20261031,
    DEVELOPER_WARSZAWA_20261031,
    UNKNOWN_CITY,
    raw,
)
from support.providers.service import PAGES

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


DEVELOPER_BUDGET = 12_000
"""Characters of ``get_developer`` with the default limit for the whole country."""

BY_ACTIVE_OFFERS = [
    "krakow",
    "poznan",
    "lodz",
    "szczecin",
    "katowice",
    "gdansk",
    "wroclaw",
    "piastow",
    "gliwice",
    "gdynia",
    "warszawa",
    "kowale",
    "swarzedz",
    "reda",
]
"""ATAL's 14 cities by their active offers on 2026-10-31 (705, 704, 674 … 31, 18)."""

NOT_FOUND_IN_WARSAW = (
    "Nie znaleziono dewelopera 'nieistniejacy-deweloper' w 'warszawa'. Slug dewelopera "
    "podaje search_developers (po nazwie) albo pole developer_slug w search_offers, "
    "get_investment i get_offer; city to city_slug z search_locations albo polska (cała "
    "Polska). Albo deweloper nie ma w tym mieście aktywnych ofert: spróbuj city=polska."
)

CITIES_OF_INVESTMENTS_ONLY = (
    "Serwis nie podał listy miast dewelopera: cities to tylko miasta inwestycji w city "
    "(wszystkie: city=polska)."
)


def page_route(service: respx.MockRouter, city: str, developer: str, payload: bytes) -> None:
    path = DEVELOPERS_PATH.format(city=city, developer=developer)
    service.get(path=path).respond(200, content=payload, headers=RSC_HEADERS)


def test_get_developer_in_a_city(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    developer_routes(service)

    result = data(call(server, "get_developer", developer_slug="atal", city="warszawa"))

    # [P 2026-10-31] tests/fixtures/rsc/developer_atal_warszawa_20261031.rsc: no website on
    # the 2.0 page; the summary is computed from the 4 investments.
    assert result["developer"] == {"developer_slug": "atal", "name": "ATAL S.A."}
    assert result["developer_url"] == f"{PAGES}/warszawa/deweloperzy/atal"
    assert result["city_slug"] == "warszawa"
    assert result["summary"] == {
        "active_offers": 60,
        "cities": 1,
        "avg_price": 993384.0,
        "avg_area_m2": 62.3,
        "avg_price_per_m2": 16110.0,
    }
    assert (result["investments_total"], result["investments_returned"]) == (4, 4)
    assert (result["investments_omitted"], result["truncated"]) == (0, False)
    assert [i["investment_slug"] for i in result["investments"]] == [
        "warszawska-58a",
        "nowy-targowek-vi",
        "osiedle-poematu-ii",
        "zakatek-harmonia-ii",
    ]
    assert result["investments"][0] == {
        "investment_slug": "warszawska-58a",
        "name": "Warszawska 58A",
        "city": "Warszawa",
        "city_slug": "warszawa",
        "status": "active",
        "active_offers": 32,
        "total_offers": 73,
        "avg_price": 966208.84,
        "avg_area_m2": 59.93,
        "avg_price_per_m2": 16123.0,
        "investment_url": f"{PAGES}/warszawa/deweloperzy/atal/warszawska-58a",
    }
    # The most active offers first, whatever the service's order (by price per m²).
    assert [city["city_slug"] for city in result["cities"]] == BY_ACTIVE_OFFERS
    assert result["cities"][:2] == [
        {
            "city": "Kraków",
            "city_slug": "krakow",
            "investments": 7,
            "active_offers": 705,
            "avg_price_per_m2": 13757.0,
        },
        {
            "city": "Poznań",
            "city_slug": "poznan",
            "investments": 4,
            "active_offers": 704,
            "avg_price_per_m2": 11864.0,
        },
    ]
    assert "hint" not in result


def test_the_cities_come_by_active_offers_whatever_the_order_of_the_chart(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """The real page of Warsaw with the rows of its chart of cities reversed."""
    page_route(service, "warszawa", "atal", with_cities_reversed(raw(DEVELOPER_WARSZAWA_20261031)))

    result = data(call(server, "get_developer", developer_slug="atal", city="warszawa"))

    assert [city["city_slug"] for city in result["cities"]] == BY_ACTIVE_OFFERS


def test_a_city_page_without_the_chart_of_cities_says_its_cities_are_those_of_the_city(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """[W] a page without the chart is a developer in one city. Should the service drop the
    chart, ATAL's 14 cities become 1: the hint says the list may be incomplete."""
    page_route(service, "warszawa", "atal", without_cities_chart(raw(DEVELOPER_WARSZAWA_20261031)))

    result = data(call(server, "get_developer", developer_slug="atal", city="warszawa"))

    assert [city["city_slug"] for city in result["cities"]] == ["warszawa"]
    assert result["hint"] == CITIES_OF_INVESTMENTS_ONLY


def test_the_whole_country_without_the_chart_of_cities_has_every_city_and_no_hint(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """The investments of the whole country are in every city of the developer."""
    page_route(service, "polska", "atal", without_cities_chart(raw(DEVELOPER_POLSKA_20261031)))

    result = data(call(server, "get_developer", developer_slug="atal", limit=100))

    assert sorted(city["city_slug"] for city in result["cities"]) == sorted(BY_ACTIVE_OFFERS)
    assert "hint" not in result


def test_a_cut_city_page_without_the_chart_of_cities_gives_both_hints(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """Dom Development in Warsaw, 28 investments, with the chart renamed: 20 shown."""
    page = without_cities_chart(raw(DEVELOPER_DOM_DEVELOPMENT_WARSZAWA_20261031))
    page_route(service, "warszawa", "dom-development", page)

    result = data(call(server, "get_developer", developer_slug="dom-development", city="warszawa"))

    assert result["truncated"] is True
    assert result["hint"] == (
        f"{CITIES_OF_INVESTMENTS_ONLY} Pokazano 20 z 28 inwestycji (najwięcej aktywnych ofert); "
        "pozostałe pokaże większy limit (najwyżej 100)."
    )


def test_a_developer_in_one_city_has_the_city_of_its_investments(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """[P 2026-10-31] Ceres Development: its page has no chart of cities. The hint is true
    there too: the result cannot tell it from a developer in more cities."""
    developer_routes(service)

    result = data(
        call(server, "get_developer", developer_slug="ceres-development", city="warszawa")
    )

    assert result["developer"] == {
        "developer_slug": "ceres-development",
        "name": "Ceres Development Sp. z o.o.",
    }
    assert result["summary"] == {
        "active_offers": 110,
        "cities": 1,
        "avg_price": 662273.0,
        "avg_area_m2": 50.96,
        "avg_price_per_m2": 12996.0,
    }
    assert result["cities"] == [
        {
            "city": "Warszawa",
            "city_slug": "warszawa",
            "investments": 1,
            "active_offers": 110,
            "avg_price_per_m2": 12996.0,
        }
    ]
    assert result["hint"] == CITIES_OF_INVESTMENTS_ONLY


def test_get_developer_of_the_whole_country_is_cut_and_fits_its_budget(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    developer_routes(service)

    async def both(client: Client) -> list[CallToolResult]:
        return [
            await client.call_tool("get_developer", {"developer_slug": "atal"}),
            await client.call_tool("get_developer", {"developer_slug": "atal", "limit": 100}),
        ]

    default, everything = with_client(server, both)

    result = data(default)
    assert (result["city_slug"], result["investments_total"]) == ("polska", 42)
    assert (result["investments_returned"], result["investments_omitted"]) == (20, 22)
    assert result["truncated"] is True
    assert result["hint"] == (
        "Pokazano 20 z 42 inwestycji (najwięcej aktywnych ofert); pozostałe pokaże większy "
        "limit (najwyżej 100)."
    )
    active = [i["active_offers"] for i in result["investments"]]
    assert active == sorted(active, reverse=True) and active[0] == 338
    assert len(text(default)) < DEVELOPER_BUDGET
    assert data(everything)["investments_returned"] == 42
    assert len(text(everything)) < 42 * 400 + 3_000
    assert len(service.calls) == 1  # the second call came from the cache


def test_a_removed_profile_page_is_a_changed_service_not_an_unknown_developer(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """D21: the developer is named as the subject, and the text says in so many words that
    it does not mean the developer is gone (the whole text, as the model reads it)."""
    service.get(path="/ceny-ofertowe/warszawa/deweloperzy/atal").respond(404, **removed_route())

    result = call(server, "get_developer", developer_slug="atal", city="warszawa")

    assert result.is_error is True
    assert text(result) == (
        "Deweloper 'atal' w 'warszawa': Narzędzie nie może pobrać tych danych, bo serwis "
        "przeniósł je w inne miejsce albo przestał je udostępniać. To nie musi znaczyć, że "
        "argumenty są błędne ani że szukanego obiektu nie ma. Serwis mógł się zmienić po "
        "aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi."
    )


def test_an_unknown_developer_says_where_its_slug_comes_from(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    developer_routes(service)
    failed_lookup_route(service, "warszawa")  # a failed lookup: the first words stand

    result = call(
        server, "get_developer", developer_slug="nieistniejacy-deweloper", city="warszawa"
    )

    assert result.is_error is True
    assert text(result) == NOT_FOUND_IN_WARSAW


def test_a_developer_in_an_unknown_city_says_there_is_no_such_place(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """T39 [P 2026-11-02]: not "the service changed" (the page sends the reader on to the
    developer's page for the whole country), and the place lookup tells a wrong city slug
    from a place without the developer's offers."""
    routes = developer_routes(service)

    result = call(server, "get_developer", developer_slug="atal", city=UNKNOWN_CITY)

    assert result.is_error is True
    assert text(result) == f"{UNKNOWN_PLACE_MESSAGE} {CHECK_THE_DEVELOPER}"
    assert routes[(UNKNOWN_CITY, "atal")].call_count == 1


def test_a_developer_in_a_known_place_without_its_offers_names_the_place(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    known_place_without_offers_route(service)
    city_lookup_routes(service)

    result = call(server, "get_developer", developer_slug="atal", city="krakow")

    assert result.is_error is True
    assert text(result) == (
        "Miejscowość 'Kraków' istnieje, ale serwis nie ma dla niej aktywnych ofert tego "
        "dewelopera. Sprawdź developer_slug (search_developers) albo spróbuj city=polska "
        "(cała Polska)."
    )


def test_an_unknown_developer_in_the_whole_country(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """[P 2026-10-31] the page for Poland answers with Next.js's 404 marker too; without a
    city there is no city to have no offers in."""
    developer_routes(service)

    result = call(server, "get_developer", developer_slug="nieistniejacy-deweloper")

    assert result.is_error is True
    assert text(result) == NOT_FOUND_IN_WARSAW.replace(" w 'warszawa'", "").removesuffix(
        " Albo deweloper nie ma w tym mieście aktywnych ofert: spróbuj city=polska."
    )


def test_the_description_says_what_the_result_holds_and_where_slugs_come_from() -> None:
    description = GetDeveloperTool.description
    fields = DeveloperResult.model_json_schema()["$defs"]

    for said in (
        "Nie podaje strony www dewelopera.",
        "od miasta z największą liczbą aktywnych ofert",
        "summary liczy narzędzie z inwestycji w zakresie city",
        "summary.cities to liczba miast",
        "Średnia cena oferty w jednym mieście: city=<city_slug>, pole summary.avg_price.",
        "get_market_statistics (top_developers)",
        "(city_slug z search_locations albo z cities)",
        "o pominięciu mówią investments_omitted (ile), truncated i hint.",
        "developer_slug weź z search_developers (po nazwie)",
        "cities obejmuje całą Polskę (gdy serwis nie podaje listy miast, tylko miasta "
        "inwestycji: wtedy hint)",
    ):
        assert said in description, said
    assert "cities zawsze" not in description
    assert len(description) <= 1_200
    per_m2 = fields["DeveloperSummaryItem"]["properties"]["avg_price_per_m2"]["description"]
    assert "nie jest ilorazem avg_price / avg_area_m2" in per_m2
    city_per_m2 = fields["DeveloperCityItem"]["properties"]["avg_price_per_m2"]["description"]
    assert "wg serwisu albo liczona z inwestycji" in city_per_m2
    for item, name in (
        ("DeveloperInvestmentItem", "active_offers"),
        ("DeveloperInvestmentItem", "avg_area_m2"),
        ("DeveloperInvestmentItem", "avg_price_per_m2"),
        ("DeveloperCityItem", "active_offers"),
    ):
        assert fields[item]["properties"][name].get("description"), (item, name)
