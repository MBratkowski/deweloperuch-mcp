"""Searching investments (D3, D13): the investments of one city with the averages of their
active offers, or the investments whose name contains a text, across the country.

- ``InvestmentSummary``: an investment as a search lists it. A search in a city knows its
  place, developer, offer counts and averages; a search by name only its slug, name and
  active offers.
- ``InvestmentSearchCriteria``: a city or a part of the name (or both), optionally a
  developer and an order (both need the city), and how many investments a result shows.
- ``InvestmentSearchCriteria.select``: what a search in a city shows of the city's
  investments: filtered by name and developer, ordered, cut to the limit (D4).
- ``InvestmentSearchResult.of_matches``: what a search by name shows of what the service
  matched, in the service's order.

A part of a name matches regardless of letter case, Polish diacritics and repeated spaces
(``InvestmentName.folded``: ``Kolibki`` finds ``Nowe Kolibki etap 4``, ``targowek`` finds
``Nowy Targówek VI``).
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Self

from deweloperuch_mcp.models.errors import (
    InvalidValueError,
    OneOf,
    TextLength,
    ValueName,
    WholeNumber,
)
from deweloperuch_mcp.models.offer import DeveloperRef, InvestmentRef
from deweloperuch_mcp.models.values import CitySlug, DeveloperSlug

NAME_MIN, NAME_MAX = 2, 100
"""Characters of a part of an investment's name."""

DEFAULT_INVESTMENTS_LIMIT = 10
"""Investments a result shows unless asked otherwise."""

INVESTMENTS_LIMIT_MAX = 500
"""Most investments one result shows (the largest city lists a few hundred)."""

NAME_SEARCH_MAX = 50
"""Most investments a search by name shows: the service's search by name feeds a box of
suggestions (the sample api.investments_q asks for 5), not long lists."""

_POLISH = str.maketrans("ąćęłńóśźż", "acelnoszz")


@dataclass(frozen=True)
class InvestmentsCity(CitySlug):
    """The one city of an investments search; the whole country has no such list."""

    NAME: ClassVar[ValueName] = ValueName.INVESTMENTS_CITY


@dataclass(frozen=True)
class InvestmentName:
    """A part of an investment's name: ``NAME_MIN``..``NAME_MAX`` characters, Polish
    letters included."""

    text: str

    def __post_init__(self) -> None:
        given: object = self.text  # a dataclass does not check the type it is given
        if not isinstance(given, str) or not NAME_MIN <= len(given) <= NAME_MAX:
            raise self.refused(given)

    @classmethod
    def parse(cls, value: object) -> Self:
        """``value`` without spaces around it; a refusal repeats ``value`` as given."""
        text = value.strip() if isinstance(value, str) else ""
        if not NAME_MIN <= len(text) <= NAME_MAX:
            raise cls.refused(value)
        return cls(text)

    @staticmethod
    def refused(value: object) -> InvalidValueError:
        return InvalidValueError(ValueName.INVESTMENT_NAME, TextLength(NAME_MIN, NAME_MAX), value)

    def matches(self, name: str) -> bool:
        """Whether ``name`` contains this text (``folded``: case, diacritics, spaces)."""
        return self.folded(self.text) in self.folded(name)

    @staticmethod
    def folded(text: str) -> str:
        """``text`` for comparing names: lowercase, without Polish diacritics, single spaces."""
        return " ".join(text.casefold().translate(_POLISH).split())


class InvestmentSort(StrEnum):
    """The order of a search in a city; without one, the most active offers first."""

    ACTIVE_OFFERS = "active_offers"
    PRICE_PER_M2_ASC = "price_per_m2_asc"
    PRICE_PER_M2_DESC = "price_per_m2_desc"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    NAME = "name"

    @classmethod
    def parse(cls, value: object) -> "InvestmentSort | None":
        """``None`` keeps the default order; anything but a known name is refused."""
        if value is None:
            return None
        if not isinstance(value, str) or value not in cls._value2member_map_:
            choices = tuple(member.value for member in cls)
            raise InvalidValueError(ValueName.INVESTMENT_SORT, OneOf(choices), value)
        return cls(value)

    def ordered(self, investments: "Iterable[InvestmentSummary]") -> "list[InvestmentSummary]":
        """``investments`` in this order; ties (and ``name``) by name, then slug. An
        investment without the compared value comes last, whichever the direction."""

        def by_name(item: InvestmentSummary) -> tuple[str, str]:
            return InvestmentName.folded(item.name), item.investment_slug

        if self is InvestmentSort.NAME:
            return sorted(investments, key=by_name)
        value, descending = _ORDERS[self]

        def key(item: InvestmentSummary) -> tuple[bool, float, tuple[str, str]]:
            found = value(item)
            if found is None:
                return True, 0.0, by_name(item)
            return False, -found if descending else found, by_name(item)

        return sorted(investments, key=key)


DEFAULT_INVESTMENT_SORT = InvestmentSort.ACTIVE_OFFERS


@dataclass(frozen=True)
class InvestmentsLimit:
    """How many investments a result shows: 1..``INVESTMENTS_LIMIT_MAX``."""

    value: int = DEFAULT_INVESTMENTS_LIMIT

    def __post_init__(self) -> None:
        WholeNumber(1, INVESTMENTS_LIMIT_MAX).check(ValueName.INVESTMENTS_LIMIT, self.value)

    @classmethod
    def parse(cls, value: object) -> Self:
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


