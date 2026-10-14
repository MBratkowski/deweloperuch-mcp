"""Valuation of a flat (D3 ``Valuation``): an estimate from the RCN transactions nearby.

The service values a flat of a given area at a point by comparing it with transactions
of the Register of Real Estate Prices (RCN) around that point: an estimated price per m²
and value, the radius and the period it took the transactions from, statistics of their
prices per m², and the transactions themselves. An approximation from comparable
transactions, not an appraisal::

    subject = ValuationSubject.parse(52.2297, 21.0122, 50)  # InvalidValueError if refused
    valuation = source.valuation(subject)                  # ports.ValuationSource
    listing = valuation.nearest(ComparablesLimit(10))      # D4, D5: the nearest, the rest counted

The domain says where a point may be (``POLAND_LAT``, ``POLAND_LNG``), which flats are
valued (``ValuedArea``) and how a result is cut: the nearest comparable transactions
first, at most ``limit`` of them, with the number left out. Plain Python: no I/O, no
backend names, no addresses of pages.
"""

import datetime as dt
import math
from dataclasses import dataclass
from typing import ClassVar, Self

from deweloperuch_mcp.models.errors import (
    InvalidValueError,
    NumberBetween,
    TextLength,
    ValueName,
    WholeNumber,
)

POLAND_LAT = (49.0, 54.9)
"""Latitudes of Poland in degrees, rounded outwards (49.00 N to 54.84 N): geography, not
a rule of the service. A point inside this box but outside Poland is not refused."""
POLAND_LNG = (14.1, 24.2)
"""Longitudes of Poland in degrees, rounded outwards (14.12 E to 24.15 E)."""

VALUED_AREA_MIN, VALUED_AREA_MAX = 10, 500
"""Areas of a flat to value, in m²: from a small studio to a large apartment."""
AREA_DECIMALS = 2
"""An area is kept to 0.01 m², as the service writes areas (e.g. 43.57)."""

ADDRESS_MIN, ADDRESS_MAX = 3, 200
"""Characters of an address that describes the valued flat."""

COMPARABLES_LIMIT_MAX = 100_000
"""Most comparable transactions a result may ask for (the CLI shows all by default)."""

PRIMARY, SECONDARY = "primary", "secondary"
"""Markets of a transaction: primary (from a developer) and secondary (resale) [P]
(docs/discovery/entities.md, ``marketType``); other values pass through."""


def _number(
    name: ValueName, value: object, low: float, high: float, unit: str | None = None
) -> float:
    """``value`` as a float if it is a finite number (not ``True``/``False``) within
    ``low``..``high``."""
    if (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and low <= value <= high
    ):
        return float(value)
    raise InvalidValueError(name, NumberBetween(low, high, unit), value)


# --- what to value ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Coordinates:
    """A point in Poland: latitude and longitude in degrees (WGS 84)."""

    lat: float
    lng: float

    def __post_init__(self) -> None:
        _number(ValueName.LATITUDE, self.lat, *POLAND_LAT)
        _number(ValueName.LONGITUDE, self.lng, *POLAND_LNG)

    @classmethod
    def parse(cls, lat: object, lng: object) -> Self:
        """Checked in this order: latitude, longitude."""
        return cls(
            _number(ValueName.LATITUDE, lat, *POLAND_LAT),
            _number(ValueName.LONGITUDE, lng, *POLAND_LNG),
        )


@dataclass(frozen=True)
class ValuedArea:
    """The area of the flat to value: ``VALUED_AREA_MIN``..``VALUED_AREA_MAX`` m²."""

    value: float

    UNIT: ClassVar[str] = "m²"

    def __post_init__(self) -> None:
        _number(ValueName.VALUED_AREA, self.value, VALUED_AREA_MIN, VALUED_AREA_MAX, self.UNIT)

    @classmethod
    def parse(cls, value: object) -> Self:
        """``value`` rounded to 0.01 m² (``AREA_DECIMALS``)."""
        area = _number(ValueName.VALUED_AREA, value, VALUED_AREA_MIN, VALUED_AREA_MAX, cls.UNIT)
        return cls(round(area, AREA_DECIMALS))


