"""``OffersPageDto``: one page of the offers list of a city or of a district
(``/ceny-ofertowe/{city}[/{district}]/mieszkania``, RSC) [P 2026-10-31]: the props ``sales``
(the offers, each with its investment and developer) and ``serverPaginationData``
(samples ``page.offers_list.v2_sales``, ``page.offers_list.v2_pagination``; whole pages in
tests/fixtures/rsc/offers_warszawa_20261031.rsc and offers_warszawa_mokotow_20261031.rsc).
The 1.0 prop ``initialData`` is gone since 2026-10-29."""

from dataclasses import replace

from deweloperuch_mcp.api.dto.developer_dto import DeveloperDto
from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.api.dto.sale_dto import SaleDto
from deweloperuch_mcp.models.offer import InvestmentRef, ListedOffer, OfferSearchPage
from deweloperuch_mcp.models.price_history import DECREASE, INCREASE, NO_CHANGE, PriceChange

_CHANGE_KINDS = {"PRICE_INCREASE": INCREASE, "PRICE_DECREASE": DECREASE, "NO_CHANGE": NO_CHANGE}


class SaleListInvestDto(Dto):
    """``invest`` of a row. 2.0 added ``district`` and ``street`` [P 2026-10-31]: the district
    is a name, as the locations search gives it (``Mokotów``), and the search shows it; the
    street is not shown. ``""`` where the investment has none (Sopot in the offer snapshot
    [P 2026-10-31])."""

    invest_id: int | None = None
    name: str
    city: str | None = None
    city_slug: str | None = None
    slug: str
    district: str | None = None
    developer: DeveloperDto

    def to_model(self) -> InvestmentRef:
        return InvestmentRef(
            investment_slug=self.slug,
            name=self.name,
            city=self._text(self.city),
            city_slug=self._text(self.city_slug),
            district=self._text(self.district),
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
        ``NO_CHANGE`` -> ``no_change``; unknown ones (``NEW_OFFER`` [P 2026-10-31])
        lowercased."""
        raw = cls._text(value)
        return None if raw is None else _CHANGE_KINDS.get(raw, raw.lower())


class ServerPaginationDto(Dto):
    """``serverPaginationData``: integers [P 2026-10-31]. ``totalPages`` (capped at 20),
    ``startItem`` and ``endItem`` are not read: the model counts the pages itself."""

    currentPage: int
    perPage: int
    totalCount: int


class OffersPageDto(Dto):
    sales: list[SaleListItemDto]
    serverPaginationData: ServerPaginationDto

    def to_model(self) -> OfferSearchPage:
        """The page as the service paged it (its own page and page size)."""
        paging = self.serverPaginationData
        return OfferSearchPage(
            items=tuple(item.to_model() for item in self.sales),
            total=paging.totalCount,
            page=paging.currentPage,
            per_page=paging.perPage,
        )
