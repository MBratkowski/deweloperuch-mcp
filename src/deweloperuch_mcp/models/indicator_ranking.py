"""``IndicatorRanking``: the cities with powiat rights ranked by one official indicator
(GUS, NBP) at one point in time (D3, D13).

Plain Python. For each of 66 cities the service gives the latest value of seven
indicators, each for its own period; the port ``usecases.ports.CityIndicatorSource``
hands one indicator over as ``IndicatorValues``. A ranking keeps the cities that have a
value (NBP prices: 17 of 66 [P 2026-11-02]), orders them by it and cuts the list to
``limit`` (D4)::

    criteria = IndicatorCriteria(Indicator.UNEMPLOYMENT_RATE, order=RankingOrder.VALUE_ASC)
    ranking = IndicatorRanking.of(criteria, source.indicator(criteria.indicator))

What each value means is the ranking's description's business (the tool's, checked against
the time series of ``models.government_statistics``); here a value is a number in its
``Indicator.unit``.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from deweloperuch_mcp.models.errors import InvalidValueError, OneOf, ValueName
from deweloperuch_mcp.models.location_ranking import RankingLimit, RankingOrder


class Indicator(StrEnum):
    """An official indicator of a city, as the ranking names it."""

    UNEMPLOYMENT_RATE = "unemployment_rate"
    AVERAGE_WAGE = "average_wage"
    DWELLINGS_COMPLETED = "dwellings_completed"
    DWELLINGS_STARTED = "dwellings_started"
    AVERAGE_DWELLING_AREA = "average_dwelling_area"
    NATURAL_INCREASE = "natural_increase"
    NBP_PRICE_PER_M2 = "nbp_price_per_m2"

    @classmethod
    def parse(cls, value: object) -> "Indicator":
        """An ``Indicator`` or its value (spaces around it ignored)."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str) and value.strip() in cls._value2member_map_:
            return cls(value.strip())
        raise InvalidValueError(ValueName.INDICATOR, OneOf(tuple(i.value for i in cls)), value)

    @property
    def unit(self) -> str:
        """What a value counts, in Polish: the wage is a monthly one (the mean of the year),
        the dwellings a sum of 12 months (tests/contract/api/dto/test_gov_map_stats_dto.py)."""
        return _UNITS[self]


_UNITS = {
    Indicator.UNEMPLOYMENT_RATE: "%",
    Indicator.AVERAGE_WAGE: "PLN/mies.",
    Indicator.DWELLINGS_COMPLETED: "mieszkania (suma 12 miesięcy)",
    Indicator.DWELLINGS_STARTED: "mieszkania (suma 12 miesięcy)",
    Indicator.AVERAGE_DWELLING_AREA: "m²",
    Indicator.NATURAL_INCREASE: "osoby",
    Indicator.NBP_PRICE_PER_M2: "PLN/m²",
}


@dataclass(frozen=True, kw_only=True)
class CityIndicator:
    """One city's value of an indicator; ``None``: the service has none for it."""

    city_slug: str
    name: str
    value: float | None


@dataclass(frozen=True, kw_only=True)
class IndicatorValues:
    """Every city's value of one indicator, for one period.

    ``period``: a label of ``models.government_statistics`` (``2026-08``, ``2026-Q2``,
    ``2025``), ``None`` when the service's cannot be read. ``section``: where a city's page
    of government statistics shows the indicator, an opaque identity for
    ``ports.RankingLinks`` (``StatisticsTable.section``); ``None`` when there is none.
    """

    indicator: Indicator
    period: str | None
    cities: tuple[CityIndicator, ...]
    section: str | None = None


@dataclass(frozen=True)
class IndicatorCriteria:
    """Which indicator to rank by, in which order and how many cities."""

    indicator: Indicator
    order: RankingOrder = RankingOrder.VALUE_DESC
    limit: RankingLimit = field(default_factory=RankingLimit)

    def __post_init__(self) -> None:
        if not self.order.by_value:
            raise ValueError(f"{self.order}: wskaźnik porządkuje tylko value_desc albo value_asc")


@dataclass(frozen=True)
class IndicatorRanking:
    """The first cities by an indicator and how many there were (D4: the cut is explicit)."""

    criteria: IndicatorCriteria
    period: str | None
    items: tuple[CityIndicator, ...]
    total: int
    """Cities with a value, before the cut to ``limit``."""
    left_out: int
    """Cities without a value."""

    @classmethod
    def of(cls, criteria: IndicatorCriteria, values: IndicatorValues) -> "IndicatorRanking":
        """Ties go to the name; a city without a value is left out, never ranked as 0."""
        if values.indicator is not criteria.indicator:
            raise ValueError(f"wartości {values.indicator}, a ranking {criteria.indicator}")
        sign = -1 if criteria.order is RankingOrder.VALUE_DESC else 1
        known = [(city, city.value) for city in values.cities if city.value is not None]
        ranked = [
            city for city, _ in sorted(known, key=lambda pair: (sign * pair[1], pair[0].name))
        ]
        return cls(
            criteria,
            values.period,
            tuple(ranked[: criteria.limit.value]),
            len(ranked),
            len(values.cities) - len(ranked),
        )

    @property
    def returned(self) -> int:
        return len(self.items)

    @property
    def truncated(self) -> bool:
        """More cities have a value than shown."""
        return self.total > self.returned
