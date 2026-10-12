"""Value objects of the domain (D13): checked when they are made, immutable, plain Python.

What a caller may ask for, in the domain's terms: amounts in PLN, areas in m², ranges of
both, slugs of cities, investments and locations, an offer id, a page of results and its
size, the order of offers, a search text. A constructor (or ``parse``, for raw input)
raises ``InvalidValueError``: which value, which rule, what was given. The application
words it for its callers (``application.arguments``).

The limits are the service's (docs/discovery/pages-rsc.md, "Wspólne reguły list"): at
most ``BROWSABLE_PAGES`` pages, ``PAGE_SIZES`` offers a page, prices up to
``AmountPln.MAX`` and areas up to ``AreaM2.MAX``. A range open at one end has no bound
there (``None``); how the service is told so is the infrastructure's business.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Generic, Self, TypeVar

from deweloperuch_mcp.domain.errors import (
    InvalidValueError,
    LowNotAboveHigh,
    OneOf,
    SlugText,
    TextLength,
    TrueOrFalse,
    ValueName,
    WholeNumber,
)

WHOLE_COUNTRY = "polska"
"""The slug of the whole country: of the offers list and of the government statistics [P]."""

BROWSABLE_PAGES = 20
"""[P] pages-rsc.md, "Wspólne reguły list": a page above 20 returns page 20."""

PAGE_SIZES = (10, 50, 100)
"""[P] same section: other page sizes (20, 500) silently fall back to 10."""

DEFAULT_PAGE_SIZE = 10
"""The service's own page size [P]."""

SLUG_MAX = 200
QUERY_MIN, QUERY_MAX = 2, 100
OFFERS_LIMIT_MAX = 100_000
OFFER_ID_MAX = 2**63 - 1

# Slugs seen in the samples and on the statistics pages [P 2026-10-11]: lowercase ASCII
# letters, digits and hyphens. Anything else (Polish letters, `/`, `?`, `..`) is not a
# slug and must not reach a URL path.
_SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")


def is_whole(value: object) -> bool:
    """An ``int`` that is not a ``bool`` (``True`` is no number here)."""
    return isinstance(value, int) and not isinstance(value, bool)


def whole(name: ValueName, value: object, low: int, high: int, unit: str | None = None) -> int:
    """``value`` if it is a whole number within ``low``..``high``."""
    if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high:
        return value
    raise InvalidValueError(name, WholeNumber(low, high, unit), value)


def flag(name: ValueName, value: object) -> bool:
    """``value`` if it is ``True`` or ``False``."""
    if not isinstance(value, bool):
        raise InvalidValueError(name, TrueOrFalse(), value)
    return value


def is_slug(text: str) -> bool:
    return len(text) <= SLUG_MAX and _SLUG.fullmatch(text) is not None


