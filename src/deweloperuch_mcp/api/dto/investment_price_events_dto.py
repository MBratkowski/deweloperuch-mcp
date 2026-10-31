"""``InvestmentPriceEventsDto``: the price events of every offer of an investment, read
from the answer of ``GET /api/map/investments/visible/{slug}`` (``InvestmentDto`` reads the
investment from it). Since the service's 2.0 of 2026-10-29 each ``sale`` carries its
events in ``ev`` [P 2026-10-30] (samples ``api.map_inv_visible.v2`` and
``api.map_inv_visible.no_v``; a whole answer in
tests/fixtures/api/map_inv_visible_smolna_20261031.json).

``ev`` took the place of ``GET /api/investments/{investId}/sale-events``, which the 2.0
service removed (an HTML 404 [P 2026-10-30], docs/discovery/endpoints.md section 8).
"""

import datetime as dt
from collections.abc import Mapping
from typing import Any

from pydantic import field_validator, model_validator

from deweloperuch_mcp.api.dto.dto import DateText, Dto, Number
from deweloperuch_mcp.models.price_history import (
    EVENT_ARCHIVED,
    EVENT_OFFER,
    EVENT_RESTORED,
    PriceEvent,
)

_EVENT_KINDS = (EVENT_OFFER, EVENT_ARCHIVED, EVENT_RESTORED)
"""Event types by their index in a row: 0 ``OFFER_EVENT``, 1 ``ARCHIVED_EVENT``, 2
``RESTORED_EVENT`` ([P z kodu], module 80026 of the 2.0 client). [P 2026-10-30] the seven
events of offer 33103 decoded so equal those ``/api/sale-events?saleId=33103`` names
(sample ``api.sale_events.v2``): all three types."""

_POSITIONS = ("event_date", "amount", "event_type")
"""What the client reads of a row, by position."""


class PriceEventRowDto(Dto):
    """One row of ``ev``: ``[date "YYYY-MM-DD", amount, event type index, source index]``
    [P 2026-10-30], under the names ``SaleEventDto`` gives the same event of
    ``/api/sale-events``.

    The source is in no output (``get_offer``, which reads ``/api/sale-events``, shows none
    either), so it is not read: of its table ([P z kodu], module 80026: 0 ``ANNOUCMENT_PR``,
    1 ``ANNOUCMENT``, 2 ``ANNOUCMENT_OD``, 3 ``DANEGOVPL``, 4 ``archive_stale_sales``, 5
    ``""``) 2 and 3 were never seen (T68), and a row without a source, or with positions
    after it, has the same event: a new position is ignored like a new field.
    """

    event_date: DateText
    amount: Number | None
    event_type: int
    """An index of ``_EVENT_KINDS``."""

    @model_validator(mode="before")
    @classmethod
    def _positions(cls, row: Any) -> Any:
        if not isinstance(row, list) or len(row) < len(_POSITIONS):
            raise ValueError("oczekiwano tablicy [data, kwota, typ zdarzenia, źródło]")
        return dict(zip(_POSITIONS, row, strict=False))

    @field_validator("event_type", mode="before")
    @classmethod
    def _known_type(cls, value: Any) -> Any:
        """An index of the table, nothing else. Positions carry no names: an index the
        table lacks means the client's table changed, and then the other indexes may mean
        something else too, so the history is off the contract (a changed service), not an
        event of an unknown kind."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"oczekiwano numeru typu zdarzenia, podano {value!r}")
        if not 0 <= value < len(_EVENT_KINDS):
            raise ValueError(f"nieznany numer typu zdarzenia {value}")
        return value

    def to_model(self) -> PriceEvent:
        return PriceEvent(
            date=self._day(self.event_date),
            kind=_EVENT_KINDS[self.event_type],
            price=self._number(self.amount),
        )


class SalePriceEventsDto(Dto):
    """One ``sale`` of the answer, read for its events only."""

    sale_id: int
    ev: list[PriceEventRowDto]
    """Required: every offer of both 2.0 captures has it, with its first price at least
    (127 of 127 [P 2026-10-30], 17 of 17 [P 2026-10-31]). An offer without it is another
    answer (the one before 2.0 had no ``ev``), not an offer without a history."""

    def to_model(self) -> tuple[PriceEvent, ...]:
        """Oldest first. ``ev`` comes so [P 2026-10-30]; the stable sort puts a row out of
        order in its place (``PriceHistory`` refuses events out of order) and keeps the
        service's order of the events of one day (a price, then its withdrawal; a return,
        then the new price). Events without a date (none seen) come first, as in
        ``SaleEventDto.price_events``."""
        ordered = sorted(self.ev, key=lambda row: self._day(row.event_date) or dt.date.min)
        return tuple(row.to_model() for row in ordered)


class InvestmentPriceEventsDto(Dto):
    """The answer of ``map/investments/visible/{slug}`` read for its offers' events."""

    sale: list[SalePriceEventsDto]

    def to_model(self) -> Mapping[int, tuple[PriceEvent, ...]]:
        """Offer id -> its events, oldest first."""
        return {sale.sale_id: sale.to_model() for sale in self.sale}
