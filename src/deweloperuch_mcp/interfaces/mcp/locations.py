"""Tool ``search_locations``: cities, districts and streets by a part of their name."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.application import arguments
from deweloperuch_mcp.interfaces import views
from deweloperuch_mcp.interfaces.mcp import presenters
from deweloperuch_mcp.interfaces.mcp.calls import SessionContext, run, session_of
from deweloperuch_mcp.interfaces.mcp.presenters import LocationsResult

# [W] docs/discovery/endpoints.md, location-search: `count` (offer_count of districts and
# streets) is the number of offers, hence "wg serwisu"; truncated is a heuristic for the
# suggestions (the location directory of the infrastructure), hence "może być więcej".
SEARCH_LOCATIONS = """\
Znajduje miasta, dzielnice i ulice w Polsce po fragmencie nazwy. Użyj na początku, \
żeby zamienić nazwę miejsca na city_slug, którego wymaga search_offers. Nie zwraca \
ofert ani cen.

Zwraca items (kind: city, district albo street; name, city, city_slug, opcjonalnie \
district, street, lat, lng i offer_count, czyli liczbę ofert wg serwisu) oraz total, \
returned, truncated i hint. total jest null, gdy wyników jest więcej niż pokazano; \
truncated=true znaczy, że pasujących może być więcej: doprecyzuj nazwę. Miejscowości z \
offer_count=0 nie mają ofert: nie przekazuj ich do search_offers. Dzielnica i ulica \
podają city_slug swojego miasta; search_offers filtruje tylko po mieście."""


async def search_locations(
    query: Annotated[
        str,
        Field(
            title="Szukany tekst",
            description=(
                "Fragment nazwy miasta, dzielnicy lub ulicy, 2–100 znaków, z polskimi "
                "znakami, np. Kraków, Mokotów."
            ),
        ),
    ],
    ctx: SessionContext,
) -> Annotated[CallToolResult, LocationsResult]:
    session = session_of(ctx)
    return await run(
        lambda: presenters.locations(
            views.location_search(session.search_locations(arguments.location_query(query)))
        )
    )