# --- slugs -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Slug:
    """An identity as the service writes it in its addresses: ``[a-z0-9][a-z0-9-]*``.

    Subclasses say what it identifies (``NAME``).
    """

    value: str

    NAME: ClassVar[ValueName]

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not is_slug(self.value):
            raise self.refused(self.value)

    @classmethod
    def parse(cls, value: object) -> Self:
        """``value`` without spaces around it; a refusal repeats ``value`` as given."""
        text = value.strip() if isinstance(value, str) else ""
        if not text or not is_slug(text):
            raise cls.refused(value)
        return cls(text)

    @classmethod
    def refused(cls, value: object) -> InvalidValueError:
        return InvalidValueError(cls.NAME, SlugText(), value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class CitySlug(Slug):
    """The city of an offers search, or ``polska`` for the whole country."""

    NAME: ClassVar[ValueName] = ValueName.CITY

    @property
    def whole_country(self) -> bool:
        return self.value == WHOLE_COUNTRY


@dataclass(frozen=True)
class InvestmentSlug(Slug):
    NAME: ClassVar[ValueName] = ValueName.INVESTMENT


@dataclass(frozen=True)
class LocationSlug(Slug):
    """A location of the government statistics: ``polska``, an aggregate or a city."""

    NAME: ClassVar[ValueName] = ValueName.STATISTICS_LOCATION

    @classmethod
    def parse(cls, value: object) -> Self:
        """``value`` without spaces around it, in lowercase (``Warszawa`` is ``warszawa``);
        Polish letters are not replaced, so ``Kraków`` is refused. A refusal repeats the
        trimmed text."""
        if not isinstance(value, str):
            raise cls.refused(value)
        text = value.strip()
        if not is_slug(text.lower()):
            raise cls.refused(text)
        return cls(text.lower())

    @property
    def whole_country(self) -> bool:
        return self.value == WHOLE_COUNTRY


# --- numbers -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class OfferId:
    """An offer's identifier, as search results and investments give it."""

    value: int

    def __post_init__(self) -> None:
        whole(ValueName.OFFER, self.value, 1, OFFER_ID_MAX)

    @classmethod
    def parse(cls, value: object) -> Self:
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


@dataclass(frozen=True)
class AmountPln:
    """A whole amount in PLN, 0..``MAX``: the largest price a filter takes."""

    value: int

    MAX: ClassVar[int] = 99_999_999
    UNIT: ClassVar[str] = "PLN"

    def __post_init__(self) -> None:
        whole(ValueName.AMOUNT, self.value, 0, self.MAX, self.UNIT)

    @classmethod
    def parse(cls, value: object, *, name: ValueName = ValueName.AMOUNT) -> Self:
        """``value`` checked as ``name`` (the start or the end of a range...)."""
        return cls(whole(name, value, 0, cls.MAX, cls.UNIT))


@dataclass(frozen=True)
class AreaM2:
    """A whole area in m², 0..``MAX``: the largest area a filter takes."""

    value: int

    MAX: ClassVar[int] = 9_999
    UNIT: ClassVar[str] = "m²"

    def __post_init__(self) -> None:
        whole(ValueName.AREA, self.value, 0, self.MAX, self.UNIT)

    @classmethod
    def parse(cls, value: object, *, name: ValueName = ValueName.AREA) -> Self:
        return cls(whole(name, value, 0, cls.MAX, cls.UNIT))


Q = TypeVar("Q", AmountPln, AreaM2)


@dataclass(frozen=True)
class Range(Generic[Q]):
    """From ``low`` to ``high``, both included; an end left open (``None``) has no bound."""

    low: Q | None = None
    high: Q | None = None

    NAME: ClassVar[ValueName]
    LOW: ClassVar[ValueName]
    HIGH: ClassVar[ValueName]

    def __post_init__(self) -> None:
        if self.low is not None and self.high is not None and self.low.value > self.high.value:
            bounds = (self.low.value, self.high.value)
            raise InvalidValueError(self.NAME, LowNotAboveHigh(*bounds), bounds)

    @classmethod
    def end(cls, value: object, name: ValueName) -> Q:
        raise NotImplementedError

    @classmethod
    def parse(cls, low: object, high: object) -> Self | None:
        """``None`` when both ends are open (no bound at all); the start is checked first."""
        if low is None and high is None:
            return None
        return cls(
            None if low is None else cls.end(low, cls.LOW),
            None if high is None else cls.end(high, cls.HIGH),
        )


class PriceRange(Range[AmountPln]):
    """Prices in PLN."""

    NAME = ValueName.PRICE_RANGE
    LOW = ValueName.PRICE_FROM
    HIGH = ValueName.PRICE_TO

    @classmethod
    def end(cls, value: object, name: ValueName) -> AmountPln:
        return AmountPln.parse(value, name=name)


class AreaRange(Range[AreaM2]):
    """Areas in m²."""

    NAME = ValueName.AREA_RANGE
    LOW = ValueName.AREA_FROM
    HIGH = ValueName.AREA_TO

    @classmethod
    def end(cls, value: object, name: ValueName) -> AreaM2:
        return AreaM2.parse(value, name=name)


# --- pages and order ------------------------------------------------------------------------


@dataclass(frozen=True)
class PageNumber:
    """A page of search results: 1..``BROWSABLE_PAGES``."""

    value: int = 1

    def __post_init__(self) -> None:
        whole(ValueName.PAGE, self.value, 1, BROWSABLE_PAGES)

    @classmethod
    def parse(cls, value: object) -> Self:
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


@dataclass(frozen=True)
class PageSize:
    """Offers on a page: one of ``PAGE_SIZES``."""

    value: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if not is_whole(self.value) or self.value not in PAGE_SIZES:
            raise InvalidValueError(ValueName.PAGE_SIZE, OneOf(PAGE_SIZES), self.value)

    @classmethod
    def parse(cls, value: object) -> Self:
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


class OfferSort(StrEnum):
    """The order of an offers search; without one, the service's own order [P]."""

    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"

    @classmethod
    def parse(cls, value: object) -> "OfferSort | None":
        """``None`` keeps the service's order; anything but a known name is refused."""
        if value is None:
            return None
        if not isinstance(value, str) or value not in cls._value2member_map_:
            choices = tuple(member.value for member in cls)
            raise InvalidValueError(ValueName.SORT, OneOf(choices), value)
        return cls(value)


@dataclass(frozen=True)
class OffersLimit:
    """How many offers of an investment a result shows (``None`` elsewhere: all of them)."""

    value: int

    def __post_init__(self) -> None:
        whole(ValueName.OFFERS_LIMIT, self.value, 0, OFFERS_LIMIT_MAX)

    @classmethod
    def parse(cls, value: object) -> "OffersLimit | None":
        return None if value is None else cls(value)  # type: ignore[arg-type]


@dataclass(frozen=True)
class LocationQuery:
    """A part of the name of a city, district or street: ``QUERY_MIN``..``QUERY_MAX``
    characters, Polish letters included."""

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not QUERY_MIN <= len(self.text) <= QUERY_MAX:
            raise self.refused(self.text)

    @classmethod
    def parse(cls, value: object) -> Self:
        """``value`` without spaces around it; a refusal repeats ``value`` as given."""
        text = value.strip() if isinstance(value, str) else ""
        if not QUERY_MIN <= len(text) <= QUERY_MAX:
            raise cls.refused(value)
        return cls(text)

    @staticmethod
    def refused(value: object) -> InvalidValueError:
        return InvalidValueError(ValueName.QUERY, TextLength(QUERY_MIN, QUERY_MAX), value)

    def __str__(self) -> str:
        return self.text
