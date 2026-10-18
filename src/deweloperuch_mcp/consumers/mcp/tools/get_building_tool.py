"""``GetBuildingTool``: a building of the price register with its units and their
transactions, and on request the price trend around it: at most ``limit`` units and the
newest ``TREND_QUARTERS`` quarters of the trend."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.get_building_mcp_presenter import (
    BuildingResult,
    GetBuildingMcpPresenter,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import null_is, whole_or
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.usecases.get_building import GetBuildingRequest

DEFAULT_BUILDING_LIMIT = 10
"""Units ``get_building`` returns unless asked otherwise: about 200 characters a
transaction, and a unit may have several (tests: 3 each stay within the budget)."""
MAX_BUILDING_LIMIT = 50
TREND_QUARTERS = 12
"""Quarters of the trend a result holds: the newest three years."""
Limit = Annotated[int, Field(ge=0, le=MAX_BUILDING_LIMIT)]

ORDER = (
    "Kolejność: lokale od tego z najnowszą transakcją, transakcje każdego lokalu od najstarszej."
)


class GetBuildingTool(ToolBase):
    name = "get_building"
    title = "Budynek z transakcjami"
    description = (
        "Zwraca budynek z rejestru cen transakcyjnych (RCN): adres, współrzędne, średnie ceny "
        "podane przez serwis i lokale z transakcjami: datą, ceną, ceną za m², rynkiem, "
        "rodzajem i stronami. To ceny, za które lokale sprzedano, nie ceny ofertowe "
        "deweloperów. building_slug to ostatni człon adresu strony budynku z cenami "
        "transakcyjnymi na deweloperuch.pl, np. 23-marca-79c-sopot; gdy go nie znasz, poproś "
        "użytkownika o link do tej strony. building_url to ta strona: podaj ją jako link. "
        f"{ORDER} Transakcji o classification innym niż regular (udział, egzekucja, "
        "bonifikata…) nie uśredniaj ze zwykłymi: to nie zwykła sprzedaż po cenie rynkowej; "
        "liczy je non_regular_transactions.\n"
        "\n"
        "Ograniczenia: tylko budynki z mieszkaniami, nie domy. Zwraca najwyżej limit lokali "
        f"(domyślnie {DEFAULT_BUILDING_LIMIT}); truncated i units_omitted mówią, czy i ile "
        "pominięto; units_total i transactions_total liczą cały budynek. Najnowsze miesiące "
        "bywają niepełne (rejestr spływa z opóźnieniem). include_trend=true dodaje średnią "
        "cenę za m² transakcji w okolicy budynku (promień radius_km) w ostatnich "
        f"{TREND_QUARTERS} kwartałach; to jedno zapytanie do serwisu więcej."
    )

    async def __call__(
        self,
        building_slug: Annotated[
            str,
            Field(
                title="Budynek",
                description=(
                    "Slug budynku, np. 23-marca-79c-sopot, ze strony budynku albo z comparables "
                    "w estimate_property_value."
                ),
            ),
        ],
        ctx: SessionContext,
        limit: Annotated[
            Limit,
            whole_or(DEFAULT_BUILDING_LIMIT),
            Field(
                title="Limit lokali",
                description=(
                    "Najwięcej lokali w wyniku (tych z najnowszymi transakcjami), domyślnie "
                    f"{DEFAULT_BUILDING_LIMIT}, najwyżej {MAX_BUILDING_LIMIT}; 0 = tylko "
                    "podsumowanie budynku. Ile pominięto, mówi units_omitted. Wynik ma ok. 200 "
                    "znaków na transakcję; lokal może mieć kilka transakcji, więc zwykle "
                    "wystarcza domyślny limit."
                ),
            ),
        ] = DEFAULT_BUILDING_LIMIT,
        include_trend: Annotated[
            bool,
            null_is(False),
            Field(
                title="Z trendem okolicy",
                description=(
                    "true: dołącz średnią cenę za m² transakcji w okolicy budynku w ostatnich "
                    f"{TREND_QUARTERS} kwartałach (jedno zapytanie więcej)."
                ),
            ),
        ] = False,
    ) -> Annotated[CallToolResult, BuildingResult]:
        session = session_of(ctx)

        def get() -> BuildingResult:
            request = GetBuildingRequest.parse(
                building_slug=building_slug,
                limit=limit,
                include_trend=include_trend,
                trend_quarters=TREND_QUARTERS,
            )
            return GetBuildingMcpPresenter().present(session.get_building.execute(request))

        return await run(get)
