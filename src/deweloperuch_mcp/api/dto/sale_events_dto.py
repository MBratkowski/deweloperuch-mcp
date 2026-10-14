"""``SaleEventsDto``: ``GET /api/sale-events?saleId=`` [P] (sample ``api.sale_events``), the
price events of one offer, and ``SaleEventDto``, one event, also of
``InvestmentSaleEventsDto`` (``api.dto.investment_dto``)."""

import datetime as dt
from collections.abc import Sequence

from deweloperuch_mcp.api.dto.dto import DateText, Dto, Number
from deweloperuch_mcp.models.price_history import (
    EVENT_ARCHIVED,
    EVENT_OFFER,
    EVENT_RESTORED,
    PriceEvent,
)

_EVENT_KINDS = {
    "OFFER_EVENT": EVENT_OFFER,
    "ARCHIVED_EVENT": EVENT_ARCHIVED,
    "RESTORED_EVENT": EVENT_RESTORED,
}


class SaleEventDto(Dto):
    sale_event_id: int
    event_type: str
    event_data: str | None = None
    amount: Number | None
    event_date: DateText
    source: str | None = None

    def to_model(self) -> PriceEvent:
        return PriceEvent(
            date=self._day(self.event_date),
            kind=self._kind(self.event_type),
            price=self._number(self.amount),
        )

    @classmethod
    def price_events(cls, events: Sequence["SaleEventDto"]) -> tuple[PriceEvent, ...]:
        """Chronological; events of one day in the order the service recorded them (by id).

        The service does not sort them (sample ``api.inv_sale_events``). Events without a
        date (none seen so far) come first.
        """
        ordered = sorted(
            events, key=lambda e: (cls._day(e.event_date) or dt.date.min, e.sale_event_id)
        )
        return tuple(event.to_model() for event in ordered)

    @staticmethod
    def _kind(value: str) -> str:
        """``OFFER_EVENT`` -> ``offer``, ``ARCHIVED_EVENT`` -> ``archived``,
        ``RESTORED_EVENT`` -> ``restored``; unknown ones lowercased without ``_event``."""
        return _EVENT_KINDS.get(value, value.lower().removesuffix("_event"))


class SaleDataDto(Dto):
    name: str | None = None
    amount: Number | None = None
    size: Number | None = None
    currency: str | None = None


class SaleEventsDto(Dto):
    success: bool | None = None
    saleData: SaleDataDto | None = None
    events: list[SaleEventDto]

    def to_model(self) -> tuple[PriceEvent, ...]:
        return SaleEventDto.price_events(self.events)
