"""``GetDeveloperMcpPresenter``: ``get_developer``'s result for a model, and its output schema
(``DeveloperResult``)."""

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.mcp_model import (
    DEVELOPER_URL,
    INVESTMENT_URL,
    STATUS,
    McpModel,
)
from deweloperuch_mcp.consumers.shared.developer_views import DeveloperProfileView
from deweloperuch_mcp.usecases.get_developer import GetDeveloperResult

# Class docstrings would become schema descriptions for the model: comments instead.


class DeveloperBrief(McpModel):
    developer_slug: str
    name: str
    website: str | None = None


class DeveloperSummaryItem(McpModel):
    # [P 2026-10-13] the meaning of every field: tests/contract/api/dto/test_developer_page_dto.py.
    active_offers: int | None = Field(None, description="Aktywne oferty w zakresie city.")
    cities: int | None = Field(
        None,
        description=(
            "Miasta z aktywnymi ofertami w zakresie city (lista cities obejmuje zawsze "
            "wszystkie miasta dewelopera)."
        ),
    )
    avg_price: float | None = Field(None, description="Średnia cena aktywnych ofert w PLN.")
    avg_area_m2: float | None = Field(None, description="Średni metraż aktywnych ofert.")
    avg_price_per_m2: float | None = Field(
        None, description="Średnia cena za m² aktywnych ofert wg serwisu."
    )


class DeveloperInvestmentItem(McpModel):
    investment_slug: str
    name: str
    city: str | None = None
    city_slug: str | None = None
    status: str = Field(description=STATUS)
    active_offers: int | None = None
    total_offers: int | None = Field(None, description="Aktywne i archiwalne oferty.")
    avg_price: float | None = Field(None, description="Średnia cena aktywnych ofert w PLN.")
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None
    investment_url: str | None = Field(None, description=INVESTMENT_URL)


class DeveloperCityItem(McpModel):
    city: str
    city_slug: str
    investments: int | None = Field(None, description="Inwestycje z aktywnymi ofertami.")
    active_offers: int | None = None
    avg_price: float | None = Field(None, description="Średnia cena aktywnych ofert w PLN.")
    avg_price_per_m2: float | None = None


class DeveloperResult(McpModel):
    developer: DeveloperBrief
    developer_url: str | None = Field(None, description=DEVELOPER_URL)
    city_slug: str = Field(description="Zakres summary i investments: miasto albo polska.")
    summary: DeveloperSummaryItem
    investments_total: int = Field(description="Wszystkie inwestycje z aktywnymi ofertami.")
    investments_returned: int
    investments_omitted: int = Field(description="Inwestycji pominiętych przez limit.")
    truncated: bool = Field(description="true: lista investments jest niepełna.")
    hint: str | None = None
    investments: list[DeveloperInvestmentItem]
    cities: list[DeveloperCityItem] = Field(
        description=(
            "Wszystkie miasta dewelopera w Polsce, niezależnie od argumentu city (także "
            "przy city=warszawa)."
        )
    )


class GetDeveloperMcpPresenter:
    """The profile as its view has it (``DeveloperProfileView``) with the D4 counters; a
    truncated result gets a hint: a larger ``limit``, up to ``max_limit`` (the tool's)."""

    def __init__(self, *, max_limit: int) -> None:
        self._max_limit = max_limit

    def present(self, result: GetDeveloperResult) -> DeveloperResult:
        view = DeveloperProfileView.from_result(result)
        data = view.model_dump()
        returned = len(view.investments)
        data["investments_returned"] = returned
        data["truncated"] = view.investments_omitted > 0
        if data["truncated"] and view.hint is None:
            data["hint"] = self._larger_limit(returned, view.investments_total)
        return DeveloperResult.model_validate(data)

    def _larger_limit(self, returned: int, total: int) -> str:
        shown = f"Pokazano {returned} z {total} inwestycji (najwięcej aktywnych ofert)"
        if returned < self._max_limit:
            return f"{shown}; pozostałe pokaże większy limit (najwyżej {self._max_limit})."
        return f"{shown}. To maksimum w jednym wywołaniu; zawęź city do jednego miasta."
