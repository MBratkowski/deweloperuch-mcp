"""Tests of ``deweloperuch_mcp.api.dto.sale_events_dto``."""

import datetime as dt

import pytest

from deweloperuch_mcp.api.dto import sale_events_dto
from deweloperuch_mcp.api.dto.sale_events_dto import SaleEventDto
from deweloperuch_mcp.models.price_history import PriceEvent


def event(
    event_id: int, kind: str, amount: int | float | str | None, when: str
) -> sale_events_dto.SaleEventDto:
    return sale_events_dto.SaleEventDto(
        sale_event_id=event_id, event_type=kind, amount=amount, event_date=when, source=""
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("OFFER_EVENT", "offer"),
        ("ARCHIVED_EVENT", "archived"),
        ("RESTORED_EVENT", "restored"),
        ("PRICE_CHANGE_EVENT", "price_change"),
    ],
)
def test_event_kind(value: str, expected: str) -> None:
    assert SaleEventDto._kind(value) == expected


def test_price_events_are_chronological_with_domain_kinds() -> None:
    events = [
        event(510028, "ARCHIVED_EVENT", "1620000", "2025-02-25T00:00:00.000Z"),
        event(841366, "RESTORED_EVENT", "1620175", "2026-10-03T00:00:00.000Z"),
        event(145581, "OFFER_EVENT", "1620000", "2025-02-25T00:00:00.000Z"),
        event(900000, "OFFER_EVENT", "", "2026-10-04"),
        event(950000, "SOMETHING_NEW", 1, ""),
    ]

    assert SaleEventDto.price_events(events) == (
        PriceEvent(date=None, kind="something_new", price=1.0),
        PriceEvent(date=dt.date(2025, 2, 25), kind="offer", price=1620000.0),
        PriceEvent(date=dt.date(2025, 2, 25), kind="archived", price=1620000.0),
        PriceEvent(date=dt.date(2026, 10, 3), kind="restored", price=1620175.0),
        PriceEvent(date=dt.date(2026, 10, 4), kind="offer", price=None),
    )
