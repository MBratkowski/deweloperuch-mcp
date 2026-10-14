"""``GetMarketStatisticsTool``: the offer market of one city in numbers (D15)."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.get_market_statistics_mcp_presenter import (
    GetMarketStatisticsMcpPresenter,
    MarketStatisticsResult,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import Area, OptionalWholeNumber, Price, whole_or
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.models.market_statistics import DEFAULT_TOP_DEVELOPERS
from deweloperuch_mcp.models.values import TOP_DEVELOPERS_MAX
from deweloperuch_mcp.usecases.get_market_statistics import GetMarketStatisticsRequest

TopDevelopers = Annotated[int, Field(ge=1, le=TOP_DEVELOPERS_MAX)]


class GetMarketStatisticsTool(ToolBase):
    # D15: every active offer of the city in one request, summed up in the domain; no single
    # offer leaves the process. [P 2026-10-10] active offers only, `polska` refused by the
    # service (refused here before any request). [W] the counts may differ a little from the
    # offers list's total (Kraków 2026-10-13: 7325 here, 7307 on the list a minute apart).
    name = "get_market_statistics"
    title = "Statystyki rynku miasta"
    description = """\
Zwraca statystyki rynku ofert deweloperskich w jednym mieście: liczbę ofert, inwestycji \
i deweloperów, rozkład cen (PLN), cen za m² (PLN/m²) i metraży (m²) jako min, p25, \
median, p75 i max oraz największych deweloperów wg liczby ofert (developer_slug, \
offers, investments, median_price_per_m2, developer_url; developer_slug to \
identyfikator, a nazwę dewelopera daje get_developer). Opcjonalnie tylko oferty z \
zakresu ceny i metrażu. Użyj, gdy pytanie dotyczy rynku miasta (typowe ceny, kto ma \
najwięcej ofert), a nie konkretnych mieszkań (search_offers).

Ograniczenia: tylko aktywne oferty (bez archiwalnych) i tylko jedno miasto (city_slug z \
search_locations; polska nie działa). Liczby mogą się nieco różnić od total w \
search_offers. Pojedynczych ofert tu nie ma: list_url to lista tych ofert na \
deweloperuch.pl z tymi samymi filtrami, a developer_url profil dewelopera: podawaj je \
użytkownikowi jako linki."""

    async def __call__(
        self,
        city: Annotated[
            str,
            Field(
                title="Miasto",
                description="city_slug jednego miasta z search_locations, np. krakow (nie polska).",
            ),
        ],
        ctx: SessionContext,
        price_min: Annotated[
            Price | None,
            OptionalWholeNumber,
            Field(title="Cena od", description="Najniższa cena oferty w PLN."),
        ] = None,
        price_max: Annotated[
            Price | None,
            OptionalWholeNumber,
            Field(title="Cena do", description="Najwyższa cena oferty w PLN."),
        ] = None,
        area_min: Annotated[
            Area | None,
            OptionalWholeNumber,
            Field(title="Metraż od", description="Najmniejszy metraż w m²."),
        ] = None,
        area_max: Annotated[
            Area | None,
            OptionalWholeNumber,
            Field(title="Metraż do", description="Największy metraż w m²."),
        ] = None,
        top_developers: Annotated[
            TopDevelopers,
            whole_or(DEFAULT_TOP_DEVELOPERS),
            Field(
                title="Liczba deweloperów",
                description="Ilu największych deweloperów pokazać, 1–30, domyślnie 10.",
            ),
        ] = DEFAULT_TOP_DEVELOPERS,
    ) -> Annotated[CallToolResult, MarketStatisticsResult]:
        session = session_of(ctx)

        def get() -> MarketStatisticsResult:
            request = GetMarketStatisticsRequest.parse(
                city=city,
                price_min=price_min,
                price_max=price_max,
                area_min=area_min,
                area_max=area_max,
                top_developers=top_developers,
            )
            return GetMarketStatisticsMcpPresenter().present(
                session.get_market_statistics.execute(request)
            )

        return await run(get)
