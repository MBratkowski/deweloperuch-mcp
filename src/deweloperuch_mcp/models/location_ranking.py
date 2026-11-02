"""``LocationRanking``: cities and powiats ranked by their RCN transactions (D3, D13, D17).

Plain Python. For every city (towns and villages included) the service gives the number
of its transactions and its price per m², area and price; for every powiat it gives the
same on each market (secondary, primary, both) over one 12-month period. The port
``usecases.ports.TransactionRankingSource`` hands them over as ``LocationTransactions``
(the powiats in ``PowiatTransactions``). A ranking keeps the places with at least
``min_transactions`` (when it is not given: 20 for the orders by price,
``PRICE_ORDER_MIN_TRANSACTIONS``, and 0 for the order by transactions), orders them and
cuts the list to ``limit``; the result says how many places there were and whether it is
cut (D4)::

    criteria = RankingCriteria(
        order=RankingOrder.PRICE_PER_M2_DESC, min_transactions=MinTransactions(50)
    )
    ranking = LocationRanking.of(criteria, source.cities())

What the figures mean is known only in part: the service does not say whether its prices
and areas are averages or medians (T10, T85), nor which period the figures of a city
cover; a powiat's cover the 12 months it names [P 2026-11-01]. The model names them after
what they measure, without "average" or "median"; their changes over time are [H] and are
not part of it. The two orders by an indicator's value belong to
``models.indicator_ranking``.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeVar

from deweloperuch_mcp.models.errors import InvalidValueError, OneOf, ValueName, WholeNumber

DEFAULT_RANKING_LIMIT = 20
"""Places a ranking shows unless asked otherwise."""
RANKING_LIMIT_MAX = 100
"""Most places one ranking shows."""
TRANSACTIONS_MAX = 10_000_000
"""Upper bound of ``min_transactions``, far above any place (Warszawa: 386 990 transactions
over the whole register [P 2026-11-01], docs/discovery/endpoints.md, ``map/tx-cities``)."""
# [W] tests/fixtures/api/city_tx_stats_20261015.json [P 2026-10-15]: of 2529 places 1628
# have at most 2 transactions, 258 at least 20 and 108 at least 50, and ranked by the
# price per m² every one of the 100 cheapest has at most 2: a price from a handful of
# transactions is chance, not the price of a place
# (tests/contract/api/dto/test_city_transactions_list_dto.py). 20 is the user's decision
# of 2026-10-15; it leaves out few powiats (31 of 364 on the secondary market, 43 of 310
# on the primary [P 2026-11-02], tests/contract/api/dto/test_powiat_map_stats_dto.py).
PRICE_ORDER_MIN_TRANSACTIONS = 20
"""The fewest transactions of a place ranked by its price when ``min_transactions`` is
not given."""

E = TypeVar("E", bound=StrEnum)


def _member(kind: type[E], name: ValueName, value: object) -> E:
    """``value`` as a member of ``kind``: the member itself or its value (spaces around it
    ignored)."""
    if isinstance(value, kind):
        return value
    if isinstance(value, str) and value.strip() in kind._value2member_map_:
        return kind(value.strip())
    raise InvalidValueError(name, OneOf(tuple(member.value for member in kind)), value)


# --- the places ------------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class LocationTransactions:
    """The transactions of one city or powiat as the service sums them up.

    The prices and the area are the service's figures: averages or medians, it does not
    say which (T10, T85, [H]); the period of a city's figures is not given either.
    """

    name: str
    transaction_count: int
    price_per_m2: float | None = None
    """PLN per m²."""
    area_m2: float | None = None
    price: float | None = None
    """PLN."""
    city_slug: str | None = None
    """The city's slug (level ``city``)."""
    powiat_id: int | None = None
    """The powiat's id in the service (level ``powiat``)."""


class RankingMarket(StrEnum):
    """The market of a powiat's transactions: secondary, primary or both as the service
    counts them together (not the sum of the other two: [P 2026-11-01] equal in 80 of 303
    powiats, T86). Cities have no market."""

    SECONDARY = "secondary"
    PRIMARY = "primary"
    ALL = "all"

    @classmethod
    def parse(cls, value: object) -> "RankingMarket":
        return _member(cls, ValueName.RANKING_MARKET, value)


