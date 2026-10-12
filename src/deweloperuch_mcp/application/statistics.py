"""Use case: the latest periods of a government dataset (GUS, NBP) for a location."""

from dataclasses import dataclass

from deweloperuch_mcp.application.failures import reported_as
from deweloperuch_mcp.domain.ports import GovernmentStatisticsSource, PageLinks
from deweloperuch_mcp.domain.statistics import Dataset, GovernmentStatistics, PeriodCount
from deweloperuch_mcp.domain.values import LocationSlug


@dataclass(frozen=True)
class FoundStatistics:
    """The statistics with what to do about older periods (``hint``) and the section of
    the service's page that shows them (D12)."""

    statistics: GovernmentStatistics
    hint: str | None
    stats_url: str | None


def statistics_hint(statistics: GovernmentStatistics) -> str | None:
    """Older periods exist than the ones shown: a larger ``periods`` shows them (D4)."""
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

    def __call__(
        self, location: LocationSlug, dataset: Dataset, periods: PeriodCount
    ) -> FoundStatistics:
        with reported_as(
            f"Statystyki rządowe dla {location.value!r}",
            not_found=(
                f"Serwis nie ma statystyk rządowych dla lokalizacji {location.value!r}. "
                "Podaj polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo slug "
                "miasta na prawach powiatu bez polskich znaków, np. warszawa, krakow. Jeśli nie "
                "znasz sluga miasta, spróbuj city_slug z search_locations (zwykle jest taki "
                "sam, ale nie zawsze, np. dla Jastrzębia-Zdroju użyj jastrzebie). Statystyki "
                "są tylko dla miast na prawach powiatu."
            ),
        ):
            published = self._source.location_statistics(location, dataset)
        statistics = published.statistics(dataset, periods)
        return FoundStatistics(
            statistics=statistics,
            hint=statistics_hint(statistics),
            stats_url=self._links.government_statistics(location, statistics.section),
        )
