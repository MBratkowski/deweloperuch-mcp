"""``GetInvestmentTool``: an investment with its developer and offers."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.get_investment_mcp_presenter import (
    GetInvestmentMcpPresenter,
    InvestmentResult,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import null_is, whole_or
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.usecases.get_investment import GetInvestmentRequest

DEFAULT_INVESTMENT_LIMIT = 20
"""Offers ``get_investment`` returns unless asked otherwise (about 6k characters)."""
MAX_INVESTMENT_LIMIT = 200
Limit = Annotated[int, Field(ge=0, le=MAX_INVESTMENT_LIMIT)]


class GetInvestmentTool(ToolBase):
    name = "get_investment"
    title = "Inwestycja z ofertami"
    description = """\
Zwraca inwestycję (projekt deweloperski): miasto, ulicę, współrzędne, dewelopera, \
średnie ceny aktywnych ofert, liczbę ofert i listę ofert (najpierw aktywne, potem \
archiwalne). Użyj, gdy chcesz zobaczyć mieszkania jednego projektu. investment_slug \
daje search_investments, search_offers albo get_developer. investment_url i \
developer_url to strony inwestycji i dewelopera na deweloperuch.pl: podawaj je \
użytkownikowi jako linki.

Ograniczenia: zwraca najwyżej limit ofert (domyślnie 20); offers_returned mówi, ile ich \
jest na liście, truncated i offers_omitted, czy i ile pominięto. offers_total to liczba \
z serwisu, a pominięte oferty liczy offers_omitted. Przy dużej inwestycji nie zwiększaj \
limitu bez potrzeby; offers_omitted > 0 znaczy, że lista jest niepełna. \
include_history=true dodaje historię ceny każdej zwróconej oferty: wynik jest dłuższy i \
powstaje wolniej. Dla jednej oferty lepiej użyć get_offer."""

    async def __call__(
        self,
        investment_slug: Annotated[
            str,
            Field(
                title="Inwestycja",
                description=(
                    "investment_slug z search_investments, search_offers albo get_developer, np. "
                    "smolna."
                ),
            ),
        ],
        ctx: SessionContext,
        include_history: Annotated[
            bool,
            null_is(False),
            Field(
                title="Z historią cen",
                description="true: dołącz historię ceny każdej zwróconej oferty (dłuższy wynik).",
            ),
        ] = False,
        limit: Annotated[
            Limit,
            whole_or(DEFAULT_INVESTMENT_LIMIT),
            Field(
                title="Limit ofert",
                description=(
                    "Najwięcej ofert w wyniku (najpierw aktywne), domyślnie 20, 0 = tylko "
                    "podsumowanie inwestycji. Ile pominięto, mówi offers_omitted. Każda oferta "
                    "to ok. 300 znaków wyniku, z historią ceny kilkaset więcej. Maksimum 200 "
                    "daje ok. 60 tys. znaków; zwykle wystarcza domyślne 20."
                ),
            ),
        ] = DEFAULT_INVESTMENT_LIMIT,
    ) -> Annotated[CallToolResult, InvestmentResult]:
        session = session_of(ctx)

        def get() -> InvestmentResult:
            request = GetInvestmentRequest.parse(
                investment_slug=investment_slug, include_history=include_history, limit=limit
            )
            return GetInvestmentMcpPresenter().present(session.get_investment.execute(request))

        return await run(get)
