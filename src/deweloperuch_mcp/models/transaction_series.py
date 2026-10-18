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
Nieruchomości, RCN), which the service republishes; only flats here. They reach the
register late, so the newest periods of a series have too few of them: ``latest`` flags
those as ``incomplete`` and names the newest period with a usual number of transactions
(``last_complete_period``); see ``INCOMPLETE_SHARE`` for the rule.
"""

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import ClassVar, Self

from deweloperuch_mcp.models.errors import InvalidValueError, NotFoundError, OneOf, ValueName
from deweloperuch_mcp.models.government_statistics import Frequency, PeriodCount
from deweloperuch_mcp.models.market_statistics import Spread
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

    @property
    def reference_periods(self) -> int:
        """How many periods right before a period tell its usual number of transactions:
        the year before it (``TransactionSeries.latest``)."""
        return 12 if self is Granularity.MONTH else 4

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
            "transakcji i mniej pewne ceny. Nie porównuj ich z okresami o zwykłej liczbie "
            "transakcji."
        )


# --- incomplete periods -----------------------------------------------------------------------

# [W] tests/fixtures/api/monthly_tx_warszawa_20261015.json (Warsaw, 2026-10-15): after a
# year of 1,069..1,390 transactions a month, 2026-04 has 987, 2026-05 22, 2026-06 0 and
# 2026-07 35 (its median price per m² 33,176, about twice the usual); 2026-04 had 29 on
# 2026-10-13. The quarters (avg_trend_city_warszawa_20261016.json) end the same way:
# 2026-Q2 1,034 and 2026-Q3 37 after about 3,700. How long the register keeps adding to a
# period is open (T46), so the rule reads only the counts. The incomplete periods are the
# longest run at the end of the series lying entirely below INCOMPLETE_SHARE of the usual
# number of transactions right before the run (the median of the reference_periods before
# it): a dip inside the series is never one, and a long tail is judged against the year
# before it, not against its own low periods. The run is at most one reference window
# long, so a lasting drop of the market, once older than that, is not taken for the lag.
# The period right before the run is the last complete one when it is judged usual
# itself; it may still grow (a usual number of transactions, not final data).

INCOMPLETE_SHARE = 0.5
"""A run of periods at the end of a series with fewer transactions than this share of the
usual number is incomplete."""

MIN_REFERENCE_PERIODS = 3
"""Fewest periods the usual number is taken from: with fewer (the start of a series), one
or two periods would decide it, and nothing is judged."""

# [W] the floor: with a usual number of a few transactions a period, chance alone puts a
# period below half of it. A Poisson simulation in the review of 2026-10-16 had the rule
# name a wrong last complete period in 85% of runs at 0.5 transactions a month, 31% at 1
# and 6% at 3; tests/fixtures/api/monthly_tx_karpacz_20261016.json (a small town) has a
# median of 1 a month and 26 months of 60 without any.
MIN_USUAL_TRANSACTIONS = 10
"""Below this usual number of transactions a period is not judged: nothing is flagged,
and no period is known to be complete."""


# --- periods and series -----------------------------------------------------------------------


@dataclass(frozen=True)
class TransactionPeriod:
    """The transactions of one period: how many there were and what they cost.

    ``median_*`` and ``average_*`` of the period's transactions: the price of one m²,
    the area and the price of the flat. Any of them may be ``None``; one that is given is
    above 0, and a period without transactions has none (``measures``). ``incomplete``:
    a period at the end of its series with too few transactions yet (set by
    ``TransactionSeries.latest``).
    """

    period: str
    transactions: int
    median_price_per_m2: float | None = None
    average_price_per_m2: float | None = None
    median_area_m2: float | None = None
    average_area_m2: float | None = None
    median_price: float | None = None
    average_price: float | None = None
    incomplete: bool = False

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
    last_complete_period: str | None
    """The newest period judged to have a usual number of transactions, shown or not;
    ``None`` when none could be (too little history, or too few transactions)."""
    few_transactions: bool
    """Too few transactions a period to judge the newest ones (``MIN_USUAL_TRANSACTIONS``):
    none is flagged, though they may be incomplete, and prices of a few transactions are
    chance."""
    note: str
    """The caveat about the latest periods (``Granularity.lag_note``)."""
    periods: tuple[TransactionPeriod, ...]
    """With ``incomplete`` set, judged on every period of the series."""


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
        """The last ``count`` periods, the incomplete ones flagged; ``NotFoundError`` when
        there is none at all. The flags come from the whole series, so a period shown
        alone is still judged against the periods before it. The last complete period is
        the one right before the incomplete ones (or the newest) when it is judged usual
        itself."""
        if not self.periods:
            raise NotFoundError(
                f"Serwis nie ma transakcji mieszkań dla miasta {self.city.value!r}."
            )
        start = self._incomplete_from()
        flagged = tuple(
            replace(item, incomplete=index >= start) for index, item in enumerate(self.periods)
        )
        shown = flagged[-count.value :]
        last = start - 1  # right before the incomplete periods; the newest when none is
        return TransactionStatistics(
            city_slug=self.city.value,
            granularity=self.granularity,
            total=len(self.periods),
            returned=len(shown),
            truncated=len(shown) < len(self.periods),
            available_from=self.periods[0].period,
            last_complete_period=self.periods[last].period if self._is_usual(last) else None,
            few_transactions=start == len(self.periods) and self._too_few(last),
            note=self.granularity.lag_note(),
            periods=shown,
        )

    def _incomplete_from(self) -> int:
        """Where the incomplete periods at the end start: the earliest start, at most one
        reference window back, from which every period is below the limit right before
        it; the number of periods when there is none. The rule: the comment above
        ``INCOMPLETE_SHARE``."""
        end = len(self.periods)
        counts = [item.transactions for item in self.periods]
        for first in range(max(0, end - self.granularity.reference_periods), end):
            limit = self._limit(first)
            if limit is not None and all(count < limit for count in counts[first:]):
                return first
        return end

    def _is_usual(self, index: int) -> bool:
        """The period at ``index`` is judged, and has at least its limit."""
        limit = self._limit(index)
        return limit is not None and self.periods[index].transactions >= limit

    def _too_few(self, index: int) -> bool:
        """The period at ``index`` has the history to be judged, but too few transactions
        (no limit, ``_limit``)."""
        return self._usual(index) is not None and self._limit(index) is None

    def _limit(self, index: int) -> float | None:
        """Fewer transactions than this make the period at ``index`` incomplete: a share
        of its usual number; ``None`` when it is not judged (too little history, or a usual
        number below ``MIN_USUAL_TRANSACTIONS``)."""
        usual = self._usual(index)
        if usual is None or usual < MIN_USUAL_TRANSACTIONS:
            return None
        return INCOMPLETE_SHARE * usual

    def _usual(self, index: int) -> float | None:
        """The usual number of transactions of the period at ``index``: the median count
        of the ``reference_periods`` right before it; ``None`` with fewer than
        ``MIN_REFERENCE_PERIODS`` of them."""
        window = self.granularity.reference_periods
        before = sorted(item.transactions for item in self.periods[max(0, index - window) : index])
        if len(before) < MIN_REFERENCE_PERIODS:
            return None
        return Spread.quantile(before, 0.5)  # q=0.5: the median

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
