"""Value objects of the domain (D13): checked when they are made, immutable, plain Python.

What a caller may ask for, in the domain's terms: amounts in PLN, areas in m², prices
per m², ranges of them, slugs of cities, investments, developers and locations, a
district, the status of offers, an offer id, a page of results and its size, the order
of offers, how many items a result shows, a search text. A constructor (or ``parse``, for raw input)
raises ``InvalidValueError``: which value, which rule, what was given. The application
words it for its callers (``usecases.support.arguments``).

The limits are the service's (docs/discovery/pages-rsc.md, "Wspólne reguły list"): at
most ``BROWSABLE_PAGES`` pages, ``PAGE_SIZES`` offers a page, prices up to
``AmountPln.MAX`` and areas up to ``AreaM2.MAX``. A range open at one end has no bound
there (``None``); how the service is told so is the infrastructure's business.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Generic, Self, TypeVar

from deweloperuch_mcp.models.errors import (
    InvalidValueError,
    LowNotAboveHigh,
    OneOf,
    SlugText,
    TextLength,
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
DISTRICT_MIN, DISTRICT_MAX = 2, 100
OFFERS_LIMIT_MAX = 100_000
INVESTMENTS_LIMIT_MAX = 1_000
TOP_DEVELOPERS_MAX = 30
OFFER_ID_MAX = 2**63 - 1

# Slugs seen in the samples and on the statistics pages [P 2026-10-11]: lowercase ASCII
# letters, digits and hyphens. Anything else (Polish letters, `/`, `?`, `..`) is not a
# slug and must not reach a URL path.
_SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")


def _is_whole(value: object) -> bool:
    """An ``int`` that is not a ``bool`` (``True`` is no number here)."""
    return isinstance(value, int) and not isinstance(value, bool)


# --- slugs -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Slug:
    """An identity as the service writes it in its addresses: ``[a-z0-9][a-z0-9-]*``.

    Subclasses say what it identifies (``NAME``).
    """

    value: str

    NAME: ClassVar[ValueName]

    def __post_init__(self) -> None:
        given: object = self.value  # a dataclass does not check the type it is given
        if not isinstance(given, str) or not Slug.fits(given):
            raise self.refused(given)

    @staticmethod
    def fits(text: str) -> bool:
        """``text`` is written as the service writes identities (at most ``SLUG_MAX``)."""
        return len(text) <= SLUG_MAX and _SLUG.fullmatch(text) is not None

    @classmethod
    def parse(cls, value: object) -> Self:
        """``value`` without spaces around it; a refusal repeats ``value`` as given."""
        text = value.strip() if isinstance(value, str) else ""
        if not text or not Slug.fits(text):
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
class DeveloperSlug(Slug):
    NAME: ClassVar[ValueName] = ValueName.DEVELOPER


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
        if not Slug.fits(text.lower()):
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
        WholeNumber(1, OFFER_ID_MAX).check(ValueName.OFFER, self.value)

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
        WholeNumber(0, self.MAX, self.UNIT).check(ValueName.AMOUNT, self.value)

    @classmethod
    def parse(cls, value: object, *, name: ValueName = ValueName.AMOUNT) -> Self:
        """``value`` checked as ``name`` (the start or the end of a range...)."""
        return cls(WholeNumber(0, cls.MAX, cls.UNIT).check(name, value))


@dataclass(frozen=True)
class AreaM2:
    """A whole area in m², 0..``MAX``: the largest area a filter takes."""

    value: int

    MAX: ClassVar[int] = 9_999
    UNIT: ClassVar[str] = "m²"

    def __post_init__(self) -> None:
        WholeNumber(0, self.MAX, self.UNIT).check(ValueName.AREA, self.value)

    @classmethod
    def parse(cls, value: object, *, name: ValueName = ValueName.AREA) -> Self:
        return cls(WholeNumber(0, cls.MAX, cls.UNIT).check(name, value))


@dataclass(frozen=True)
class PricePerM2Pln:
    """A whole price per m² in PLN, 0..``MAX``: the largest one a filter takes (the UI's
    open upper end of its price-per-m² range, [P z kodu] pages-rsc.md)."""

    value: int

    MAX: ClassVar[int] = 999_999
    UNIT: ClassVar[str] = "PLN/m²"

    def __post_init__(self) -> None:
        WholeNumber(0, self.MAX, self.UNIT).check(ValueName.PRICE_PER_M2, self.value)

    @classmethod
    def parse(cls, value: object, *, name: ValueName = ValueName.PRICE_PER_M2) -> Self:
        return cls(WholeNumber(0, cls.MAX, cls.UNIT).check(name, value))


Q = TypeVar("Q", AmountPln, AreaM2, PricePerM2Pln)


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


class PricePerM2Range(Range[PricePerM2Pln]):
    """Prices per m² in PLN."""

    NAME = ValueName.PRICE_PER_M2_RANGE
    LOW = ValueName.PRICE_PER_M2_FROM
    HIGH = ValueName.PRICE_PER_M2_TO

    @classmethod
    def end(cls, value: object, name: ValueName) -> PricePerM2Pln:
        return PricePerM2Pln.parse(value, name=name)


# --- what else narrows a search -------------------------------------------------------------


@dataclass(frozen=True)
class DistrictName:
    """A district of a city as the locations search names it, e.g. ``Mokotów``:
    ``DISTRICT_MIN``..``DISTRICT_MAX`` printable characters, Polish letters included."""

    text: str

    def __post_init__(self) -> None:
        given: object = self.text  # a dataclass does not check the type it is given
        if not (
            isinstance(given, str)
            and DISTRICT_MIN <= len(given) <= DISTRICT_MAX
            and given.isprintable()
        ):
            raise self.refused(given)

    @classmethod
    def parse(cls, value: object) -> "DistrictName | None":
        """``None`` (no district) for ``None``; otherwise ``value`` without spaces around
        it. A refusal repeats ``value`` as given."""
        if value is None:
            return None
        text = value.strip() if isinstance(value, str) else ""
        if not (DISTRICT_MIN <= len(text) <= DISTRICT_MAX and text.isprintable()):
            raise cls.refused(value)
        return cls(text)

    @staticmethod
    def refused(value: object) -> InvalidValueError:
        return InvalidValueError(ValueName.DISTRICT, TextLength(DISTRICT_MIN, DISTRICT_MAX), value)

    def __str__(self) -> str:
        return self.text


class OfferStatus(StrEnum):
    """Which offers a search returns: those in the price lists now (the default), those
    withdrawn from them, or both [P] (pages-rsc.md)."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    ALL = "all"

    @classmethod
    def parse(cls, value: object) -> "OfferStatus":
        """``None`` is ``ACTIVE``; anything but a known name is refused."""
        if value is None:
            return cls.ACTIVE
        if not isinstance(value, str) or value not in cls._value2member_map_:
            choices = tuple(member.value for member in cls)
            raise InvalidValueError(ValueName.OFFER_STATUS, OneOf(choices), value)
        return cls(value)


