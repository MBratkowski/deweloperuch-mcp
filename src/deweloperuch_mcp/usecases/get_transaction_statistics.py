"""Use case ``GetTransactionStatistics``: the latest periods of the RCN transaction prices
of flats in a city, with what to do about older periods and the service's page of them."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.government_statistics import DEFAULT_PERIODS, PeriodCount
from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionCity,
    TransactionStatistics,
)
from deweloperuch_mcp.usecases.ports import TransactionStatisticsLinks, TransactionStatisticsSource
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs


@dataclass(frozen=True, kw_only=True)
class GetTransactionStatisticsRequest:
    """The city, the length of a period and how many periods, checked (``parse``) before
    anything is sent."""

    city: TransactionCity
    granularity: Granularity
    periods: PeriodCount

    @classmethod
    def parse(
        cls,
        *,
        city: object,
        granularity: object = Granularity.MONTH,
        periods: object = DEFAULT_PERIODS,
    ) -> Self:
        """Checked in this order: city, granularity, periods. A refusal names the
        parameter (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(
                city=TransactionCity.parse(city),
                granularity=Granularity.parse(granularity),
                periods=PeriodCount.parse(periods),
            )


@dataclass(frozen=True, kw_only=True)
class GetTransactionStatisticsResult:
    """The statistics with the service's page of them, for people (D12)."""

    statistics: TransactionStatistics
    stats_url: str | None

    @property
    def hint(self) -> str | None:
        """What to do next: older periods exist than the ones shown, so a larger
        ``periods`` shows them (D4); then what the newest periods are worth
        (``latest_periods_hint``)."""
        statistics = self.statistics
        older = None
        if statistics.truncated:
            older = (
                f"Pokazano ostatnie {statistics.returned} z {statistics.total} okresów (dane "
                f"od {statistics.available_from}); starsze pokaże większa wartość periods."
            )
        return " ".join(part for part in (older, self.latest_periods_hint) if part) or None

    @property
    def latest_periods_hint(self) -> str | None:
        """What the newest periods are worth: the incomplete ones shown, not to be read as
        a trend, then the newest period with a usual number of transactions, which may
        still change too (Warsaw's 2026-04 grew from 29 to 987 transactions in two days,
        2026-10-13..15); or, for a series with too few transactions to judge, that any
        of them may be incomplete."""
        statistics = self.statistics
        if statistics.few_transactions:
            return (
                "Transakcji jest za mało, by ocenić, które najnowsze okresy są niepełne: każdy "
                "może jeszcze urosnąć, a ceny z kilku transakcji są przypadkowe; nie wyciągaj "
                "z nich trendu."
            )
        labels = [item.period for item in statistics.periods if item.incomplete]
        if not labels:
            return None
        hint = self._incomplete(labels)
        last = statistics.last_complete_period
        if last is None:
            return hint
        return (
            f"{hint} Ostatni okres ze zwykłą liczbą transakcji: {last} (jego dane też mogą się "
            "jeszcze zmienić)."
        )

    @staticmethod
    def _incomplete(labels: list[str]) -> str:
        """The incomplete periods by name, ``2026-05, 2026-06 i 2026-07``."""
        if len(labels) == 1:
            return (
                f"Okres {labels[0]} ma mniej niż połowę zwykłej liczby transakcji (dane RCN "
                "jeszcze niepełne): nie wyciągaj wniosków z jego cen ani liczby transakcji."
            )
        named = f"{', '.join(labels[:-1])} i {labels[-1]}"
        return (
            f"Okresy {named} mają mniej niż połowę zwykłej liczby transakcji (dane RCN "
            "jeszcze niepełne): nie wyciągaj wniosków z ich cen ani liczby transakcji."
        )


class GetTransactionStatistics:
    """One request per city and granularity; the domain cuts the result (D4)."""

    def __init__(
        self, source: TransactionStatisticsSource, links: TransactionStatisticsLinks
    ) -> None:
        self._source = source
        self._links = links

    def execute(self, request: GetTransactionStatisticsRequest) -> GetTransactionStatisticsResult:
        city = request.city
        with ReportedAs(
            f"Ceny transakcyjne dla {city.value!r}", not_found=self._unknown_city(city)
        ):
            series = self._source.transaction_series(city, request.granularity)
            statistics = series.latest(request.periods)
        return GetTransactionStatisticsResult(
            statistics=statistics, stats_url=self._links.transaction_statistics(city)
        )

    @staticmethod
    def _unknown_city(city: TransactionCity) -> str:
        return (
            f"Serwis nie ma cen transakcyjnych mieszkań dla miasta {city.value!r}. Sprawdź "
            "city_slug w search_locations (np. warszawa, krakow); statystyki są dla całych "
            "miast, nie dla dzielnic ani ulic."
        )
