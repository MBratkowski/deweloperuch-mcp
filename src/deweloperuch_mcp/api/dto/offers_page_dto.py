"""``OffersPageDto``: prop ``initialData`` of ``/ceny-ofertowe/{city}/mieszkania`` (RSC) [P]
(samples ``page.offers_list``, ``page.offers_list.filtered``): one page of offers, each
with its investment and developer."""

from dataclasses import replace

from deweloperuch_mcp.api.dto.developer_dto import DeveloperDto
from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.api.dto.sale_dto import SaleDto
from deweloperuch_mcp.models.offer import InvestmentRef, ListedOffer, OfferSearchPage
from deweloperuch_mcp.models.price_history import DECREASE, INCREASE, NO_CHANGE, PriceChange

_CHANGE_KINDS = {"PRICE_INCREASE": INCREASE, "PRICE_DECREASE": DECREASE, "NO_CHANGE": NO_CHANGE}


class SaleListInvestDto(Dto):
    invest_id: int | None = None
    name: str
    city: str | None = None
    city_slug: str | None = None
    slug: str
    developer: DeveloperDto

    def to_model(self) -> InvestmentRef:
        return InvestmentRef(
            investment_slug=self.slug,
            name=self.name,
            city=self._text(self.city),
            city_slug=self._text(self.city_slug),
            developer=self.developer.to_model(),
        )


class SaleListItemDto(SaleDto):
    last_amount_difference: Number | None = None
    last_amount_difference_percent: Number | None = None
    last_event_type: str | None = None
    total_events: int | None = None
    invest: SaleListInvestDto

    def to_model(self) -> ListedOffer:
        """An offer of the search results: its last change and its number of events too."""
        history = replace(
            self._history(),
            last_change=PriceChange(
                pln=self._number(self.last_amount_difference),
                percent=self._number(self.last_amount_difference_percent),
                direction=self._change_kind(self.last_event_type),
            ),
            events_count=self.total_events,
        )
        return ListedOffer(offer=self._offer(history), investment=self.invest.to_model())

    @classmethod
    def _change_kind(cls, value: str | None) -> str | None:
        """``PRICE_INCREASE`` -> ``increase``, ``PRICE_DECREASE`` -> ``decrease``,
        ``NO_CHANGE`` -> ``no_change``; unknown ones lowercased."""
        raw = cls._text(value)
        return None if raw is None else _CHANGE_KINDS.get(raw, raw.lower())


class PaginationDto(Dto):
    page: int
    perPage: int
    total: int
    totalPages: int | None = None


class OffersPageDto(Dto):
    data: list[SaleListItemDto]
    pagination: PaginationDto

    def to_model(self) -> OfferSearchPage:
        """The page as the service paged it (its own ``page`` and ``perPage``)."""
        return OfferSearchPage(
            items=tuple(item.to_model() for item in self.data),
            total=self.pagination.total,
            page=self.pagination.page,
            per_page=self.pagination.perPage,
        )
