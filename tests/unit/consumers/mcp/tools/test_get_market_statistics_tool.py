"""Tests of ``deweloperuch_mcp.consumers.mcp.tools.get_market_statistics_tool``."""

import pytest
import respx
from mcp.server.mcpserver import MCPServer

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.usecases.get_market_statistics import ONE_CITY
from support.checks.leaks import SIZE_BUDGET
from support.providers.error_answers import (
    CHANGED_SERVICE,
    UNKNOWN_CITY_ERROR,
    removed_route,
    unknown_entity,
)
from support.providers.mcp import call, calls, data, keys, text
from support.providers.routes.city_lookup import UNKNOWN_PLACE_MESSAGE, VILLAGE, failed_lookup_route
from support.providers.routes.offer_snapshot import OFFER_SNAPSHOT_PATH, offer_snapshot_routes
from support.providers.rsc import UNKNOWN_CITY
from support.providers.service import PAGES

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_get_market_statistics_of_a_city(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    routes = offer_snapshot_routes(service)

    result = data(call(server, "get_market_statistics", city="sopot", top_developers=1))

    assert result == {
        "city_slug": "sopot",
        "as_of": "2026-10-31",
        "offers": 8,
        "investments": 2,
        "developers": 1,
        # statistics.quantiles(..., method="inclusive") of the 8 offers, rounded
        "price": {
            "min": 1261250,
            "p25": 1534860,
            "median": 1616858,
            "p75": 1661530,
            "max": 3735107,
        },
        "price_per_m2": {
            "min": 24289,
            "p25": 25224,
            "median": 25808,
            "p75": 26383,
            "max": 39115,
        },
        "area_m2": {"min": 48.73, "p25": 58.11, "median": 64.69, "p75": 66.02, "max": 95.49},
        "top_developers": [
            {
                "developer_slug": "invest-komfort-spolka-akcyjna",
                "developer_name": "Invest Komfort Spółka Akcyjna Sp.K.",
                "offers": 8,
                "investments": 2,
                "median_price_per_m2": 25808,
                "developer_url": f"{PAGES}/sopot/deweloperzy/invest-komfort-spolka-akcyjna",
            }
        ],
        "developers_returned": 1,
        "developers_omitted": 0,
        "truncated": False,
        "list_url": f"{PAGES}/sopot/mieszkania?perPage=10",
    }
    assert routes["sopot"].call_count == 1


def test_get_market_statistics_of_wroclaw_agrees_with_the_services_summary(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """[P 2026-10-30, PR #16] Wrocław's snapshot, captured with the package's client in
    PR #16. By its description, the service's own summary on ``/statystyki/wroclaw/oferty``
    agreed that day: 5,836 offers, 110 investments, 46 developers, a median of
    14,600 PLN/m² and Develia first with 818 offers; at 45-55 m², ``offers search``
    listed 956 offers, as many as this summary counts."""
    routes = offer_snapshot_routes(service)

    whole, sized = (
        data(result)
        for result in calls(
            server,
            "get_market_statistics",
            {"city": "wroclaw", "top_developers": 1},
            {"city": "wroclaw", "area_min": 45, "area_max": 55},
        )
    )

    assert (whole["as_of"], whole["offers"], whole["investments"], whole["developers"]) == (
        "2026-10-30",
        5836,
        110,
        46,
    )
    assert whole["price_per_m2"]["median"] == 14600
    assert [(top["developer_slug"], top["offers"]) for top in whole["top_developers"]] == [
        ("develia", 818)
    ]
    assert (sized["offers"], sized["investments"], sized["developers"]) == (956, 75, 36)
    # One client: the second summary comes from the snapshot the first one cached.
    assert routes["wroclaw"].call_count == 1


def test_the_market_never_shows_single_offers_and_fits_its_budget(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """D5, D20: 11,672 offers of Warszawa, only aggregates and 30 developers at most."""
    offer_snapshot_routes(service)

    result = call(
        server, "get_market_statistics", city="warszawa", price_max=900_000, top_developers=30
    )

    found = data(result)
    assert found["offers"] < 11_672 and found["developers_returned"] == 30
    assert found["list_url"].endswith("/warszawa/mieszkania?filterPrice=0-900000&perPage=10")
    assert not {"offer_id", "items", "offers_list", "sales"} & keys(found)
    assert len(text(result)) < SIZE_BUDGET


@pytest.mark.parametrize(
    ("city", "message", "sent"),
    [
        (
            "polska",
            "city: statystyki rynku są tylko dla jednego miasta; podaj city_slug miasta z "
            "search_locations (np. warszawa), a nie polska; podano 'polska'.",
            0,
        ),
        (
            "Kraków",
            "city: oczekiwano slug jednego miasta z search_locations: małe litery, bez "
            "polskich znaków (np. warszawa, sopot; nie polska); podano 'Kraków'.",
            0,
        ),
        pytest.param(UNKNOWN_CITY, f"{UNKNOWN_PLACE_MESSAGE} {ONE_CITY}", 2, id="unknown-place"),
        pytest.param(
            VILLAGE,
            "Miejscowość 'Ignatki-osiedle' istnieje, ale serwis nie ma dla niej statystyk "
            "rynku. Nie ponawiaj; powiedz to użytkownikowi.",
            2,
            id="known-place",
        ),
        pytest.param(
            "atlantyda",
            "Serwis nie zna miasta 'atlantyda' albo nie ma w nim ofert. Podaj city_slug z "
            "search_locations (miejscowości z offer_count=0 nie mają statystyk; statystyki "
            "rynku są tylko dla jednego miasta).",
            2,
            id="lookup-failed",
        ),
    ],
)
def test_the_market_of_the_whole_country_or_an_unknown_city(
    server: MCPServer[bootstrap.Session],
    service: respx.MockRouter,
    city: str,
    message: str,
    sent: int,
) -> None:
    offer_snapshot_routes(service)
    failed_lookup_route(service, "atlantyda")
    for unknown in (VILLAGE, "atlantyda"):  # answered as UNKNOWN_CITY's [P 2026-10-31]
        service.get(path=OFFER_SNAPSHOT_PATH + unknown).respond(
            404, **unknown_entity(UNKNOWN_CITY_ERROR)
        )

    result = call(server, "get_market_statistics", city=city)

    assert result.is_error is True and text(result) == message
    assert service.calls.call_count == sent


def test_a_removed_snapshot_is_a_changed_service_not_an_unknown_city(
    server: MCPServer[bootstrap.Session], service: respx.MockRouter
) -> None:
    """D21: the HTML 404 of a route that is gone tells the model to report it, not to look
    for another city."""
    service.get(OFFER_SNAPSHOT_PATH + "sopot").respond(404, **removed_route())

    result = call(server, "get_market_statistics", city="sopot")

    assert result.is_error is True
    assert text(result) == f"Statystyki rynku w 'sopot': {CHANGED_SERVICE}"
