"""Tests of ``deweloperuch_mcp.models.price_history``."""

import datetime as dt

import pytest

from deweloperuch_mcp.api.dto import investment_dto, sale_events_dto
from deweloperuch_mcp.api.dto.investment_sale_events_dto import InvestmentSaleEventsDto
from deweloperuch_mcp.api.dto.sale_events_dto import SaleEventDto
from deweloperuch_mcp.models.offer import (
    Offer,
)
from deweloperuch_mcp.models.price_history import PriceEvent, PriceFlags, PriceHistory
from support.providers.samples import body

DAY = dt.date


def history(*events: tuple[str, str, float | None]) -> PriceHistory:
    """Events ``(date, kind, price)``, oldest first."""
    return PriceHistory().with_events(
        PriceEvent(date=DAY.fromisoformat(day), kind=kind, price=price)
        for day, kind, price in events
    )


def prices(*points: tuple[str, float]) -> PriceHistory:
    return history(*((day, "offer", price) for day, price in points))


def offer_4397() -> PriceHistory:
    """[P 2026-10-10] 1 000 000 (2025-02-25), 994 006 (2025-09-11), 927 706 (2025-12-09)."""
    events = sale_events_dto.SaleEventsDto.model_validate(
        body("api.sale_events.price_history")
    ).events
    return PriceHistory().with_events(SaleEventDto.price_events(events))


def offer_2377() -> PriceHistory:
    """[P 2026-10-09] sample api.sale_events (first 3 of 4 events): 1 620 000 and its
    withdrawal on 2025-02-25, the return at 1 620 175 (the current price) on 2026-10-03."""
    events = sale_events_dto.SaleEventsDto.model_validate(body("api.sale_events")).events
    return PriceHistory().with_events(SaleEventDto.price_events(events))


def active_offers_with_history() -> list[tuple[int, float, PriceHistory]]:
    """Every active offer of the sample investment with its history and current price."""
    investment = investment_dto.InvestmentDto.model_validate(body("api.map_inv_visible")).to_model()
    histories = InvestmentSaleEventsDto.model_validate(body("api.inv_sale_events")).root
    found = []
    for offer in investment.offers:
        if offer.active and offer.price is not None and offer.offer_id in histories:
            events = SaleEventDto.price_events(histories[offer.offer_id])
            found.append((offer.offer_id, offer.price, PriceHistory().with_events(events)))
    return found


def test_the_flags_of_a_real_history() -> None:
    flags = offer_4397().price_flags(DAY(2026, 10, 13))

    assert flags == PriceFlags(
        lowest_price_30d=927_706.0,
        lowest_price_90d=927_706.0,
        price_changes=2,
        largest_drop_pct=6.67,  # 994 006 -> 927 706
        largest_rise_pct=None,
        suspicious_reduction=False,
    )


def test_the_windows_reach_back_to_the_price_in_effect_when_they_began() -> None:
    """2025-12-20: the 30 days began on 2025-11-20 at 994 006, the 90 days on 2025-09-21
    at 994 006 too; both include the drop to 927 706 of 2025-12-09."""
    real = offer_4397()

    assert real.lowest_price(30, DAY(2025, 12, 20)) == 927_706.0
    assert real.lowest_price(30, DAY(2025, 12, 1)) == 994_006.0
    assert real.lowest_price(90, DAY(2025, 9, 20)) == 994_006.0
    assert real.lowest_price(5, DAY(2025, 9, 10)) == 1_000_000.0
    assert real.lowest_price(30, DAY(2025, 2, 24)) is None  # before the first price


def test_a_return_sets_a_price_and_a_withdrawal_ends_the_one_before() -> None:
    """The price before the withdrawal is not in effect while the offer is withdrawn, so
    it is not carried into a window that begins after the withdrawal."""
    flags = offer_2377().price_flags(DAY(2026, 10, 13))

    assert flags == PriceFlags(
        lowest_price_30d=1_620_175.0,
        lowest_price_90d=1_620_175.0,
        price_changes=1,
        largest_drop_pct=None,
        largest_rise_pct=0.01,
        suspicious_reduction=False,
    )
    assert offer_2377().lowest_price(30, DAY(2026, 10, 2)) is None  # withdrawn all along


