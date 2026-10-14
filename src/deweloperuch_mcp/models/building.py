"""Buildings of the price register (RCN): their units and the transactions they sold in
(D3, D13).

The register's world is apart from the offers' (docs/discovery/entities.md): a building
is an address with units (flats), each sold in one or more transactions recorded by the
national price register, at the prices of the deeds (not asking prices). No backend names
(``invest``, ``sale``, ``amount``) and no backend values: numbers are ``float`` (PLN,
m²), dates ``datetime.date``, missing values ``None``. Value sets the service may extend
(the market, the classification, the parties) stay plain strings: unknown values pass
through, so a new one is shown instead of failing.

- ``Building.listing``: what a result shows: the units whose last transaction is the
  newest first, at most ``limit`` of them, with the number left out (D4).
- ``NeighbourhoodTrend.latest``: the newest quarters of the price per m² around the
  building, with the number of older ones left out (D4).
"""

import datetime as dt
from dataclasses import dataclass, replace
from typing import ClassVar, Self

from deweloperuch_mcp.models.errors import ValueName, WholeNumber
from deweloperuch_mcp.models.values import Slug

PRIMARY, SECONDARY = "primary", "secondary"
"""Markets of a transaction [P]."""

NATURAL_PERSON, LEGAL_PERSON = "natural_person", "legal_person"
"""Buyers and sellers [P]: a person, or a company or an institution."""

REGULAR, SHARE, BULK, GOVERNMENT, ENFORCEMENT, DISCOUNT = (
    "regular",
    "share",
    "bulk",
    "government",
    "enforcement",
    "discount",
)
ANOMALY_LOW, ANOMALY_HIGH = "anomaly_low", "anomaly_high"
"""How the service classes a transaction [P]; what each class means is read from its
Polish label [W] (``api.dto.building_dto``)."""

WHOLE_UNIT = "1/1"
"""The share of a transaction that sold the whole unit [P]."""

UNITS_LIMIT_MAX = 100_000


# --- value objects ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildingSlug(Slug):
    """A building of the register as the service writes it in addresses, e.g.
    ``23-marca-79c-sopot`` [P]. Its alphabet is the other slugs' (``values.Slug``): that
    building slugs never hold other characters is [W] (two samples), and anything else
    must not reach a URL path anyway."""

    NAME: ClassVar[ValueName] = ValueName.BUILDING


@dataclass(frozen=True)
class UnitsLimit:
    """How many units of a building a result shows (``None`` elsewhere: all of them)."""

    value: int

    def __post_init__(self) -> None:
        WholeNumber(0, UNITS_LIMIT_MAX).check(ValueName.UNITS_LIMIT, self.value)

    @classmethod
    def parse(cls, value: object) -> "UnitsLimit | None":
        return None if value is None else cls(value)  # type: ignore[arg-type]


# --- the building ----------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class Transaction:
    """One sale of a unit, as the register recorded it."""

    date: dt.date | None
    """The day of the deed; ``None`` only if the service gave no date."""
    price: float | None
    """The price of the deed, in ``currency``."""
    price_per_m2: float | None
    """As the service computes it."""
    currency: str | None = None
    market: str | None = None
    """``primary`` or ``secondary``."""
    classification: str | None = None
    """``regular``, ``share``, ``bulk``, ``government``, ``enforcement``, ``discount``,
    ``anomaly_low`` or ``anomaly_high``."""
    buyer: str | None = None
    """``natural_person`` or ``legal_person``."""
    seller: str | None = None
    """``natural_person`` or ``legal_person``."""
    share: str | None = None
    """The fraction of the unit sold, e.g. ``1/2``; ``1/1`` is the whole unit."""

    @property
    def whole_unit(self) -> bool:
        return self.share == WHOLE_UNIT


def _day(transaction: Transaction) -> dt.date:
    return transaction.date or dt.date.min


