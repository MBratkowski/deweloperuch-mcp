"""``GetMarketStatisticsMcpPresenter``: ``get_market_statistics``'s result for a model and
its output schema (``MarketStatisticsResult``)."""

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.mcp_model import DEVELOPER_URL, McpModel
from deweloperuch_mcp.consumers.shared.market_views import MarketStatisticsView
from deweloperuch_mcp.usecases.get_market_statistics import GetMarketStatisticsResult

# Class docstrings would become schema descriptions for the model: comments instead.


class SpreadItem(McpModel):
    min: int | float
    p25: int | float
    median: int | float
    p75: int | float
    max: int | float


class DeveloperShareItem(McpModel):
    developer_slug: str = Field(
        description="Identyfikator dewelopera (bez nazwy); nazwę i inwestycje daje get_developer."
    )
    offers: int = Field(description="Pasujące aktywne oferty dewelopera w mieście.")
    investments: int
    median_price_per_m2: int | None = Field(None, description="Mediana ceny za m² w PLN.")
    developer_url: str | None = Field(None, description=DEVELOPER_URL)


class MarketStatisticsResult(McpModel):
    city_slug: str
    offers: int = Field(description="Pasujące aktywne oferty.")
    investments: int
    developers: int = Field(description="Wszyscy deweloperzy z pasującymi ofertami.")
    price: SpreadItem | None = Field(None, description="Ceny w PLN: min, kwartyle, mediana, max.")
    price_per_m2: SpreadItem | None = Field(None, description="Ceny za m² w PLN.")
    area_m2: SpreadItem | None = Field(None, description="Metraże w m².")
    top_developers: list[DeveloperShareItem] = Field(
        description="Deweloperzy z największą liczbą pasujących ofert, malejąco."
    )
    developers_returned: int
    developers_omitted: int
    truncated: bool = Field(description="true: deweloperów jest więcej niż w top_developers.")
    hint: str | None = None
    list_url: str | None = Field(
        None,
        description=(
            "Lista tych ofert na deweloperuch.pl (te same filtry ceny i metrażu): podaj ją "
            "użytkownikowi jako link."
        ),
    )


class GetMarketStatisticsMcpPresenter:
    """The summary as its view has it (``MarketStatisticsView``) with the D4 counters of
    the developers; ``dump`` leaves out ``null``."""

    def present(self, result: GetMarketStatisticsResult) -> MarketStatisticsResult:
        view = MarketStatisticsView.from_result(result)
        data = view.model_dump()
        data["developers_returned"] = len(view.top_developers)
        data["truncated"] = view.developers_omitted > 0
        return MarketStatisticsResult.model_validate(data)
