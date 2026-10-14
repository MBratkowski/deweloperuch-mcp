"""``SearchInvestmentsTool``: the investments of a city, or by a part of their name."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.search_investments_mcp_presenter import (
    InvestmentsResult,
    SearchInvestmentsMcpPresenter,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import OptionalChoice, whole_or
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.consumers.shared.choices import InvestmentSortChoice
from deweloperuch_mcp.models.investment_summary import DEFAULT_INVESTMENTS_LIMIT
from deweloperuch_mcp.usecases.search_investments import SearchInvestmentsRequest

MAX_INVESTMENTS_LIMIT = 30
"""Investments one result may show in MCP: up to about 23k characters with the links
(Warsaw-like items with a district, a street and a long developer slug), within the
budget of a page of 50 offers (tests/unit/consumers/mcp/tools/test_search_investments_tool.py)."""
Limit = Annotated[int, Field(ge=1, le=MAX_INVESTMENTS_LIMIT)]


class SearchInvestmentsTool(ToolBase):
    name = "search_investments"
    title = "Szukaj inwestycji"
    description = """\
Wyszukuje inwestycje (projekty deweloperskie, rynek pierwotny). Dwa tryby: city (pełne \
dane) albo samo name (cała Polska; tylko investment_slug, name i offers_active, w \
kolejności serwisu). Użyj, gdy pytanie dotyczy projektów, a nie pojedynczych mieszkań: \
np. najtańsze za m² w mieście, inwestycje jednego dewelopera, slug inwestycji po nazwie.

Z city zwraca inwestycje, które serwis pokazuje na mapie miasta (z aktywnymi ofertami; \
bez nich mogą nie być na liście): investment_slug, name, city_slug, ulica, status, \
offers_active, offers_total, średnie (avg_price, avg_area_m2, avg_price_per_m2; tylko \
aktywne oferty, wg serwisu), developer_slug, developer_name, investment_url i \
developer_url. name i developer_slug zawężają listę, sort ją porządkuje (domyślnie \
najwięcej aktywnych ofert); pozycje bez średniej są na końcu. Oferty i szczegóły \
inwestycji daje get_investment (investment_slug). Linki podawaj użytkownikowi.

Ograniczenia: najwyżej limit pozycji; total, returned, truncated i hint mówią, ile \
pominięto i co zawęzić. Nie filtruje po cenie ani metrażu (do tego search_offers); \
city=polska nie działa."""

    async def __call__(
        self,
        ctx: SessionContext,
        city: Annotated[
            str | None,
            OptionalChoice,
            Field(
                title="Miasto",
                description=(
                    "city_slug miasta z search_locations, np. warszawa, sopot (nie polska)."
                ),
            ),
        ] = None,
        name: Annotated[
            str | None,
            OptionalChoice,
            Field(
                title="Nazwa",
                description=(
                    "Fragment nazwy inwestycji, 2–100 znaków, np. Kolibki. Z city wielkość liter "
                    "i polskie znaki nie mają znaczenia; bez city szuka serwis w całej Polsce."
                ),
            ),
        ] = None,
        developer_slug: Annotated[
            str | None,
            OptionalChoice,
            Field(
                title="Deweloper",
                description=(
                    "developer_slug z search_developers (po nazwie) albo z pól developer_slug w "
                    "search_offers, get_investment, get_offer, np. atal. Tylko z city."
                ),
            ),
        ] = None,
        sort: Annotated[
            InvestmentSortChoice | None,
            OptionalChoice,
            Field(
                title="Kolejność",
                description=(
                    "Tylko z city. active_offers: najwięcej aktywnych ofert (domyślnie); "
                    "price_per_m2_asc, price_per_m2_desc: średnia cena za m²; price_asc, "
                    "price_desc: średnia cena; name: alfabetycznie. Bez średniej na końcu."
                ),
            ),
        ] = None,
        limit: Annotated[
            Limit,
            whole_or(DEFAULT_INVESTMENTS_LIMIT),
            Field(
                title="Limit inwestycji",
                description=(
                    "Najwięcej inwestycji w wyniku, 1–30, domyślnie 10. Pozycja z city to ok. "
                    "550–750 znaków wyniku (z linkami), więc 30 daje najwyżej ok. 23 tys.; "
                    "zwykle wystarcza 10."
                ),
            ),
        ] = DEFAULT_INVESTMENTS_LIMIT,
    ) -> Annotated[CallToolResult, InvestmentsResult]:
        session = session_of(ctx)

        def search() -> InvestmentsResult:
            request = SearchInvestmentsRequest.parse(
                city=city, name=name, developer_slug=developer_slug, sort=sort, limit=limit
            )
            return SearchInvestmentsMcpPresenter().present(
                session.search_investments.execute(request)
            )

        return await run(search)
