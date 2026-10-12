"""Tool ``get_investment``: an investment with its developer and offers."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.application import arguments
from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.interfaces import views
from deweloperuch_mcp.interfaces.mcp import presenters
from deweloperuch_mcp.interfaces.mcp.calls import SessionContext, run, session_of
from deweloperuch_mcp.interfaces.mcp.inputs import null_is, whole_or
from deweloperuch_mcp.interfaces.mcp.presenters import InvestmentResult

DEFAULT_INVESTMENT_LIMIT = 20
"""Offers ``get_investment`` returns unless asked otherwise (about 6k characters)."""
MAX_INVESTMENT_LIMIT = 200
Limit = Annotated[int, Field(ge=0, le=MAX_INVESTMENT_LIMIT)]


def _investment(session: Session, slug: str, include_history: bool, limit: int) -> views.Investment:
    given = arguments.investment(slug, include_history=include_history, limit=limit)
    found = session.get_investment(
        given.investment, include_history=given.include_history, limit=given.limit
    )
    return views.investment(found)


GET_INVESTMENT = """\
Zwraca inwestycję (projekt deweloperski): miasto, ulicę, współrzędne, dewelopera, \
średnie ceny aktywnych ofert, liczbę ofert i listę ofert (najpierw aktywne, potem \
archiwalne). Użyj, gdy chcesz zobaczyć mieszkania jednego projektu. investment_slug \
podaje search_offers. investment_url i developer_url to strony inwestycji i dewelopera \
na deweloperuch.pl: podawaj je użytkownikowi jako linki.

Ograniczenia: zwraca najwyżej limit ofert (domyślnie 20); offers_returned mówi, ile ich \
jest na liście, truncated i offers_omitted, czy i ile pominięto. offers_total to liczba \
z serwisu, a pominięte oferty liczy offers_omitted. Przy dużej inwestycji nie zwiększaj \
limitu bez potrzeby; offers_omitted > 0 znaczy, że lista jest niepełna. \
include_history=true dodaje historię ceny każdej zwróconej oferty: wynik jest dłuższy i \
powstaje wolniej. Dla jednej oferty lepiej użyć get_offer."""


async def get_investment(
    investment_slug: Annotated[
        str,
        Field(title="Inwestycja", description="investment_slug z search_offers, np. smolna."),
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
    return await run(
        lambda: presenters.investment(_investment(session, investment_slug, include_history, limit))
    )