@dataclass(frozen=True)
class AddressText:
    """How a person describes the valued flat, e.g. ``Marszałkowska 100, Warszawa``:
    ``ADDRESS_MIN``..``ADDRESS_MAX`` characters. It does not say where the flat is: the
    coordinates do."""

    text: str

    def __post_init__(self) -> None:
        given: object = self.text  # a dataclass does not check the type it is given
        if not isinstance(given, str) or not ADDRESS_MIN <= len(given) <= ADDRESS_MAX:
            raise self.refused(given)

    @classmethod
    def parse(cls, value: object) -> "AddressText | None":
        """``None`` and blank text: no address; other text without spaces around it."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise cls.refused(value)
        text = value.strip()
        if not text:
            return None
        if not ADDRESS_MIN <= len(text) <= ADDRESS_MAX:
            raise cls.refused(value)
        return cls(text)

    @staticmethod
    def refused(value: object) -> InvalidValueError:
        return InvalidValueError(ValueName.ADDRESS, TextLength(ADDRESS_MIN, ADDRESS_MAX), value)


@dataclass(frozen=True)
class ValuationSubject:
    """What to value: a flat of ``area`` m² at ``point``; ``address`` only describes it."""

    point: Coordinates
    area: ValuedArea
    address: AddressText | None = None

    @classmethod
    def parse(cls, lat: object, lng: object, area: object, address: object = None) -> Self:
        """Checked in this order: latitude, longitude, area, address."""
        return cls(Coordinates.parse(lat, lng), ValuedArea.parse(area), AddressText.parse(address))


@dataclass(frozen=True)
class ComparablesLimit:
    """How many comparable transactions a result shows (``None`` elsewhere: all)."""

    value: int

    def __post_init__(self) -> None:
        WholeNumber(0, COMPARABLES_LIMIT_MAX).check(ValueName.COMPARABLES_LIMIT, self.value)

    @classmethod
    def parse(cls, value: object) -> "ComparablesLimit | None":
        if value is None:
            return None
        return cls(WholeNumber(0, COMPARABLES_LIMIT_MAX).check(ValueName.COMPARABLES_LIMIT, value))


# --- the valuation ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ComparableTransaction:
    """A sale of a flat near the valued point that the service compared it with."""

    address: str | None = None
    """Street and number of the building, as the service writes it."""
    date: dt.date | None = None
    price: float | None = None
    """The price paid, in PLN."""
    area_m2: float | None = None
    price_per_m2: float | None = None
    floor: int | None = None
    distance_m: float | None = None
    """From the valued point, in metres, rounded by the service to the nearest 50 m."""
    market: str | None = None
    """``PRIMARY`` or ``SECONDARY``."""
    building_slug: str | None = None
    """The service's identity of the building (what get_building takes)."""
    city_slug: str | None = None


@dataclass(frozen=True, kw_only=True)
class PricePerM2Stats:
    """Statistics of prices per m² (PLN) as the service gives them; which transactions
    they cover is the service's choice ([W]: the comparable ones in both samples)."""

    count: int | None = None
    median_price_per_m2: float | None = None
    average_price_per_m2: float | None = None
    min_price_per_m2: float | None = None
    max_price_per_m2: float | None = None


@dataclass(frozen=True, kw_only=True)
class Valuation:
    """The service's estimate for ``subject`` and the transactions it compared it with,
    in the service's order. ``None`` where the service gave no value."""

    subject: ValuationSubject
    estimated_value: float | None = None
    """In PLN: ``price_per_m2`` times the area."""
    price_per_m2: float | None = None
    radius_m: int | None = None
    """How far from the point the comparable transactions are."""
    period_months: int | None = None
    """How many of the latest months the comparable transactions come from."""
    stats: PricePerM2Stats | None = None
    comparables: tuple[ComparableTransaction, ...] = ()

    @property
    def estimated(self) -> bool:
        return self.estimated_value is not None

    def nearest(self, limit: ComparablesLimit | None = None) -> "ValuationListing":
        """The comparable transactions from the nearest (the service's order among equal
        distances, unknown distances last), at most ``limit``."""
        ordered = sorted(self.comparables, key=_by_distance)  # stable
        kept = ordered if limit is None else ordered[: limit.value]
        return ValuationListing(
            valuation=self, comparables=tuple(kept), omitted=len(ordered) - len(kept)
        )


def _by_distance(comparable: ComparableTransaction) -> tuple[bool, float]:
    distance = comparable.distance_m
    return (distance is None, 0.0 if distance is None else distance)


@dataclass(frozen=True, kw_only=True)
class ValuationListing:
    """What a result shows of a valuation: the comparable transactions kept and how many
    were left out (D4; D5: never the service's whole working set)."""

    valuation: Valuation
    comparables: tuple[ComparableTransaction, ...]
    omitted: int

    @property
    def total(self) -> int:
        """Every comparable transaction the service gave."""
        return len(self.valuation.comparables)

    @property
    def returned(self) -> int:
        return len(self.comparables)

    @property
    def truncated(self) -> bool:
        return self.omitted > 0
