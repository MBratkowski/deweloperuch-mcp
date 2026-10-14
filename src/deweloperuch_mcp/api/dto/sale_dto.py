"""``SaleDto``: what the two DTOs of an offer (the backend's ``sale``) share, an investment's
offer (``InvestmentSaleDto``) and an item of the offers list (``SaleListItemDto``)."""

from deweloperuch_mcp.api.dto.dto import DateText, Dto, Number
from deweloperuch_mcp.models.offer import Offer
from deweloperuch_mcp.models.price_history import PriceChange, PriceHistory


class SaleDto(Dto):
    """The fields of a ``sale`` both DTOs have, and its offer and price summary for the
    subclasses' ``to_model()``."""

    sale_id: int
    name: str
    status: str
    amount: Number | None
    currency: str | None = None
    size: Number | None
    start_amount_difference: Number | None = None
    start_amount_difference_percent: Number | None = None
    last_event_date: DateText | None = None
    last_change_event_date: DateText | None = None
    creation_date: DateText | None = None

    def _offer(self, history: PriceHistory) -> Offer:
        return Offer(
            offer_id=self.sale_id,
            name=self.name,
            status=self.status,
            price=self._number(self.amount),
            currency=self._text(self.currency),
            area_m2=self._number(self.size),
            history=history,
        )

    def _history(self) -> PriceHistory:
        return PriceHistory(
            since_start=PriceChange(
                pln=self._number(self.start_amount_difference),
                percent=self._number(self.start_amount_difference_percent),
            ),
            created_on=self._day(self.creation_date),
            last_event_on=self._day(self.last_event_date),
            last_changed_on=self._day(self.last_change_event_date),
        )
