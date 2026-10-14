"""Use case ``GetMarketStatistics``: the offer market of one city in numbers (D15)."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.market_statistics import (
    DEFAULT_TOP_DEVELOPERS,
    MarketCriteria,
    MarketStatistics,
)
from deweloperuch_mcp.models.offer import OfferSearchCriteria
from deweloperuch_mcp.models.values import AreaRange, CitySlug, DeveloperCount, PriceRange
from deweloperuch_mcp.usecases.ports import CityOffersSource, PageLinks
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs


@dataclass(frozen=True, kw_only=True)
class GetMarketStatisticsRequest:
    """What a market summary asks for, checked (``parse``) before anything is sent."""

    criteria: MarketCriteria

    @classmethod
    def parse(  # noqa: PLR0913 - one keyword per argument of the tool and the command (D17)
        cls,
        *,
        city: object,
        price_min: object = None,
        price_max: object = None,
        area_min: object = None,
        area_max: object = None,
        top_developers: object = DEFAULT_TOP_DEVELOPERS,
    ) -> Self:
        """Checked in this order: city (one city, not polska), price, area, top developers.
        A refusal names the parameter (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(
                criteria=MarketCriteria(
                    city=MarketCriteria.one_city(CitySlug.parse(city)),
                    price=PriceRange.parse(price_min, price_max),
                    area=AreaRange.parse(area_min, area_max),
                    top=DeveloperCount.parse(top_developers),
                )
            )


@dataclass(frozen=True, kw_only=True)
class GetMarketStatisticsResult:
    """The summary with the links of D12: the list of the same offers on the service, and
    each top developer's profile in the city (aligned with ``statistics.top_developers``)."""

    statistics: MarketStatistics
    list_url: str | None
    developer_urls: tuple[str | None, ...]

    @property
    def hint(self) -> str | None:
        """What to do about an empty summary; ``None`` otherwise."""
        if self.statistics.offers:
            return None
        city = self.statistics.criteria.city.value
        return (
            f"Brak aktywnych ofert spełniających kryteria w {city!r}. Sprawdź slug miasta "
            "(search_locations) i poluzuj filtry (cena, metraż)."
        )


class GetMarketStatistics:
    """Every active offer of the city in one request; the domain sums them up and names
    the largest developers. Single offers stay here (D15)."""

    def __init__(self, source: CityOffersSource, links: PageLinks) -> None:
        self._source = source
        self._links = links

    def execute(self, request: GetMarketStatisticsRequest) -> GetMarketStatisticsResult:
        criteria = request.criteria
        city = criteria.city.value
        with ReportedAs(f"Statystyki rynku w {city!r}", not_found=self._unknown_city(city)):
            offers = self._source.city_offers(criteria.city)
        statistics = offers.statistics(criteria)
        same_offers = OfferSearchCriteria(
            city=criteria.city, price=criteria.price, area=criteria.area
        )
        return GetMarketStatisticsResult(
            statistics=statistics,
            list_url=self._links.offers_list(same_offers),
            developer_urls=tuple(
                self._links.developer_in(city, share.developer_slug)
                for share in statistics.top_developers
            ),
        )

    @staticmethod
    def _unknown_city(city: str) -> str:
        return (
            f"Serwis nie zna miasta {city!r}. Podaj city_slug z search_locations "
            "(statystyki rynku są tylko dla jednego miasta)."
        )
