"""``GetInvestmentMcpPresenter``: ``get_investment``'s result for a model, and its output
schema (``InvestmentResult``); its offers share ``get_offer``'s models (``OfferFields``,
``PriceEventItem``)."""

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.get_offer_mcp_presenter import (
    OfferFields,
    PriceEventItem,
)
from deweloperuch_mcp.consumers.mcp.support.mcp_model import (
    DEVELOPER_URL,
    INVESTMENT_URL,
    STATUS,
    McpModel,
)
from deweloperuch_mcp.consumers.shared.investment_views import InvestmentView
from deweloperuch_mcp.consumers.shared.offer_views import Developer
from deweloperuch_mcp.usecases.get_investment import GetInvestmentResult

# Class docstrings would become schema descriptions for the model: comments instead.


class InvestmentOfferItem(OfferFields):
    price_history: list[PriceEventItem] | None = None


class InvestmentResult(McpModel):
    investment_slug: str
    name: str
    status: str = Field(description=STATUS)
    investment_url: str | None = Field(None, description=INVESTMENT_URL)
    city: str
    city_slug: str
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    currency: str | None = None
    developer: Developer
    developer_url: str | None = Field(None, description=DEVELOPER_URL)
    avg_price: float | None = Field(None, description="Średnia cena aktywnych ofert w PLN.")
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None
    offers_active: int | None = None
    offers_total: int | None = Field(
        None,
        description=(
            "Wszystkie oferty inwestycji wg serwisu, także archiwalne; lista offers jest "
            "ucięta przez limit."
        ),
    )
    offers: list[InvestmentOfferItem]
    offers_returned: int = Field(description="Ofert na liście offers.")
    offers_omitted: int = Field(description="Ofert pominiętych przez limit.")
    truncated: bool = Field(description="true: lista offers jest niepełna (offers_omitted > 0).")


class GetInvestmentMcpPresenter:
    """The investment as its view has it, with how many offers it returned and whether
    the list is cut (D4)."""

    def present(self, result: GetInvestmentResult) -> InvestmentResult:
        view = InvestmentView.from_result(result)
        data = view.model_dump()
        data["offers_returned"] = len(view.offers)
        data["truncated"] = view.offers_omitted > 0
        return InvestmentResult.model_validate(data)
