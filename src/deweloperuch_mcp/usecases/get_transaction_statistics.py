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
        """Older periods exist than the ones shown: a larger ``periods`` shows them (D4)."""
        statistics = self.statistics
        if not statistics.truncated:
            return None
        return (
            f"Pokazano ostatnie {statistics.returned} z {statistics.total} okresów (dane od "
            f"{statistics.available_from}); starsze pokaże większa wartość periods."
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
