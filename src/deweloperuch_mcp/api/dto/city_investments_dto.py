"""``CityInvestmentsDto``: ``GET /api/map/investments?citySlug=`` [P] (sample
``api.map_investments_sopot``), every investment of a city's map at once, a JSON array."""

from pydantic import ConfigDict, RootModel

from deweloperuch_mcp.api.dto.developer_dto import DeveloperDto
from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.models.investment_summary import InvestmentSummary


class CityInvestmentDto(Dto):
    """An investment of the city's map; the averages come as numbers, unrounded
    (``63.966667``)."""

    invest_id: int | None = None
    latitude: Number | None = None
    longitude: Number | None = None
    name: str
    slug: str
    city: str
    city_slug: str
    street: str | None = None
    district: str | None = None
    status: str
    avg_amount: Number | None = None
    avg_size: Number | None = None
    avg_price_sqm: Number | None = None
    active_offers: int | None = None
    total_offers: int | None = None
    developer: DeveloperDto

    def to_model(self) -> InvestmentSummary:
        return InvestmentSummary(
            investment_slug=self.slug,
            name=self.name,
            status=self.status,
            city=self.city,
            city_slug=self.city_slug,
            district=self._text(self.district),
            street=self._text(self.street),
            lat=self._number(self.latitude),
            lng=self._number(self.longitude),
            developer=self.developer.to_model(),
            # [P] the mean of the active offers: smolna's 1566392 is the mean of its three
            # active prices in api.city_sales_sopot, captured the same day.
            avg_price=self._average(self.avg_amount, 0),
            avg_area_m2=self._average(self.avg_size, 2),
            avg_price_per_m2=self._average(self.avg_price_sqm, 2),
            offers_active=self.active_offers,
            offers_total=self.total_offers,
        )

    @classmethod
    def _average(cls, value: int | float | str | None, digits: int) -> float | None:
        """An average of the active offers, rounded to ``digits``; 0 is no average.

        [W] sample api.map_investments_sopot (2026-10-09): 0 means there was nothing to
        average. Its ``avg_*_archived`` are 0 although both investments have archived
        offers (``total_offers`` > ``active_offers``), so a 0 is not a price.
        """
        found = cls._number(value)
        return round(found, digits) if found else None


class CityInvestmentsDto(RootModel[list[CityInvestmentDto]]):
    model_config = ConfigDict(frozen=True)

    def to_model(self) -> tuple[InvestmentSummary, ...]:
        """The city's investments in the service's order."""
        return tuple(item.to_model() for item in self.root)
