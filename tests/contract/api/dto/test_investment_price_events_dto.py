"""Contract of ``deweloperuch_mcp.api.dto.investment_price_events_dto`` with the service's
real answers (the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).

The 2.0 answer of ``map/investments/visible/{slug}`` carries every offer's price events in
``ev``, rows ``[date, amount, event type index, source index]`` [P 2026-10-30,
docs/discovery/endpoints.md]. The client reads the first three positions of a row.
"""

import datetime as dt

from deweloperuch_mcp.api.dto import investment_dto
from deweloperuch_mcp.api.dto.investment_price_events_dto import InvestmentPriceEventsDto
from deweloperuch_mcp.api.dto.sale_events_dto import SaleEventDto, SaleEventsDto
from deweloperuch_mcp.models.price_history import PriceEvent
from support.providers.routes.investments import smolna_with_events
from support.providers.samples import body

DAY = dt.date


def test_the_2_0_answer_has_the_events_of_every_offer() -> None:
    """tests/fixtures/api/README.md: 17 offers (4 active), 38 events, 1 to 5 per offer."""
    parsed = InvestmentPriceEventsDto.model_validate(smolna_with_events())

    assert len(parsed.sale) == 17
    assert sum(len(sale.ev) for sale in parsed.sale) == 38
    assert {len(sale.ev) for sale in parsed.sale} == {1, 2, 5}


def test_rows_keep_their_values_as_sent() -> None:
    """Dates ``YYYY-MM-DD``, amounts whole numbers, type indexes 0 to 2: what the client
    reads of each row, 1:1 with the service."""
    parsed = InvestmentPriceEventsDto.model_validate(smolna_with_events())
    rows = [row for sale in parsed.sale for row in sale.ev]

    assert all(DAY.fromisoformat(row.event_date) for row in rows)
    assert all(isinstance(row.amount, int) for row in rows)
    assert {row.event_type for row in rows} == {0, 1, 2}


def test_the_fourth_position_is_a_source_the_client_does_not_read() -> None:
    """The capture has sources 0, 1 and 5 (``ANNOUCMENT_PR``, ``ANNOUCMENT``, ``""``):
    present in every row, never part of an event (neither tool shows a source)."""
    answer = smolna_with_events()
    rows = [row for sale in answer["sale"] for row in sale["ev"]]

    assert {len(row) for row in rows} == {4}
    assert {row[3] for row in rows} == {0, 1, 5}


def test_an_offer_restored_after_its_withdrawal() -> None:
    """Offer 2377 (C224): its first price and withdrawal on one day, the return and a new
    price on 2026-10-03, a rise on 2026-10-24."""
    events = InvestmentPriceEventsDto.model_validate(smolna_with_events()).to_model()

    assert events[2377] == (
        PriceEvent(date=DAY(2025, 2, 25), kind="offer", price=1_620_000.0),
        PriceEvent(date=DAY(2025, 2, 25), kind="archived", price=1_620_000.0),
        PriceEvent(date=DAY(2026, 10, 3), kind="restored", price=1_620_175.0),
        PriceEvent(date=DAY(2026, 10, 3), kind="offer", price=1_620_175.0),
        PriceEvent(date=DAY(2026, 10, 24), kind="offer", price=1_620_768.0),
    )
    assert events[206523] == (PriceEvent(date=DAY(2026, 10, 24), kind="offer", price=3_735_107.0),)


def test_events_are_oldest_first_in_the_service_order() -> None:
    answer = smolna_with_events()
    events = InvestmentPriceEventsDto.model_validate(answer).to_model()

    for sale in answer["sale"]:
        dates = [row[0] for row in sale["ev"]]
        assert dates == sorted(dates)  # as sent: ascending [P 2026-10-30]
        assert [e.date for e in events[sale["sale_id"]]] == [DAY.fromisoformat(d) for d in dates]


def test_the_events_agree_with_the_offers_of_the_same_answer() -> None:
    """[P 2026-10-30] across 127 offers, and here across 17: the first event is the first
    price (the price minus its change since the start), the last one the current price;
    an active offer ends with a price, an archived one with its withdrawal."""
    answer = smolna_with_events()
    offers = investment_dto.InvestmentDto.model_validate(answer).to_model().offers
    events = InvestmentPriceEventsDto.model_validate(answer).to_model()

    assert {offer.offer_id for offer in offers} == set(events)
    for offer in offers:
        history, since_start = events[offer.offer_id], offer.history.since_start.pln
        assert offer.price is not None and since_start is not None
        assert history[0].price == offer.price - since_start, offer.offer_id
        assert history[-1].price == offer.price, offer.offer_id
        assert history[-1].kind == ("offer" if offer.active else "archived"), offer.offer_id


def test_withdrawals_and_returns_are_the_events_the_service_names() -> None:
    """[P 2026-10-09] the named events of offers 2377 (``/api/sale-events``) and 2377, 2386
    and 2373 (the investment's route before 2.0), sorted as ``get_offer`` sorts them, are
    the start of their ``ev`` of 2026-10-31 (the samples keep three; events are only added
    later). They cover types 0, 1 and 2: offer, withdrawal and return."""
    events = InvestmentPriceEventsDto.model_validate(smolna_with_events()).to_model()
    by_investment = body("api.inv_sale_events")
    named = [
        (2377, body("api.sale_events")["events"]),
        (2377, by_investment["2377"]),
        (2386, by_investment["2386"]),
        (2373, by_investment["2373"]),
    ]

    kinds = set()
    for offer_id, rows in named:
        expected = SaleEventDto.price_events([SaleEventDto.model_validate(row) for row in rows])
        assert events[offer_id][: len(expected)] == expected, offer_id
        kinds |= {event.kind for event in expected}
    assert kinds == {"offer", "archived", "restored"}


def test_an_offer_has_the_events_sale_events_gives_for_it() -> None:
    """[P 2026-10-30] offer 33103 of ``nowy-czechow``: the events of the investment's
    answer equal those of ``/api/sale-events?saleId=33103`` (``get_offer``'s history), event
    for event; both samples keep the first three of seven."""
    answer = body("api.map_inv_visible.v2")
    sample = next(sale for sale in answer["sale"] if sale["sale_id"] == 33103)
    events = InvestmentPriceEventsDto.model_validate({"sale": [sample]}).to_model()[33103]
    named = SaleEventsDto.model_validate(body("api.sale_events.v2")).events

    assert events == SaleEventDto.price_events(named)
    assert [event.kind for event in events] == ["offer", "offer", "offer"]
