"""``SearchLocationsTool``: cities, districts and streets by a part of their name."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.search_locations_mcp_presenter import (
    LocationsResult,
    SearchLocationsMcpPresenter,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.usecases.search_locations import SearchLocationsRequest


class SearchLocationsTool(ToolBase):
    # [W] docs/discovery/endpoints.md, location-search: `count` (offer_count of districts and
    # streets) is the number of offers, hence "wg serwisu"; truncated is a heuristic for the
    # suggestions (``LocationsApi``), hence "może być więcej".
    name = "search_locations"
    title = "Szukaj lokalizacji"
    description = """\
Znajduje miasta, dzielnice i ulice w Polsce po fragmencie nazwy. Użyj na początku, \
żeby zamienić nazwę miejsca na city_slug, którego wymaga search_offers. Nie zwraca \
ofert ani cen.

Zwraca items (kind: city, district albo street; name, city, city_slug, opcjonalnie \
district, street, lat, lng i offer_count, czyli liczbę ofert wg serwisu) oraz total, \
returned, truncated i hint. total jest null, gdy wyników jest więcej niż pokazano; \
truncated=true znaczy, że pasujących może być więcej: doprecyzuj nazwę. Miejscowości z \
offer_count=0 nie mają ofert: nie przekazuj ich do search_offers. Dzielnica i ulica \
podają city_slug swojego miasta. Nazwę dzielnicy (kind=district, pole name) przekaż do \
search_offers jako district razem z tym city_slug; po ulicy search_offers nie filtruje."""

    async def __call__(
        self,
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

        def search() -> LocationsResult:
            request = SearchLocationsRequest.parse(query=query)
            return SearchLocationsMcpPresenter().present(session.search_locations.execute(request))

        return await run(search)
