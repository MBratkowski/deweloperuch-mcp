"""``OffersPageDto``: prop ``initialData`` of ``/ceny-ofertowe/{city}/mieszkania`` (RSC) [P]
(samples ``page.offers_list``, ``page.offers_list.filtered``): one page of offers, each
with its investment and developer.

Since the 2.0 build (2026-10-29) the page has no ``initialData``: the rows are the prop
``sales`` (the same fields) and the paging is ``serverPaginationData`` [P 2026-10-30, live
RSC payload of the package client]; ``from_props`` reads either shape.
"""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any, Self

from deweloperuch_mcp.api.dto.developer_dto import DeveloperDto
from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.api.dto.sale_dto import SaleDto
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError
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


OFFERS_PROPS = ("initialData", "sales", "serverPaginationData")
"""The props ``from_props`` reads: the old shape (``initialData``) or the 2.0 one."""


class OffersPageDto(Dto):
    data: list[SaleListItemDto]
    pagination: PaginationDto

    @classmethod
    def from_props(cls, props: Mapping[str, list[Any]], *, path: str) -> Self:
        """The page from ``OFFERS_PROPS`` (``RscPage.props``): ``initialData`` as it is, or
        the 2.0 props ``sales`` and ``serverPaginationData`` (``currentPage``, ``perPage``,
        ``totalCount``, ``totalPages``) [P 2026-10-30]."""
        old = [value for value in props.get("initialData", ()) if isinstance(value, dict)]
        if old:
            return Dto.validated(cls, old[0], f"{path} (prop initialData)")
        sales = [value for value in props.get("sales", ()) if isinstance(value, list)]
        paging = [v for v in props.get("serverPaginationData", ()) if isinstance(v, dict)]
        if not sales or not paging:
            raise UnexpectedResponseError(
                f"Na stronie serwisu brakuje oczekiwanych danych. {SERVICE_CHANGED}",
                detail=f"{path}: brak propsów sales i serverPaginationData (2.0)",
            )
        page = paging[0]
        data = {
            "data": sales[0],
            "pagination": {
                "page": page.get("currentPage"),
                "perPage": page.get("perPage"),
                "total": page.get("totalCount"),
                "totalPages": page.get("totalPages"),
            },
        }
        return Dto.validated(cls, data, f"{path} (propsy sales, serverPaginationData)")

    def to_model(self) -> OfferSearchPage:
        """The page as the service paged it (its own ``page`` and ``perPage``)."""
        return OfferSearchPage(
            items=tuple(item.to_model() for item in self.data),
            total=self.pagination.total,
            page=self.pagination.page,
            per_page=self.pagination.perPage,
        )