@dataclass(frozen=True, kw_only=True)
class Unit:
    """A unit (a flat) of a building with its transactions, oldest first (those without
    a date, none seen so far, before the rest)."""

    unit_id: int
    """The register's number of the unit."""
    name: str
    """The register's designation of the unit, e.g. ``226401_1.0018.6977_BUD.3_LOK``."""
    floor: int | None = None
    rooms: int | None = None
    area_m2: float | None = None
    transactions: tuple[Transaction, ...] = ()

    def __post_init__(self) -> None:
        dates = [_day(transaction) for transaction in self.transactions]
        if dates != sorted(dates):
            raise ValueError("transakcje lokalu nie są w kolejności dat")

    @property
    def last_sold_on(self) -> dt.date | None:
        return max((t.date for t in self.transactions if t.date is not None), default=None)


@dataclass(frozen=True, kw_only=True)
class BuildingRef:
    """What the page of a building is found by."""

    building_slug: str
    city_slug: str | None


@dataclass(frozen=True, kw_only=True)
class Building:
    """A building (an address) of the register with every unit sold in it, in the
    service's order."""

    building_id: int
    """The register's number of the building (its neighbourhood trend is kept under
    it); never shown."""
    building_slug: str
    name: str
    """The address, as the register writes it (``23 Marca 79C``)."""
    city: str
    city_slug: str
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    avg_price: float | None = None
    """The mean transaction price, as the service counts it."""
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None
    units: tuple[Unit, ...] = ()

    @property
    def ref(self) -> BuildingRef:
        return BuildingRef(building_slug=self.building_slug, city_slug=self.city_slug)

    @property
    def transactions_count(self) -> int:
        return sum(len(unit.transactions) for unit in self.units)

    @property
    def first_sold_on(self) -> dt.date | None:
        dates = (t.date for unit in self.units for t in unit.transactions)
        return min((date for date in dates if date is not None), default=None)

    @property
    def last_sold_on(self) -> dt.date | None:
        return max((d for d in (unit.last_sold_on for unit in self.units) if d), default=None)

    def listing(self, limit: UnitsLimit | None = None) -> "UnitListing":
        """The units whose last transaction is the newest first (those without one last;
        equal ones in the service's order), at most ``limit``."""
        # sorted() is stable with reverse=True too: equals keep the service's order.
        ordered = sorted(
            self.units, key=lambda unit: unit.last_sold_on or dt.date.min, reverse=True
        )
        kept = ordered if limit is None else ordered[: limit.value]
        return UnitListing(building=self, units=tuple(kept), omitted=len(ordered) - len(kept))


@dataclass(frozen=True, kw_only=True)
class UnitListing:
    """What a result shows of a building: the units kept and how many were left out."""

    building: Building
    units: tuple[Unit, ...]
    omitted: int


# --- the neighbourhood -----------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class TrendQuarter:
    """The transactions around a building in one quarter."""

    period: str
    """``2025-Q3``: such labels sort in time order."""
    avg_price_per_m2: float | None
    transactions: int | None = None


@dataclass(frozen=True, kw_only=True)
class NeighbourhoodTrend:
    """The price per m² of the transactions within ``radius_km`` of a building, quarter
    by quarter, oldest first; ``omitted`` older quarters left out (``latest``)."""

    radius_km: float | None
    quarters: tuple[TrendQuarter, ...]
    omitted: int = 0

    def __post_init__(self) -> None:
        periods = [quarter.period for quarter in self.quarters]
        if periods != sorted(periods):
            raise ValueError("kwartały trendu nie są w kolejności")

    @property
    def total(self) -> int:
        """Every quarter the service has."""
        return len(self.quarters) + self.omitted

    def latest(self, count: int | None) -> Self:
        """The newest ``count`` quarters (all of them for ``None``)."""
        if count is None or count >= len(self.quarters):
            return self
        if count < 0:
            raise ValueError("liczba kwartałów nie może być ujemna")
        kept = self.quarters[len(self.quarters) - count :]
        return replace(self, quarters=kept, omitted=self.total - len(kept))
