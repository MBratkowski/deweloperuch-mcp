"""The views of the offer market of a city (D15): what ``get_market_statistics`` shows, for
the CLI (``--json``) and the MCP presenter. Each builds itself from the use case's result
(``from_result``) or a model (``from_model``); prices are whole PLN and areas to 0.01 m²
(the models keep them exact)."""

import dataclasses
from typing import Self

from deweloperuch_mcp.consumers.shared.view import View
from deweloperuch_mcp.models.market_statistics import DeveloperShare, Spread
from deweloperuch_mcp.usecases.get_market_statistics import GetMarketStatisticsResult


class SpreadView(View):
    """The smallest value, the quartiles, the median and the largest one."""

    min: int | float
    p25: int | float
    median: int | float
    p75: int | float
    max: int | float

    @classmethod
    def from_model(cls, spread: Spread | None, digits: int | None = None) -> Self | None:
        """Whole numbers (``digits`` ``None``) or rounded to ``digits``; ``None`` for no
        values."""
        if spread is None:
            return None
        values = dataclasses.asdict(spread)
        return cls(**{name: round(value, digits) for name, value in values.items()})


class DeveloperShareView(View):
    developer_slug: str
    offers: int
    investments: int
    median_price_per_m2: int | None = None
    """PLN/m², whole."""
    developer_url: str | None = None

    @classmethod
    def from_model(cls, share: DeveloperShare, developer_url: str | None) -> Self:
        median = share.median_price_per_m2
        return cls(
            developer_slug=share.developer_slug,
            offers=share.offers,
            investments=share.investments,
            median_price_per_m2=None if median is None else round(median),
            developer_url=developer_url,
        )


class MarketStatisticsView(View):
    """Active offers of a city that match the filters, summed up (``get_market_statistics``)."""

    city_slug: str
    offers: int
    investments: int
    developers: int
    """Developers with at least one matching offer."""
    price: SpreadView | None = None
    """PLN, whole."""
    price_per_m2: SpreadView | None = None
    """PLN/m², whole."""
    area_m2: SpreadView | None = None
    """m², to 0.01."""
    top_developers: list[DeveloperShareView]
    developers_omitted: int
    hint: str | None = None
    list_url: str | None = None
    """The list of these offers on the service (the same filters of price and area)."""

    @classmethod
    def from_result(cls, found: GetMarketStatisticsResult) -> Self:
        result = found.statistics
        return cls(
            city_slug=result.criteria.city.value,
            offers=result.offers,
            investments=result.investments,
            developers=result.developers,
            price=SpreadView.from_model(result.price_spread),
            price_per_m2=SpreadView.from_model(result.price_per_m2_spread),
            area_m2=SpreadView.from_model(result.area_spread, 2),
            top_developers=[
                DeveloperShareView.from_model(share, url)
                for share, url in zip(result.top_developers, found.developer_urls, strict=True)
            ],
            developers_omitted=result.developers_omitted,
            hint=found.hint,
            list_url=found.list_url,
        )
