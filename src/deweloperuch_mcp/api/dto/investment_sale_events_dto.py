"""``InvestmentSaleEventsDto``: ``GET /api/investments/{investId}/sale-events`` [P], the
price events of every offer of an investment (sample ``api.inv_sale_events``)."""

from collections.abc import Mapping

from pydantic import ConfigDict, RootModel

from deweloperuch_mcp.api.dto.sale_events_dto import SaleEventDto
from deweloperuch_mcp.models.price_history import PriceEvent


class InvestmentSaleEventsDto(RootModel[dict[int, list[SaleEventDto]]]):
    """Offer id -> its events."""

    model_config = ConfigDict(frozen=True)

    def to_model(self) -> Mapping[int, tuple[PriceEvent, ...]]:
        return {
            offer_id: SaleEventDto.price_events(events) for offer_id, events in self.root.items()
        }
