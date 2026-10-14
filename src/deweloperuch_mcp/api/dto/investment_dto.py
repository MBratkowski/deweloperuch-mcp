"""``InvestmentDto``: ``GET /api/map/investments/visible/{slug}`` [P] (sample
``api.map_inv_visible``), an investment with every offer."""

from deweloperuch_mcp.api.dto.developer_dto import DeveloperDto
from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.api.dto.sale_dto import SaleDto
from deweloperuch_mcp.models.investment import Investment
from deweloperuch_mcp.models.offer import Offer


class InvestmentSaleDto(SaleDto):
    """One offer (``sale``) of ``InvestmentDto``; amounts and size as strings [P]."""

    invest_id: int | None = None
    type: str | None = None

    def to_model(self) -> Offer:
        return self._offer(self._history())


class InvestmentDto(Dto):
    invest_id: int
    developer_id: int | None = None
    city: str
    city_slug: str
    street: str | None = None
    latitude: Number | None = None
    longitude: Number | None = None
    name: str
    slug: str
    status: str
    currency: str | None = None
    avg_amount: Number | None = None
    avg_size: Number | None = None
    avg_price_sqm: Number | None = None
    avg_amount_archived: Number | None = None
    avg_size_archived: Number | None = None
    avg_price_sqm_archived: Number | None = None
    avg_amount_total: Number | None = None
    avg_size_total: Number | None = None
    avg_price_sqm_total: Number | None = None
    active_offers: int | None = None
    total_offers: int | None = None
    developer: DeveloperDto
    sale: list[InvestmentSaleDto]

    def to_model(self) -> Investment:
        """The investment with every offer, in the service's order."""
        return Investment(
            investment_id=self.invest_id,
            investment_slug=self.slug,
            name=self.name,
            status=self.status,
            city=self.city,
            city_slug=self.city_slug,
            street=self._text(self.street),
            lat=self._number(self.latitude),
            lng=self._number(self.longitude),
            currency=self._text(self.currency),
            developer=self.developer.to_model(),
            avg_price=self._number(self.avg_amount),
            avg_area_m2=self._number(self.avg_size),
            avg_price_per_m2=self._number(self.avg_price_sqm),
            offers_active=self.active_offers,
            offers_total=self.total_offers,
            offers=tuple(sale.to_model() for sale in self.sale),
        )
