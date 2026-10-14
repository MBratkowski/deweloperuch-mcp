"""``LocationRanking``: cities and powiats ranked by their RCN transactions (D3, D13, D17).

Plain Python. For every city (towns and villages included) and every powiat the service
gives the number of its transactions and its price per m², area and price; the port
``usecases.ports.TransactionRankingSource`` hands them over as ``LocationTransactions``. A
ranking keeps the places with at least ``min_transactions``, orders them and cuts the
list to ``limit``; the result says how many places there were and whether it is cut
(D4)::

    criteria = RankingCriteria(
        order=RankingOrder.PRICE_PER_M2_DESC, min_transactions=MinTransactions(50)
    )
    ranking = LocationRanking.of(criteria, source.locations(criteria.level))

What the figures mean is known only in part (docs/open-questions.md, T10): the service
does not say which period they cover (it differs between the levels: a city counts far
fewer transactions than its powiat) nor whether its averages are medians. The model
names them after what they measure, without "average" or "median"; their changes over
time are [H] and are not part of it.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeVar

from deweloperuch_mcp.models.errors import InvalidValueError, OneOf, ValueName, WholeNumber

DEFAULT_RANKING_LIMIT = 20
"""Places a ranking shows unless asked otherwise."""
RANKING_LIMIT_MAX = 100
"""Most places one ranking shows."""
TRANSACTIONS_MAX = 10_000_000
"""Upper bound of ``min_transactions``, far above any place (powiat Warszawa: 351 314
transactions [P 2026-10-09], sample ``api.powiat_stats``)."""

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
    say which (T10, [H]); the period they cover is not given either.
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


# --- what is asked for -----------------------------------------------------------------------


class RankingLevel(StrEnum):
    """What is ranked: cities (with towns and villages) or powiats."""

    CITY = "city"
    POWIAT = "powiat"

    @classmethod
    def parse(cls, value: object) -> "RankingLevel":
        return _member(cls, ValueName.RANKING_LEVEL, value)


class RankingOrder(StrEnum):
    """The order of a ranking; ties go to more transactions, then to the name."""

    TRANSACTIONS_DESC = "transactions_desc"
    PRICE_PER_M2_DESC = "price_per_m2_desc"
    PRICE_PER_M2_ASC = "price_per_m2_asc"

    @classmethod
    def parse(cls, value: object) -> "RankingOrder":
        return _member(cls, ValueName.RANKING_ORDER, value)

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
    def parse(cls, value: object) -> "MinTransactions":
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


@dataclass(frozen=True)
class RankingCriteria:
    """What to rank, in which order, how many places and from how many transactions."""

    level: RankingLevel = RankingLevel.CITY
    order: RankingOrder = RankingOrder.TRANSACTIONS_DESC
    limit: RankingLimit = field(default_factory=RankingLimit)
    min_transactions: MinTransactions = field(default_factory=MinTransactions)


# --- the ranking -----------------------------------------------------------------------------


@dataclass(frozen=True)
class LocationRanking:
    """The first places of a ranking and how many there were (D4: the cut is explicit)."""

    criteria: RankingCriteria
    items: tuple[LocationTransactions, ...]
    total: int
    """Places with at least ``min_transactions``, before the cut to ``limit``."""

    @classmethod
    def of(
        cls, criteria: RankingCriteria, places: Iterable[LocationTransactions]
    ) -> "LocationRanking":
        least = criteria.min_transactions.value
        ranked = sorted(
            (place for place in places if place.transaction_count >= least),
            key=criteria.order.key,
        )
        return cls(criteria, tuple(ranked[: criteria.limit.value]), len(ranked))

    @property
    def returned(self) -> int:
        return len(self.items)

    @property
    def truncated(self) -> bool:
        """More places meet the criteria than shown."""
        return self.total > self.returned