@dataclass(frozen=True, kw_only=True)
class InvestmentSummary:
    """An investment in search results; what the search did not learn is ``None``."""

    investment_slug: str
    name: str
    status: str | None = None
    """``active`` or ``archived``."""
    city: str | None = None
    city_slug: str | None = None
    district: str | None = None
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    developer: DeveloperRef | None = None
    avg_price: float | None = None
    """Mean price of the active offers in PLN, as the service counts it."""
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None
    offers_active: int | None = None
    offers_total: int | None = None
    """Active and archived offers, as counted by the service."""

    @property
    def ref(self) -> InvestmentRef | None:
        """The investment as its pages know it; ``None`` without its developer."""
        if self.developer is None:
            return None
        return InvestmentRef(
            investment_slug=self.investment_slug,
            name=self.name,
            city=self.city,
            city_slug=self.city_slug,
            developer=self.developer,
        )


@dataclass(frozen=True)
class InvestmentMatches:
    """What the service matched by name: the investments it gave, how many match in all
    (``None``: it did not say) and whether it has more than it gave."""

    items: tuple[InvestmentSummary, ...]
    total: int | None = None
    more: bool = False


Value = Callable[[InvestmentSummary], float | None]

_ORDERS: Mapping[InvestmentSort, tuple[Value, bool]] = {
    InvestmentSort.ACTIVE_OFFERS: (lambda item: item.offers_active, True),
    InvestmentSort.PRICE_PER_M2_ASC: (lambda item: item.avg_price_per_m2, False),
    InvestmentSort.PRICE_PER_M2_DESC: (lambda item: item.avg_price_per_m2, True),
    InvestmentSort.PRICE_ASC: (lambda item: item.avg_price, False),
    InvestmentSort.PRICE_DESC: (lambda item: item.avg_price, True),
}
"""The value each order compares and whether the largest comes first."""


@dataclass(frozen=True, kw_only=True)
class InvestmentSearchCriteria:
    """What an investments search asks for: a city or a part of the name (or both); a
    developer and an order only with the city; at most ``limit`` investments."""

    city: CitySlug | None = None
    name: InvestmentName | None = None
    developer: DeveloperSlug | None = None
    sort: InvestmentSort | None = None
    """``None``: the most active offers first in a city, the service's order by name."""
    limit: InvestmentsLimit = InvestmentsLimit()

    def __post_init__(self) -> None:
        if self.city is None and self.name is None:
            raise ValueError("wyszukiwanie inwestycji wymaga miasta albo części nazwy")
        if self.city is None and (self.developer is not None or self.sort is not None):
            raise ValueError("deweloper i kolejność zawężają tylko wyszukiwanie w mieście")
        if self.city is not None and self.city.whole_country:
            raise ValueError("wyszukiwanie inwestycji obejmuje jedno miasto, nie cały kraj")

    def admits(self, investment: InvestmentSummary) -> bool:
        """Whether ``investment`` has the name part and the developer asked for."""
        if self.name is not None and not self.name.matches(investment.name):
            return False
        if self.developer is None:
            return True
        found = investment.developer
        return found is not None and found.developer_slug == self.developer.value

    @property
    def shown_at_most(self) -> InvestmentsLimit:
        """``limit``; by name, at most ``NAME_SEARCH_MAX``."""
        if self.city is None and self.limit.value > NAME_SEARCH_MAX:
            return InvestmentsLimit(NAME_SEARCH_MAX)
        return self.limit

    def select(self, investments: Iterable[InvestmentSummary]) -> "InvestmentSearchResult":
        """The city's ``investments`` this search admits, in its order, at most ``limit``."""
        matching = [item for item in investments if self.admits(item)]
        shown = (self.sort or DEFAULT_INVESTMENT_SORT).ordered(matching)[: self.limit.value]
        return InvestmentSearchResult(criteria=self, items=tuple(shown), total=len(matching))


@dataclass(frozen=True, kw_only=True)
class InvestmentSearchResult:
    """The investments a search shows (D4: what is left out is part of the result)."""

    criteria: InvestmentSearchCriteria
    items: tuple[InvestmentSummary, ...]
    total: int | None
    """All matching investments; ``None`` when the service did not say (by name)."""
    more: bool = False
    """The service has more matches than it gave (a search by name)."""

    @classmethod
    def of_matches(cls, criteria: InvestmentSearchCriteria, matches: InvestmentMatches) -> Self:
        """What a search by name shows of the service's matches: at most ``shown_at_most``
        of them, in the service's order; a total below what it gave is raised to that."""
        shown = matches.items[: criteria.shown_at_most.value]
        total = None if matches.total is None else max(matches.total, len(matches.items))
        more = matches.more or len(shown) < len(matches.items)
        return cls(criteria=criteria, items=shown, total=total, more=more)

    @property
    def returned(self) -> int:
        return len(self.items)

    @property
    def truncated(self) -> bool:
        """More investments match than the result shows."""
        return self.more or (self.total is not None and self.total > self.returned)

    @property
    def larger_limit_shows_more(self) -> bool:
        """``truncated``, and a larger ``limit`` would show more: in a city up to
        ``INVESTMENTS_LIMIT_MAX``, by name up to ``NAME_SEARCH_MAX``."""
        ceiling = INVESTMENTS_LIMIT_MAX if self.criteria.city is not None else NAME_SEARCH_MAX
        return self.truncated and self.criteria.limit.value < ceiling
