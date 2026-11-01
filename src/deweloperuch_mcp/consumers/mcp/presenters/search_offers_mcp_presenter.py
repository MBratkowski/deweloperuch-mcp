"""``SearchOffersMcpPresenter`` (D17 reference): ``search_offers``' result for a model, and its
output schema (``OffersResult``)."""

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.mcp_model import (
    AREA,
    CHANGE_SINCE_START_PCT,
    INVESTMENT_URL,
    LAST_CHANGE_KIND,
    LAST_CHANGE_PCT,
    LIST_URL,
    PRICE,
    PRICE_PER_M2,
    STATUS,
    McpModel,
)
from deweloperuch_mcp.consumers.shared.offer_views import OfferSearchView
from deweloperuch_mcp.usecases.search_offers import SearchOffersResult

# Class docstrings would become schema descriptions for the model: comments instead.


class OfferItem(McpModel):
    # A compact offer of the search results; get_offer has the rest.
    offer_id: int
    investment_slug: str
    name: str = Field(
        description=(
            "Oznaczenie mieszkania u dewelopera (np. A2, D1.1.1.4); nazwa inwestycji jest w "
            "investment_name."
        )
    )
    price: float | None = Field(None, description=PRICE)
    area_m2: float | None = Field(None, description=AREA)
    price_per_m2: float | None = Field(None, description=PRICE_PER_M2)
    status: str = Field(description=STATUS)
    investment_name: str
    district: str | None = Field(
        None,
        description=(
            "Dzielnica inwestycji, nazwa jak w search_locations (kind=district): można ją podać "
            "w district. Brak, gdy serwis jej nie podaje (np. Sopot)."
        ),
    )
    investment_url: str | None = Field(None, description=INVESTMENT_URL)
    developer_name: str
    developer_slug: str = Field(description="Slug dewelopera dla get_developer.")
    last_price_change_kind: str | None = Field(None, description=LAST_CHANGE_KIND)
    last_price_change_pct: float | None = Field(None, description=LAST_CHANGE_PCT)
    price_change_since_start_pct: float | None = Field(None, description=CHANGE_SINCE_START_PCT)


class OffersResult(McpModel):
    total: int
    returned: int
    truncated: bool = Field(
        description=(
            "true: pasujących ofert jest więcej, niż można przejrzeć (najwyżej 20 stron); "
            "zawęź filtry."
        )
    )
    page: int
    per_page: int
    pages_available: int
    hint: str | None = None
    list_url: str | None = Field(None, description=LIST_URL)
    items: list[OfferItem]


class SearchOffersMcpPresenter:
    """Compact offers, without their city: a search is of one city, the one asked for.

    A truncated result gets its own hint: narrow the filters. The use case's hint also
    suggests a bigger page, which would not narrow anything and is not offered here.
    """

    def present(self, result: SearchOffersResult) -> OffersResult:
        view = OfferSearchView.from_result(result)
        data = view.model_dump()
        if view.truncated:
            data["hint"] = self._truncated_hint(view, result.narrowing)
        return OffersResult.model_validate(data)

    @staticmethod
    def _truncated_hint(view: OfferSearchView, narrowing: str) -> str:
        shown = view.pages_available * view.per_page
        return (
            f"Pasujących ofert jest {view.total}, a można przejrzeć najwyżej "
            f"{view.pages_available} stron po {view.per_page} ({shown}). Zawęź filtry "
            f"({narrowing})."
        )
