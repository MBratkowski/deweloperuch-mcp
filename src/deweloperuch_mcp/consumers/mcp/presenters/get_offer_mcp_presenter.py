"""``GetOfferMcpPresenter`` (D17 reference): ``get_offer``'s result for a model, its output
schema (``OfferResult``), and the offer models ``get_investment``'s result shares
(``OfferFields``, ``PriceEventItem``)."""

import datetime as dt

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.mcp_model import (
    AREA,
    CHANGE_SINCE_START,
    CHANGE_SINCE_START_PCT,
    DEVELOPER_URL,
    EVENT_KIND,
    INVESTMENT_URL,
    PRICE,
    PRICE_PER_M2,
    STATUS,
    McpModel,
)
from deweloperuch_mcp.consumers.shared.offer_views import Developer, OfferDetailView
from deweloperuch_mcp.usecases.get_offer import GetOfferResult

# Class docstrings would become schema descriptions for the model: comments instead.


class PriceEventItem(McpModel):
    date: dt.date | None = None
    kind: str = Field(description=EVENT_KIND)
    price: float | None = Field(None, description=PRICE)


class OfferFields(McpModel):
    offer_id: int
    name: str
    status: str = Field(description=STATUS)
    price: float | None = Field(None, description=PRICE)
    currency: str | None = None
    area_m2: float | None = Field(None, description=AREA)
    price_per_m2: float | None = Field(None, description=PRICE_PER_M2)
    price_change_since_start: float | None = Field(None, description=CHANGE_SINCE_START)
    price_change_since_start_pct: float | None = Field(None, description=CHANGE_SINCE_START_PCT)
    creation_date: dt.date | None = None
    last_event_date: dt.date | None = None
    last_change_date: dt.date | None = None


class PriceFlagsItem(McpModel):
    lowest_price_30d: float | None = Field(
        None,
        description=(
            "Najniższa cena obowiązująca w ostatnich 30 dniach, także ta sprzed okna, o ile "
            "oferty wtedy nie wycofano (dla oferty archiwalnej: 30 dni przed wycofaniem)."
        ),
    )
    lowest_price_90d: float | None = Field(None, description="To samo dla 90 dni.")
    price_changes: int = Field(description="Ile razy cena zmieniła się względem poprzedniej.")
    largest_drop_pct: float | None = Field(
        None, description="Największa pojedyncza obniżka w % poprzedniej ceny (dodatnia)."
    )
    largest_rise_pct: float | None = Field(
        None, description="Największa pojedyncza podwyżka w % poprzedniej ceny."
    )
    suspicious_reduction: bool = Field(
        description=(
            "true: ostatnia obniżka nastąpiła do 30 dni po podwyżce, a nowa cena nie jest "
            "niższa od najniższej z 30 dni przed obniżką."
        )
    )


class OfferResult(OfferFields):
    investment_slug: str
    investment_name: str
    investment_url: str | None = Field(None, description=INVESTMENT_URL)
    city: str
    city_slug: str
    developer: Developer
    developer_url: str | None = Field(None, description=DEVELOPER_URL)
    price_history: list[PriceEventItem]
    price_flags: PriceFlagsItem | None = Field(
        None,
        description=(
            "Wnioski z historii ceny na dziś: ceny z offer i restored; wycofanie przerywa "
            "obowiązującą cenę."
        ),
    )


class GetOfferMcpPresenter:
    """The offer as its view has it (``OfferDetailView``); ``dump`` leaves out ``null``."""

    def present(self, result: GetOfferResult) -> OfferResult:
        return OfferResult.model_validate(OfferDetailView.from_result(result).model_dump())