def test_the_timeline_holds_prices_and_withdrawals() -> None:
    mixed = history(
        ("2025-02-25", "offer", 100.0),
        ("2025-02-25", "archived", 100.0),
        ("2026-10-03", "restored", 90.0),
        ("2026-10-04", "offer", None),  # a price event without a price: unknown, skipped
    )

    assert [(p.date, p.price) for p in mixed.timeline()] == [
        (DAY(2025, 2, 25), 100.0),
        (DAY(2025, 2, 25), None),
        (DAY(2026, 10, 3), 90.0),
    ]
    assert [p.price for p in mixed.price_points()] == [100.0, 90.0]
    assert mixed.price_flags(DAY(2026, 10, 13)) == PriceFlags(
        lowest_price_30d=90.0,
        lowest_price_90d=90.0,
        price_changes=1,
        largest_drop_pct=10.0,
        largest_rise_pct=None,
        suspicious_reduction=False,
    )


def test_a_withdrawal_inside_the_window_keeps_the_price_before_it() -> None:
    """Withdrawn on day 20 of the window: the price before it was in effect until then."""
    gap = history(
        ("2026-01-01", "offer", 100.0),
        ("2026-09-30", "archived", 100.0),
        ("2026-10-05", "restored", 120.0),
    )

    assert gap.lowest_price(30, DAY(2026, 10, 13)) == 100.0


@pytest.mark.parametrize(
    ("offer_id", "price", "past"),
    [
        *active_offers_with_history(),
        (2377, 1_620_175.0, offer_2377()),
        (4397, 994_012.0, offer_4397()),
    ],
)
def test_the_lowest_price_of_an_active_offer_is_not_above_its_current_one(
    offer_id: int, price: float, past: PriceHistory
) -> None:
    flags = past.price_flags(DAY(2026, 10, 13))

    assert flags is not None
    for lowest in (flags.lowest_price_30d, flags.lowest_price_90d):
        assert lowest is None or lowest <= price, (offer_id, lowest, price)


def test_no_flags_before_the_events_are_fetched() -> None:
    assert PriceHistory().price_flags(DAY(2026, 10, 13)) is None
    assert PriceHistory().with_events(()).price_flags(DAY(2026, 10, 13)) == PriceFlags(
        lowest_price_30d=None,
        lowest_price_90d=None,
        price_changes=0,
        largest_drop_pct=None,
        largest_rise_pct=None,
        suspicious_reduction=False,
    )


def test_an_archived_offer_is_judged_as_of_its_withdrawal() -> None:
    withdrawn = history(
        ("2026-01-01", "offer", 100.0),
        ("2026-03-01", "offer", 80.0),
        ("2026-03-10", "archived", 80.0),
    )
    offer = Offer(
        offer_id=1, name="M1", status="archived", price=80.0, area_m2=1.0, history=withdrawn
    )

    flags = offer.price_flags(DAY(2026, 10, 13))

    assert flags is not None
    # As of 2026-03-10: the 30 days began at 100 (2026-02-08) and saw 80.
    assert (flags.lowest_price_30d, flags.lowest_price_90d) == (80.0, 80.0)
    assert withdrawn.window_end(DAY(2026, 10, 13), archived=True) == DAY(2026, 3, 10)
    # As of today an active offer's 30 days would hold only 80 too; 90 days: 80.
    assert withdrawn.window_end(DAY(2026, 10, 13), archived=False) == DAY(2026, 10, 13)


def test_an_archived_offer_without_a_withdrawal_event_ends_as_of_the_day() -> None:
    assert prices(("2026-01-01", 1.0)).window_end(DAY(2026, 2, 1), archived=True) == DAY(2026, 2, 1)


