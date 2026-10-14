"""Use case ``GetGovernmentStatistics``: the latest periods of a government dataset (GUS,
NBP) for a location."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.government_statistics import (
    DEFAULT_PERIODS,
    Dataset,
    GovernmentStatistics,
    PeriodCount,
)
from deweloperuch_mcp.models.values import LocationSlug
from deweloperuch_mcp.usecases.ports import GovernmentStatisticsSource, PageLinks
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs


@dataclass(frozen=True, kw_only=True)
class GetGovernmentStatisticsRequest:
    """The location, the dataset and how many of its latest periods, checked (``parse``)
    before anything is sent."""

    location: LocationSlug
    dataset: Dataset
    periods: PeriodCount

    @classmethod
    def parse(cls, *, location: object, dataset: object, periods: object = DEFAULT_PERIODS) -> Self:
        """Checked in this order: location, dataset, periods. A refusal names the
        parameter (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(
                location=LocationSlug.parse(location),
                dataset=Dataset.parse(dataset),
                periods=PeriodCount.parse(periods),
            )


@dataclass(frozen=True, kw_only=True)
class GetGovernmentStatisticsResult:
    """The statistics with the section of the service's page that shows them (D12)."""

    statistics: GovernmentStatistics
    stats_url: str | None

    @property
    def hint(self) -> str | None:
        """Older periods exist than the ones shown: a larger ``periods`` shows them (D4);
        ``None`` otherwise."""
        statistics = self.statistics
        if not statistics.truncated:
            return None
        return (
            f"Pokazano ostatnie {statistics.returned} z {statistics.total} okresów (dane od "
            f"{statistics.available_from}); starsze pokaże większa wartość periods."
        )


class GetGovernmentStatistics:
    """One page of the service per location; the domain cuts the result (D4) and says
    what the location does not publish."""

    def __init__(self, source: GovernmentStatisticsSource, links: PageLinks) -> None:
        self._source = source
        self._links = links

    def execute(self, request: GetGovernmentStatisticsRequest) -> GetGovernmentStatisticsResult:
        location = request.location
        with ReportedAs(
            f"Statystyki rządowe dla {location.value!r}",
            not_found=self._unknown_location(location),
        ):
            published = self._source.location_statistics(location, request.dataset)
        statistics = published.statistics(request.dataset, request.periods)
        return GetGovernmentStatisticsResult(
            statistics=statistics,
            stats_url=self._links.government_statistics(location, statistics.section),
        )

    @staticmethod
    def _unknown_location(location: LocationSlug) -> str:
        return (
            f"Serwis nie ma statystyk rządowych dla lokalizacji {location.value!r}. "
            "Podaj polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo slug "
            "miasta na prawach powiatu bez polskich znaków, np. warszawa, krakow. Jeśli nie "
            "znasz sluga miasta, spróbuj city_slug z search_locations (zwykle jest taki "
            "sam, ale nie zawsze, np. dla Jastrzębia-Zdroju użyj jastrzebie). Statystyki "
            "są tylko dla miast na prawach powiatu."
        )
