"""``SearchInvestmentsMcpPresenter``: ``search_investments``' result for a model, and its
output schema (``InvestmentsResult``)."""

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.mcp_model import (
    DEVELOPER_URL,
    INVESTMENT_URL,
    STATUS,
    McpModel,
)
from deweloperuch_mcp.consumers.shared.investment_search_views import InvestmentSearchView
from deweloperuch_mcp.usecases.search_investments import SearchInvestmentsResult

# Class docstrings would become schema descriptions for the model: comments instead.


class InvestmentSearchItem(McpModel):
    # Compact: no city name nor coordinates (the CLI's --json has them).
    investment_slug: str
    name: str
    city_slug: str | None = None
    district: str | None = None
    street: str | None = None
    status: str | None = Field(None, description=STATUS)
    offers_active: int | None = Field(None, description="Aktywne oferty wg serwisu.")
    offers_total: int | None = Field(
        None, description="Wszystkie oferty wg serwisu, także archiwalne."
    )
    avg_price: float | None = Field(None, description="Średnia cena aktywnych ofert w PLN.")
    avg_area_m2: float | None = Field(None, description="Średni metraż aktywnych ofert w m².")
    avg_price_per_m2: float | None = Field(
        None, description="Średnia cena za m² aktywnych ofert w PLN."
    )
    developer_slug: str | None = None
    developer_name: str | None = None
    investment_url: str | None = Field(None, description=INVESTMENT_URL)
    developer_url: str | None = Field(None, description=DEVELOPER_URL)


class InvestmentsResult(McpModel):
    keep_null = frozenset({"total"})  # D4: always there, null when unknown

    total: int | None = Field(
        description="Wszystkie pasujące; null, gdy serwis nie podaje (szukanie po nazwie)."
    )
    returned: int
    truncated: bool = Field(
        description="true: pasujących jest więcej, niż pokazano; co zawęzić, mówi hint."
    )
    hint: str | None = None
    items: list[InvestmentSearchItem]


class SearchInvestmentsMcpPresenter:
    """The investments as their view has them (``InvestmentSearchView``); ``dump`` leaves
    out ``null``, except ``total``."""

    def present(self, result: SearchInvestmentsResult) -> InvestmentsResult:
        return InvestmentsResult.model_validate(
            InvestmentSearchView.from_result(result).model_dump()
        )
