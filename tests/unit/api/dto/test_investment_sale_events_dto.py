"""Tests of ``deweloperuch_mcp.api.dto.investment_sale_events_dto``."""

import datetime as dt

from deweloperuch_mcp.api.dto.investment_sale_events_dto import InvestmentSaleEventsDto
from deweloperuch_mcp.api.dto.sale_events_dto import SaleEventDto
from deweloperuch_mcp.models.price_history import PriceEvent
from support.providers.samples import body


def test_the_events_of_an_investment_by_offer() -> None:
    events = InvestmentSaleEventsDto.model_validate(body("api.inv_sale_events")).root

    by_offer = {offer_id: SaleEventDto.price_events(items) for offer_id, items in events.items()}

    assert by_offer[206087] == (
        PriceEvent(date=dt.date(2026, 10, 3), kind="offer", price=1679796.0),
    )
    assert [e.kind for e in by_offer[2377]] == ["offer", "archived", "restored"]