DEFAULT_RANKING_MARKET = RankingMarket.SECONDARY
"""The market of a powiat ranking unless asked otherwise: the user's decision of
2026-11-01 (the service shows it first in 343 of 380 powiats [P 2026-11-01], and the months
of the transaction statistics are of the secondary market too)."""


@dataclass(frozen=True, kw_only=True)
class TransactionPeriod:
    """The months a powiat's figures cover: from the first day of ``start`` (``2025-11-01``)
    to the end of the month ``end`` (``2026-10``)."""

    start: str
    end: str


@dataclass(frozen=True, kw_only=True)
class PowiatTransactions:
    """The transactions of every powiat on each market over one period.

    ``powiats``: how many powiats the service lists; a powiat without figures for a market
    is not among that market's places (``without``), never one of 0 transactions."""

    period: TransactionPeriod
    powiats: int
    markets: Mapping[RankingMarket, tuple[LocationTransactions, ...]]

    def on(self, market: RankingMarket) -> tuple[LocationTransactions, ...]:
        """The powiats with figures for ``market``."""
        return self.markets.get(market, ())

    def without(self, market: RankingMarket) -> int:
        """How many powiats have no figures for ``market``."""
        return self.powiats - len(self.on(market))


_POLISH_LETTERS = str.maketrans("ąćęłńóśźż", "acelnoszz")


@dataclass(frozen=True)
class PlaceNames:
    """The names of powiats (by their id in the service) and cities (by their slug), with
    what stands for a missing one: ``powiat {id}`` and the slug itself.

    A slug is looked up without regard to case and Polish letters: the service writes one
    city's slug in two cases (``tarnobrzeg`` and ``Tarnobrzeg`` [P 2026-11-01])."""

    powiats: Mapping[int, str]
    cities: Mapping[str, str]
    """By slug in lowercase ASCII (``fold``)."""

    def powiat(self, powiat_id: int) -> str:
        return self.powiats.get(powiat_id) or f"powiat {powiat_id}"

    def city(self, city_slug: str) -> str:
        return self.cities.get(self.fold(city_slug)) or city_slug

    @staticmethod
    def fold(slug: str) -> str:
        """``" ŁÓDŹ "`` -> ``lodz``: trimmed, lowercase, Polish letters as ASCII."""
        return slug.strip().lower().translate(_POLISH_LETTERS)


# --- what is asked for -----------------------------------------------------------------------


class RankingLevel(StrEnum):
    """What is ranked: cities (with towns and villages) or powiats."""

    CITY = "city"
    POWIAT = "powiat"

    @classmethod
    def parse(cls, value: object) -> "RankingLevel":
        return _member(cls, ValueName.RANKING_LEVEL, value)


class RankingOrder(StrEnum):
    """The order of a ranking. By transactions or price, ties go to more transactions, then
    to the name; by an indicator's value (``by_value``, ``models.indicator_ranking``), to
    the name."""

    TRANSACTIONS_DESC = "transactions_desc"
    PRICE_PER_M2_DESC = "price_per_m2_desc"
    PRICE_PER_M2_ASC = "price_per_m2_asc"
    VALUE_DESC = "value_desc"
    VALUE_ASC = "value_asc"

    @classmethod
    def parse(cls, value: object) -> "RankingOrder":
        return _member(cls, ValueName.RANKING_ORDER, value)

    @property
    def by_value(self) -> bool:
        """An order of an indicator's value, not of transactions."""
        return self in (RankingOrder.VALUE_DESC, RankingOrder.VALUE_ASC)

    @property
    def default_min_transactions(self) -> int:
        """The threshold of this order when none is given: ``PRICE_ORDER_MIN_TRANSACTIONS``
        by the price, 0 (every place) by the number of transactions."""
        return 0 if self is RankingOrder.TRANSACTIONS_DESC else PRICE_ORDER_MIN_TRANSACTIONS

    def key(self, place: LocationTransactions) -> tuple[bool, float, int, str]:
        """The sort key of ``place``: by the price per m², places without one come last."""
        ties = (-place.transaction_count, place.name)
        if self is RankingOrder.TRANSACTIONS_DESC:
            return (False, 0.0, *ties)
        price = place.price_per_m2
        if price is None:
            return (True, 0.0, *ties)
        return (False, -price if self is RankingOrder.PRICE_PER_M2_DESC else price, *ties)


