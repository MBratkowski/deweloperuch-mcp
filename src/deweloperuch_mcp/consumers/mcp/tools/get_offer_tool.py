"""``GetOfferTool`` (D17 reference): one offer with its full price history."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.get_offer_mcp_presenter import (
    GetOfferMcpPresenter,
    OfferResult,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import OfferId, WholeNumber
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.usecases.get_offer import GetOfferRequest


class GetOfferTool(ToolBase):
    name = "get_offer"
    title = "Oferta z historią ceny"
    description = """\
Zwraca jedną ofertę z pełną historią ceny, inwestycją i deweloperem. Użyj, gdy chcesz \
zobaczyć, jak zmieniała się cena mieszkania. Wymaga offer_id i investment_slug (oba \
podaje search_offers albo get_investment): samo offer_id nie wystarcza.

Zwraca cenę, metraż, cenę za m², status (active albo archived), zmianę od pierwszej \
ceny, daty, price_history (date, kind: offer, archived albo restored, price) i \
price_flags. investment_url i developer_url to strony inwestycji i dewelopera na \
deweloperuch.pl: podawaj je użytkownikowi jako linki. Do listy ofert jednej inwestycji \
użyj get_investment.

price_flags (na dziś; ceny z offer i restored, wycofanie przerywa cenę; oferta \
archiwalna do dnia wycofania): lowest_price_30d i lowest_price_90d to najniższa cena \
obowiązująca w ostatnich 30 i 90 dniach, także ta sprzed okna; price_changes to liczba \
zmian ceny; largest_drop_pct i largest_rise_pct to największa pojedyncza obniżka i \
podwyżka w % poprzedniej ceny; suspicious_reduction=true, gdy ostatnia obniżka przyszła \
do 30 dni po podwyżce, a nowa cena nie jest niższa od najniższej z 30 dni przed nią \
(„promocja” po podwyżce)."""

    async def __call__(
        self,
        offer_id: Annotated[
            OfferId,
            WholeNumber,
            Field(title="Oferta", description="offer_id z search_offers albo get_investment."),
        ],
        investment_slug: Annotated[
            str,
            Field(
                title="Inwestycja",
                description=(
                    "investment_slug inwestycji tej oferty, np. smolna (z search_investments, "
                    "search_offers albo get_developer)."
                ),
            ),
        ],
        ctx: SessionContext,
    ) -> Annotated[CallToolResult, OfferResult]:
        session = session_of(ctx)

        def get() -> OfferResult:
            request = GetOfferRequest.parse(offer_id=offer_id, investment_slug=investment_slug)
            return GetOfferMcpPresenter().present(session.get_offer.execute(request))

        return await run(get)
