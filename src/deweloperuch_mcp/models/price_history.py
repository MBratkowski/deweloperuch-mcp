"""An offer's price over time (D3): the service's summary, its events and what they say.

- ``PriceEvent``: one entry of the history (a price, a withdrawal, a return);
- ``PriceChange``: a change of price in PLN and percent, with its direction;
- ``PriceHistory``: the summary and, when fetched, the events, oldest first; from them
  ``PriceFlags`` (the lowest recent prices, the changes, a reduction after a recent rise)
  as of a given day.

Value sets the service may extend (event kinds, directions) stay plain strings: unknown
values pass through, so a new one is shown instead of failing.
"""

import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Self

EVENT_OFFER, EVENT_ARCHIVED, EVENT_RESTORED = "offer", "archived", "restored"
"""Kinds of a price event [P]: a price in the list, withdrawn, back in the list."""

INCREASE, DECREASE, NO_CHANGE = "increase", "decrease", "no_change"
"""Directions of the last price change [P]."""


@dataclass(frozen=True, kw_only=True)
class PriceEvent:
    """One entry of an offer's price history."""

    date: dt.date | None
    """``None`` only if the service gave no date."""
    kind: str
    """``offer``, ``archived`` or ``restored``."""
    price: float | None


@dataclass(frozen=True, kw_only=True)
class PriceChange:
    """A change of price: in PLN, in percent of the earlier price, and its direction
    (negative: cheaper)."""

    pln: float | None = None
    percent: float | None = None
    direction: str | None = None
    """``increase``, ``decrease`` or ``no_change``; given for the last change only."""


def _chronological(event: PriceEvent) -> dt.date:
    return event.date or dt.date.min


@dataclass(frozen=True, kw_only=True)
class PricePoint:
    """What an event set on a day: a price (an ``offer`` event, or a ``restored`` one
    with the price the offer came back at), or none (``None``: withdrawn, ``archived``)."""

    date: dt.date
    price: float | None


@dataclass(frozen=True, kw_only=True)
class PriceFlags:
    """What an offer's price history says, as of a day (``PriceHistory.price_flags``).

    The window of the lowest prices ends on that day, or on the day the offer was
    withdrawn if it is archived. Prices are those of ``offer`` and ``restored`` events
    [P 2026-10-09: the price of a return is the offer's current one, sample
    api.sale_events]; a withdrawal ends the price in effect until the next one.
    """

    lowest_price_30d: float | None
    """The lowest price in effect at any moment of the last 30 days of the window, the
    price in effect when it began included; ``None`` without a known price."""
    lowest_price_90d: float | None
    """The same for 90 days."""
    price_changes: int
    """Prices that differ from the one before them."""
    largest_drop_pct: float | None
    """The largest single drop between two prices, in % of the earlier one (positive,
    0.01); ``None`` without any drop."""
    largest_rise_pct: float | None
    """The largest single rise, the same way."""
    suspicious_reduction: bool
    """The latest drop came at most 30 days after a rise and its price is not below the
    lowest price in effect in the 30 days before it (a reduction from a raised price)."""


FLAG_WINDOWS = (30, 90)
"""Days of the windows of ``PriceFlags``' lowest prices."""
RISE_BEFORE_DROP_DAYS = 30
"""How recent a rise makes the next drop suspicious, and how far back its comparison
price goes."""


def _lowest_in_effect(timeline: Sequence[PricePoint], start: dt.date) -> float | None:
    """The lowest price in effect from ``start`` to the end of ``timeline`` (oldest
    first): the one set last before ``start`` (in effect when the day began), unless the
    offer was withdrawn after it, and every one set on ``start`` or later."""
    before = [point for point in timeline if point.date < start]
    prices = [p.price for p in timeline if p.date >= start and p.price is not None]
    if before and before[-1].price is not None:
        prices.append(before[-1].price)
    return min(prices, default=None)


def _percent(earlier: float, later: float) -> float:
    return round(abs(later - earlier) / earlier * 100, 2)


