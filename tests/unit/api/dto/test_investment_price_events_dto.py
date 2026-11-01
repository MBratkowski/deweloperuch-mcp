"""Tests of ``deweloperuch_mcp.api.dto.investment_price_events_dto``.

Rows are copies of real rows of tests/fixtures/api/map_inv_visible_smolna_20261031.json
(offer 2377), changed only where a test checks a shape.
"""

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.investment_price_events_dto import (
    InvestmentPriceEventsDto,
    PriceEventRowDto,
)
from deweloperuch_mcp.errors import UnexpectedResponseError
from deweloperuch_mcp.models.price_history import PriceEvent
from support.providers.routes.investments import smolna_with_events

DAY = dt.date
FIRST_PRICE = ["2025-02-25", 1620000, 0, 1]
WITHDRAWAL = ["2025-02-25", 1620000, 1, 5]
RETURN = ["2026-10-03", 1620175, 2, 0]
NEW_PRICE = ["2026-10-24", 1620768, 0, 0]


def answer_with(*rows: Any, **changes: Any) -> dict[str, Any]:
    """The answer for ``smolna`` with one offer, 2377, whose ``ev`` is ``rows``."""
    data: dict[str, Any] = smolna_with_events()
    sale = next(s for s in data["sale"] if s["sale_id"] == 2377)
    data["sale"] = [dict(sale, ev=list(rows), **changes)]
    return data


def events_of(*rows: Any) -> tuple[PriceEvent, ...]:
    return InvestmentPriceEventsDto.model_validate(answer_with(*rows)).to_model()[2377]


@pytest.mark.parametrize(
    ("row", "kind"),
    [(FIRST_PRICE, "offer"), (WITHDRAWAL, "archived"), (RETURN, "restored")],
)
def test_event_types_by_their_index(row: list[Any], kind: str) -> None:
    """0 ``OFFER_EVENT``, 1 ``ARCHIVED_EVENT``, 2 ``RESTORED_EVENT`` ([P z kodu],
    [P 2026-10-30])."""
    (event,) = events_of(row)

    assert event == PriceEvent(date=DAY.fromisoformat(row[0]), kind=kind, price=float(row[1]))


@pytest.mark.parametrize("index", [3, -1, True, 1.5, "offer", None])
def test_an_event_type_outside_the_table_is_no_event(index: object) -> None:
    """Positions carry no names: an index the table lacks means the table changed, and the
    other indexes may mean something else now. The history is off the contract."""
    with pytest.raises(ValidationError, match="event_type"):
        events_of(FIRST_PRICE, ["2026-10-03", 1620175, index, 0])


def test_an_event_type_outside_the_table_is_a_changed_service() -> None:
    data = answer_with(FIRST_PRICE, ["2026-10-03", 1620175, 3, 0])

    with pytest.raises(UnexpectedResponseError, match="nie pasują do kontraktu") as caught:
        Dto.validated(InvestmentPriceEventsDto, data, "/api/map/investments/visible/smolna")

    assert caught.value.detail is not None
    assert caught.value.detail.startswith("/api/map/investments/visible/smolna: sale.0.ev.1")


@pytest.mark.parametrize("source", [0, 1, 2, 3, 4, 5, 6, "", None, "ANNOUCMENT"])
def test_the_source_is_not_read(source: object) -> None:
    """The fourth position, the source, is in no output (neither is it in ``get_offer``'s):
    sources 2 ``ANNOUCMENT_OD`` and 3 ``DANEGOVPL``, known only from the client's code
    ([P z kodu], T68), and any other value give the same event."""
    assert events_of(["2025-02-25", 1620000, 0, source]) == events_of(FIRST_PRICE)


def test_positions_after_the_source_are_ignored() -> None:
    """A position the service may add later is ignored, like a new field of an object."""
    assert events_of([*FIRST_PRICE, 145581, "x"]) == events_of(FIRST_PRICE)


def test_a_row_without_its_source_still_has_its_event() -> None:
    """The client reads the date, the amount and the type; the source may be missing (as
    in the trimmed samples)."""
    assert events_of(FIRST_PRICE[:3]) == events_of(FIRST_PRICE)


@pytest.mark.parametrize(
    "row",
    [
        FIRST_PRICE[:2],
        [],
        "2025-02-25",
        {"date": "2025-02-25", "amount": 1620000, "type": 0},
        ["25.02.2025", 1620000, 0, 1],
        ["2025-02-25", "abc", 0, 1],
        None,
    ],
)
def test_a_row_of_another_shape_is_off_the_contract(row: object) -> None:
    with pytest.raises(ValidationError):
        events_of(row)


def test_an_offer_without_events_is_off_the_contract() -> None:
    """Every offer of both 2.0 captures has ``ev``, with its first price at least (127 of
    127, 17 of 17): an offer without it is no offer without a history, but another answer
    (the one before 2.0 had no ``ev`` at all)."""
    data = answer_with(FIRST_PRICE)
    del data["sale"][0]["ev"]

    with pytest.raises(ValidationError, match="ev"):
        InvestmentPriceEventsDto.model_validate(data)


def test_events_null_are_off_the_contract() -> None:
    """``null`` is no list of events: as off the contract as no ``ev`` at all."""
    data = answer_with(FIRST_PRICE)
    data["sale"][0]["ev"] = None

    with pytest.raises(ValidationError, match="ev"):
        InvestmentPriceEventsDto.model_validate(data)


def test_an_amount_null_is_an_event_without_a_price() -> None:
    """As ``SaleEventDto`` reads ``/api/sale-events``: the event stays, without a price."""
    assert events_of(["2025-02-25", None, 1, 5]) == (
        PriceEvent(date=DAY(2025, 2, 25), kind="archived", price=None),
    )


def test_an_empty_list_of_events_is_an_empty_history() -> None:
    """Not seen, but well formed: no events, as ``sale-events`` gives none for an offer."""
    assert events_of() == ()


def test_amounts_and_dates_are_read_as_the_other_events_are() -> None:
    """Amounts as numbers or numeric text, ``""`` for none; ``YYYY-MM-DD`` or an ISO
    datetime, ``""`` for no date (``SaleEventDto`` reads ``/api/sale-events`` so)."""
    assert events_of(["2025-02-25T00:00:00.000Z", "1620000", 0, 1], ["", "", 0, 1]) == (
        PriceEvent(date=None, kind="offer", price=None),
        PriceEvent(date=DAY(2025, 2, 25), kind="offer", price=1_620_000.0),
    )


def test_events_keep_the_service_order_within_a_day() -> None:
    """``ev`` comes oldest first [P 2026-10-30]; a row out of order is put in its place by
    date, and events of one day keep the order the service sent them in (a price, then
    the withdrawal; a return, then the new price)."""
    assert [e.kind for e in events_of(NEW_PRICE, FIRST_PRICE, WITHDRAWAL, RETURN)] == [
        "offer",
        "archived",
        "restored",
        "offer",
    ]
    assert [e.kind for e in events_of(WITHDRAWAL, FIRST_PRICE)] == ["archived", "offer"]


def test_events_are_keyed_by_their_offer() -> None:
    events = InvestmentPriceEventsDto.model_validate(smolna_with_events()).to_model()

    assert len(events) == 17
    assert events[2382] == (
        PriceEvent(date=DAY(2025, 2, 25), kind="offer", price=2_600_000.0),
        PriceEvent(date=DAY(2025, 2, 25), kind="archived", price=2_600_000.0),
    )


def test_a_row_is_immutable() -> None:
    row = PriceEventRowDto.model_validate(FIRST_PRICE)

    with pytest.raises(ValidationError):
        row.event_type = 1