@dataclass(frozen=True)
class RankingLimit:
    """How many places a ranking shows: 1..``RANKING_LIMIT_MAX``."""

    value: int = DEFAULT_RANKING_LIMIT

    def __post_init__(self) -> None:
        WholeNumber(1, RANKING_LIMIT_MAX).check(ValueName.RANKING_LIMIT, self.value)

    @classmethod
    def parse(cls, value: object) -> "RankingLimit":
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


@dataclass(frozen=True)
class MinTransactions:
    """The fewest transactions a place needs to be ranked; 0 ranks every place."""

    value: int = 0

    def __post_init__(self) -> None:
        WholeNumber(0, TRANSACTIONS_MAX).check(ValueName.MIN_TRANSACTIONS, self.value)

    @classmethod
    def parse(cls, value: object) -> "MinTransactions | None":
        """``None``: not given (the order's default applies, ``RankingCriteria.threshold``)."""
        return None if value is None else cls(value)  # type: ignore[arg-type]


@dataclass(frozen=True)
class RankingCriteria:
    """What to rank, in which order, how many places and from how many transactions."""

    level: RankingLevel = RankingLevel.CITY
    order: RankingOrder = RankingOrder.TRANSACTIONS_DESC
    limit: RankingLimit = field(default_factory=RankingLimit)
    min_transactions: MinTransactions | None = None
    """The threshold asked for; ``None``: not given."""
    market: RankingMarket | None = None
    """The market asked for (powiats only); ``None``: not given."""

    def __post_init__(self) -> None:
        if self.order.by_value:
            raise ValueError(f"{self.order}: kolejność rankingu wskaźnika (indicator)")
        if self.market is not None and self.level is not RankingLevel.POWIAT:
            raise ValueError(f"market {self.market}: tylko ranking powiatów ma rynki")

    @property
    def powiat_market(self) -> RankingMarket:
        """The market of a powiat ranking: ``market`` when given, else the default."""
        return self.market or DEFAULT_RANKING_MARKET

    @property
    def threshold(self) -> MinTransactions:
        """The fewest transactions of a ranked place: ``min_transactions`` when given (0
        included), else the order's default (``RankingOrder.default_min_transactions``)."""
        if self.min_transactions is not None:
            return self.min_transactions
        return MinTransactions(self.order.default_min_transactions)

    @property
    def threshold_by_default(self) -> bool:
        """Small places are left out by the order's default, not by ``min_transactions``."""
        return self.min_transactions is None and self.threshold.value > 0


# --- the ranking -----------------------------------------------------------------------------


@dataclass(frozen=True)
class LocationRanking:
    """The first places of a ranking and how many there were (D4: the cut is explicit)."""

    criteria: RankingCriteria
    items: tuple[LocationTransactions, ...]
    total: int
    """Places with at least ``criteria.threshold`` transactions, before the cut to
    ``limit``."""
    left_out: int = 0
    """Places with fewer than ``criteria.threshold`` transactions."""

    @classmethod
    def of(
        cls, criteria: RankingCriteria, places: Iterable[LocationTransactions]
    ) -> "LocationRanking":
        least = criteria.threshold.value
        every = tuple(places)
        ranked = sorted(
            (place for place in every if place.transaction_count >= least),
            key=criteria.order.key,
        )
        cut = tuple(ranked[: criteria.limit.value])
        return cls(criteria, cut, len(ranked), left_out=len(every) - len(ranked))

    @property
    def returned(self) -> int:
        return len(self.items)

    @property
    def truncated(self) -> bool:
        """More places meet the criteria than shown."""
        return self.total > self.returned