@dataclass(frozen=True, kw_only=True)
class PriceHistory:
    """An offer's price over time: the service's summary and, when fetched, its events.

    ``events`` is ``None`` until they are fetched; then oldest first (events without a
    date, none seen so far, before the rest).
    """

    since_start: PriceChange = field(default_factory=PriceChange)
    """Current price minus the first one seen."""
    last_change: PriceChange = field(default_factory=PriceChange)
    """The latest change (known in search results only)."""
    events_count: int | None = None
    created_on: dt.date | None = None
    last_event_on: dt.date | None = None
    last_changed_on: dt.date | None = None
    events: tuple[PriceEvent, ...] | None = None

    def __post_init__(self) -> None:
        if self.events is not None:
            dates = [_chronological(event) for event in self.events]
            if dates != sorted(dates):
                raise ValueError("zdarzenia historii ceny nie są w kolejności dat")

    def with_events(self, events: Iterable[PriceEvent]) -> Self:
        """This history with its events (oldest first)."""
        return replace(self, events=tuple(events))

    def timeline(self) -> tuple[PricePoint, ...]:
        """Prices set and withdrawals over time, oldest first: ``offer`` and ``restored``
        events with a date and a price, ``archived`` events with a date (``None``).
        Empty before the events are fetched."""
        found = []
        for event in self.events or ():
            if event.date is None:
                continue
            if event.kind in (EVENT_OFFER, EVENT_RESTORED) and event.price is not None:
                found.append(PricePoint(date=event.date, price=event.price))
            elif event.kind == EVENT_ARCHIVED:
                found.append(PricePoint(date=event.date, price=None))
        return tuple(found)

    def price_points(self) -> tuple[PricePoint, ...]:
        """The prices of ``timeline``, without the withdrawals."""
        return tuple(point for point in self.timeline() if point.price is not None)

    def window_end(self, as_of: dt.date, *, archived: bool) -> dt.date:
        """``as_of``; for an archived offer the day it was last withdrawn, if earlier."""
        if archived:
            withdrawn = [e.date for e in self.events or () if e.kind == EVENT_ARCHIVED and e.date]
            if withdrawn:
                return min(withdrawn[-1], as_of)
        return as_of

    def lowest_price(self, days: int, end: dt.date) -> float | None:
        """The lowest price in effect at any moment from ``end`` minus ``days`` to
        ``end``, the price in effect at the start included; ``None`` without a price."""
        timeline = [point for point in self.timeline() if point.date <= end]
        return _lowest_in_effect(timeline, end - dt.timedelta(days=days))

    def price_flags(self, as_of: dt.date, *, archived: bool = False) -> PriceFlags | None:
        """``PriceFlags`` as of ``as_of`` (for an archived offer, as of its withdrawal);
        ``None`` until the events are fetched."""
        if self.events is None:
            return None
        end = self.window_end(as_of, archived=archived)
        timeline = [point for point in self.timeline() if point.date <= end]
        steps = _steps(timeline)
        changes = [step for step in steps if step.before != step.after]
        drops = [step.percent for step in changes if step.after < step.before and step.before]
        rises = [step.percent for step in changes if step.after > step.before and step.before]
        return PriceFlags(
            lowest_price_30d=self.lowest_price(FLAG_WINDOWS[0], end),
            lowest_price_90d=self.lowest_price(FLAG_WINDOWS[1], end),
            price_changes=len(changes),
            largest_drop_pct=max(drops, default=None),
            largest_rise_pct=max(rises, default=None),
            suspicious_reduction=_suspicious_reduction(timeline, steps),
        )


@dataclass(frozen=True)
class _Step:
    """Two consecutive prices of a timeline (a withdrawal between them or not)."""

    before: float
    after: float
    date: dt.date
    """When ``after`` was set."""
    index: int
    """Of ``after`` in the timeline."""

    @property
    def percent(self) -> float:
        return _percent(self.before, self.after)


def _steps(timeline: Sequence[PricePoint]) -> list[_Step]:
    priced = [(i, p.date, p.price) for i, p in enumerate(timeline) if p.price is not None]
    return [
        _Step(before=a[2], after=b[2], date=b[1], index=b[0])
        for a, b in zip(priced, priced[1:], strict=False)
    ]


def _suspicious_reduction(timeline: Sequence[PricePoint], steps: Sequence[_Step]) -> bool:
    """The latest drop came at most ``RISE_BEFORE_DROP_DAYS`` after a rise, and its price
    is not below the lowest price in effect in the ``RISE_BEFORE_DROP_DAYS`` before it."""
    if len(steps) < 2:  # fewer than three prices
        return False
    drops = [step for step in steps if step.after < step.before]
    if not drops:
        return False
    drop = drops[-1]
    recent = drop.date - dt.timedelta(days=RISE_BEFORE_DROP_DAYS)
    rose = any(
        step.after > step.before and step.date >= recent and step.index < drop.index
        for step in steps
    )
    lowest = _lowest_in_effect(timeline[: drop.index], recent)
    return rose and lowest is not None and drop.after >= lowest