def test_the_last_withdrawal_counts_and_never_after_the_day() -> None:
    twice = history(
        ("2026-01-01", "offer", 1.0),
        ("2026-02-01", "archived", 1.0),
        ("2026-03-01", "restored", 1.0),
        ("2026-04-01", "archived", 1.0),
    )

    assert twice.window_end(DAY(2026, 10, 1), archived=True) == DAY(2026, 4, 1)
    assert twice.window_end(DAY(2026, 3, 15), archived=True) == DAY(2026, 3, 15)


def test_changes_count_only_different_prices_and_measure_each_step() -> None:
    steps = prices(
        ("2026-01-01", 100.0),
        ("2026-01-02", 100.0),  # the same price again: no change
        ("2026-01-03", 110.0),  # +10%
        ("2026-01-04", 99.0),  # -10%
        ("2026-01-05", 74.25),  # -25%
    )

    flags = steps.price_flags(DAY(2026, 1, 5))

    assert flags is not None
    assert flags.price_changes == 3
    assert (flags.largest_drop_pct, flags.largest_rise_pct) == (25.0, 10.0)


def test_prices_after_the_day_are_not_known_yet() -> None:
    later = prices(("2026-01-01", 100.0), ("2026-06-01", 50.0))

    flags = later.price_flags(DAY(2026, 3, 1))

    assert flags is not None
    assert (flags.lowest_price_30d, flags.price_changes, flags.largest_drop_pct) == (
        100.0,
        0,
        None,
    )


@pytest.mark.parametrize(
    ("points", "suspicious"),
    [
        # Raised, then "reduced" 10 days later to a price above the one before the rise.
        ([("2026-01-01", 100.0), ("2026-03-01", 120.0), ("2026-03-11", 105.0)], True),
        # The same reduction to exactly the earlier lowest price: not lower, still flagged.
        ([("2026-01-01", 100.0), ("2026-03-01", 120.0), ("2026-03-11", 100.0)], True),
        # Reduced below the lowest of the 30 days before: a real reduction.
        ([("2026-01-01", 100.0), ("2026-03-01", 120.0), ("2026-03-11", 99.0)], False),
        # The rise was 31 days before the drop.
        ([("2026-01-01", 100.0), ("2026-03-01", 120.0), ("2026-04-01", 105.0)], False),
        # The rise exactly 30 days before the drop counts.
        ([("2026-01-01", 100.0), ("2026-03-01", 120.0), ("2026-03-31", 105.0)], True),
        # Only drops.
        ([("2026-01-01", 120.0), ("2026-03-01", 110.0), ("2026-03-11", 105.0)], False),
        # The latest change is a rise: the latest drop (earlier) is judged.
        (
            [
                ("2026-01-01", 100.0),
                ("2026-03-01", 120.0),
                ("2026-03-11", 105.0),
                ("2026-05-01", 130.0),
            ],
            True,
        ),
        # Fewer than three prices.
        ([("2026-03-01", 120.0), ("2026-03-11", 105.0)], False),
    ],
)
def test_a_reduction_right_after_a_rise_is_suspicious(
    points: list[tuple[str, float]], suspicious: bool
) -> None:
    flags = prices(*points).price_flags(DAY(2026, 10, 13))

    assert flags is not None
    assert flags.suspicious_reduction is suspicious


def test_the_comparison_price_is_the_one_in_effect_30_days_before_the_drop() -> None:
    """A low price 40 days before the drop was replaced 35 days before it: the 30 days
    before the drop began at 110, so 105 is lower than any price then."""
    flagged = prices(
        ("2026-01-01", 90.0),
        ("2026-02-04", 110.0),
        ("2026-02-28", 120.0),
        ("2026-03-11", 105.0),
    )

    flags = flagged.price_flags(DAY(2026, 10, 13))

    assert flags is not None
    assert flags.suspicious_reduction is False


def test_events_without_a_date_come_first() -> None:
    first = PriceEvent(date=None, kind="offer", price=None)
    later = PriceEvent(date=dt.date(2025, 1, 1), kind="offer", price=None)

    assert PriceHistory(events=(first, later)).events == (first, later)
    with pytest.raises(ValueError):
        PriceHistory(events=(later, first))
