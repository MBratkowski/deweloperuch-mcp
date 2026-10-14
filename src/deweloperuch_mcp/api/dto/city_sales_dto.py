"""``CitySalesDto``: ``GET /api/offers/city-sales/{citySlug}`` [P] (sample
``api.city_sales_sopot``, tests/fixtures/api/city_sales_*.json), every active offer of a
city in a compact form, with the investments they belong to (D15)."""

from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.models.market_statistics import CityOffers, MarketOffer
from deweloperuch_mcp.models.values import CitySlug


class CitySalesInvestmentDto(Dto):
    id: int
    slug: str
    developerSlug: str | None = None
    status: str | None = None


class CitySaleDto(Dto):
    """One active offer, compact: ``priceSqm`` is ``amount / size`` to 0.01 [P 2026-10-13,
    tests/fixtures/api/city_sales_krakow.json], so it is not read (the domain derives it)."""

    id: int
    investId: int | None
    amount: Number | None
    size: Number | None
    status: str

    def to_model(self, investment: CitySalesInvestmentDto | None) -> MarketOffer:
        """The offer with the slugs of ``investment`` (``None``: not on the city's list)."""
        return MarketOffer(
            offer_id=self.id,
            investment_slug=None if investment is None else investment.slug,
            developer_slug=None if investment is None else self._text(investment.developerSlug),
            status=self.status,
            price=self._number(self.amount),
            area_m2=self._number(self.size),
        )


class CitySalesDto(Dto):
    investments: list[CitySalesInvestmentDto]
    sales: list[CitySaleDto]

    def to_model(self, city: CitySlug) -> CityOffers:
        """Each offer with the slugs of its investment and developer (``None`` when its
        investment is not on the city's list)."""
        investments = {item.id: item for item in self.investments}
        return CityOffers(
            city=city,
            offers=tuple(
                sale.to_model(None if sale.investId is None else investments.get(sale.investId))
                for sale in self.sales
            ),
        )
