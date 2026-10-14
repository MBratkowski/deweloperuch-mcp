"""``TransactionSeries``: prices of RCN transactions of a city over time (D3, D13, D17).

Plain Python: frozen dataclasses and enums, no I/O, no pydantic, no backend names. The
periods come through the port ``usecases.ports.TransactionStatisticsSource``: every period
the service has for one city at one granularity; this module says what they mean and
how a result is cut (D4)::

    city = TransactionCity.parse("warszawa")       # InvalidInputError if not a city slug
    granularity = Granularity.parse("month")       # InvalidInputError if unknown
    series = source.transaction_series(city, granularity)
    result = series.latest(PeriodCount.parse(12))  # NotFoundError when it has no periods

Periods are labelled as in the government statistics (``statistics.Frequency``):
``2025-08`` (month), ``2025-Q3`` (quarter). Prices are in PLN, areas in m²; ``None`` is a
measure the service does not give for that period (or at that granularity).

The transactions are those of the national register of property prices (Rejestr Cen
Nieruchomości, RCN), which the service republishes; only flats here.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Self

from deweloperuch_mcp.models.errors import InvalidValueError, NotFoundError, OneOf, ValueName
from deweloperuch_mcp.models.government_statistics import Frequency, PeriodCount
from deweloperuch_mcp.models.values import WHOLE_COUNTRY, Slug

# --- value objects ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransactionCity(Slug):
    """The city of transaction statistics: a city slug, never the whole country.

    Whether the service has these statistics for ``polska`` is not known (only city
    slugs were ever asked for, docs/discovery/endpoints.md), so it is refused here
    rather than guessed.
    """

    NAME: ClassVar[ValueName] = ValueName.TRANSACTIONS_CITY

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.value == WHOLE_COUNTRY:
            raise self.refused(self.value)

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


class Granularity(StrEnum):
    """How long one period of the statistics is."""

    MONTH = "month"
    QUARTER = "quarter"

    @classmethod
    def parse(cls, value: object) -> "Granularity":
        """A ``Granularity`` or its value (spaces around it ignored)."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str) and value.strip() in cls._value2member_map_:
            return cls(value.strip())
        raise InvalidValueError(ValueName.GRANULARITY, OneOf(tuple(g.value for g in cls)), value)

    @property
    def frequency(self) -> Frequency:
        """The same periods as the government statistics label them."""
        return Frequency(self.value)

    def lag_note(self) -> str:
        """What every result says about its latest periods.

        [P] docs/discovery/endpoints.md, monthly transaction statistics: the latest months
        have few transactions (RCN feed lag; 2026-07 had 2 transactions on 2026-10-09).
        [W] "kilkumiesięcznym": the service's own statistics page took 2026-03 as its
        latest full month on 2026-10-09 (sample page.stats_transactions, ``latestSummary``).
        """
        latest = "Ostatnie miesiące" if self is Granularity.MONTH else "Ostatnie kwartały"
        return (
            f"{latest} są niepełne: transakcje trafiają do Rejestru Cen Nieruchomości z "
            "kilkumiesięcznym opóźnieniem, więc najnowsze okresy mają zaniżoną liczbę "
            "transakcji i mniej pewne ceny. Nie porównuj ich z pełnymi okresami."
        )


# --- periods and series -----------------------------------------------------------------------


@dataclass(frozen=True)
class TransactionPeriod:
    """The transactions of one period: how many there were and what they cost.

    ``median_*`` and ``average_*`` of the period's transactions: the price of one m²,
    the area and the price of the flat. Any of them may be ``None``; one that is given is
    above 0, and a period without transactions has none (``measures``).
    """

    period: str
    transactions: int
    median_price_per_m2: float | None = None
    average_price_per_m2: float | None = None
    median_area_m2: float | None = None
    average_area_m2: float | None = None
    median_price: float | None = None
    average_price: float | None = None

    @property
    def measures(self) -> tuple[float | None, ...]:
        """Every price and area of the period, in field order."""
        return (
            self.median_price_per_m2,
            self.average_price_per_m2,
            self.median_area_m2,
            self.average_area_m2,
            self.median_price,
            self.average_price,
        )


@dataclass(frozen=True)
class TransactionStatistics:
    """The latest periods of one city (D4: the cut is explicit), oldest first."""

    city_slug: str
    granularity: Granularity
    total: int
    """Periods the service has for the city at this granularity."""
    returned: int
    truncated: bool
    """Older periods exist than the ones shown."""
    available_from: str
    """The oldest period the service has."""
    note: str
    """The caveat about the latest periods (``Granularity.lag_note``)."""
    periods: tuple[TransactionPeriod, ...]


@dataclass(frozen=True)
class TransactionSeries:
    """Every period the service has for one city at one granularity, oldest first.

    Labels match the granularity and grow strictly; counts are not negative; prices and
    areas are above 0, and a period without transactions has none. ``ValueError``
    otherwise: the adapter that read them reports the service's data as inconsistent.
    """

    city: TransactionCity
    granularity: Granularity
    periods: tuple[TransactionPeriod, ...]

    def __post_init__(self) -> None:
        self._check_labels()
        self._check_counts()
        for item in self.periods:
            self._check_measures(item)

    def latest(self, count: PeriodCount) -> TransactionStatistics:
        """The last ``count`` periods; ``NotFoundError`` when there is none at all."""
        if not self.periods:
            raise NotFoundError(
                f"Serwis nie ma transakcji mieszkań dla miasta {self.city.value!r}."
            )
        shown = self.periods[-count.value :]
        return TransactionStatistics(
            city_slug=self.city.value,
            granularity=self.granularity,
            total=len(self.periods),
            returned=len(shown),
            truncated=len(shown) < len(self.periods),
            available_from=self.periods[0].period,
            note=self.granularity.lag_note(),
            periods=shown,
        )

    def _check_labels(self) -> None:
        """Every label is a period of the granularity, and they grow strictly."""
        labels = [item.period for item in self.periods]
        pattern = self.granularity.frequency.label_pattern()
        if not all(pattern.fullmatch(label) for label in labels):
            raise ValueError(f"okresy niezgodne z długością {self.granularity.value}: {labels!r}")
        if any(later <= earlier for earlier, later in zip(labels, labels[1:], strict=False)):
            raise ValueError("okresy nie rosną albo się powtarzają")

    def _check_counts(self) -> None:
        if any(item.transactions < 0 for item in self.periods):
            raise ValueError("ujemna liczba transakcji")

    @staticmethod
    def _check_measures(item: TransactionPeriod) -> None:
        """The measures ``item`` gives are above 0, and only with transactions."""
        given = [value for value in item.measures if value is not None]
        if any(value <= 0 for value in given):
            raise ValueError(f"{item.period}: cena albo metraż nie większe od zera")
        if given and item.transactions == 0:
            raise ValueError(f"{item.period}: ceny bez transakcji")