# --- pages and order ------------------------------------------------------------------------


@dataclass(frozen=True)
class PageNumber:
    """A page of search results: 1..``BROWSABLE_PAGES``."""

    value: int = 1

    def __post_init__(self) -> None:
        WholeNumber(1, BROWSABLE_PAGES).check(ValueName.PAGE, self.value)

    @classmethod
    def parse(cls, value: object) -> Self:
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


@dataclass(frozen=True)
class PageSize:
    """Offers on a page: one of ``PAGE_SIZES``."""

    value: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if not _is_whole(self.value) or self.value not in PAGE_SIZES:
            raise InvalidValueError(ValueName.PAGE_SIZE, OneOf(PAGE_SIZES), self.value)

    @classmethod
    def parse(cls, value: object) -> Self:
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


class OfferSort(StrEnum):
    """The order of an offers search; without one, the service's own order [P]."""

    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    PRICE_PER_M2_ASC = "price_per_m2_asc"
    PRICE_PER_M2_DESC = "price_per_m2_desc"
    AREA_ASC = "area_asc"
    AREA_DESC = "area_desc"
    BIGGEST_DROP = "biggest_drop"
    """The largest drop since the first price first (the most negative change in %)."""

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
        WholeNumber(0, OFFERS_LIMIT_MAX).check(ValueName.OFFERS_LIMIT, self.value)

    @classmethod
    def parse(cls, value: object) -> "OffersLimit | None":
        return None if value is None else cls(value)  # type: ignore[arg-type]


@dataclass(frozen=True)
class InvestmentsLimit:
    """How many investments of a developer a result shows."""

    value: int

    def __post_init__(self) -> None:
        WholeNumber(1, INVESTMENTS_LIMIT_MAX).check(ValueName.INVESTMENTS_LIMIT, self.value)

    @classmethod
    def parse(cls, value: object) -> Self:
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


@dataclass(frozen=True)
class DeveloperCount:
    """How many of a city's largest developers a market summary names."""

    value: int

    def __post_init__(self) -> None:
        WholeNumber(1, TOP_DEVELOPERS_MAX).check(ValueName.TOP_DEVELOPERS, self.value)

    @classmethod
    def parse(cls, value: object) -> Self:
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


@dataclass(frozen=True)
class LocationQuery:
    """A part of the name of a city, district or street: ``QUERY_MIN``..``QUERY_MAX``
    characters, Polish letters included."""

    text: str

    def __post_init__(self) -> None:
        given: object = self.text  # a dataclass does not check the type it is given
        if not isinstance(given, str) or not QUERY_MIN <= len(given) <= QUERY_MAX:
            raise self.refused(given)

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
