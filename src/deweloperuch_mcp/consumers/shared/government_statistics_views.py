"""The view of the government statistics (GUS, NBP): what ``get_government_statistics``
shows, for the CLI (``--json``) and the MCP presenter, built from the use case's result
(``from_result``)."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.government_statistics import Dataset, Frequency, TimeSeries
from deweloperuch_mcp.usecases.get_government_statistics import GetGovernmentStatisticsResult


@dataclass(frozen=True)
class GovernmentStatisticsView:
    """The latest periods of one dataset for one location (D4: the cut is explicit).

    The CLI's ``--json`` prints it with ``dataclasses.asdict``, in this field order.
    """

    location_slug: str
    location_name: str
    dataset: Dataset
    title: str
    source: str
    frequency: Frequency
    total: int
    """Periods the service has for this dataset and location."""
    returned: int
    truncated: bool
    """Older periods exist than the ones shown."""
    available_from: str
    """The oldest period the service has."""
    hint: str | None
    note: str | None
    """A caveat about the data, e.g. a last quarter that holds only some of its months."""
    stats_url: str | None
    """The section of the service's page with this data (D12), for people."""
    series: tuple[TimeSeries, ...]

    @property
    def periods(self) -> tuple[str, ...]:
        return self.series[0].periods

    @classmethod
    def from_result(cls, found: GetGovernmentStatisticsResult) -> Self:
        result = found.statistics
        return cls(
            location_slug=result.location_slug,
            location_name=result.location_name,
            dataset=result.dataset,
            title=result.title,
            source=result.source,
            frequency=result.frequency,
            total=result.total,
            returned=result.returned,
            truncated=result.truncated,
            available_from=result.available_from,
            hint=found.hint,
            note=result.note,
            stats_url=found.stats_url,
            series=result.series,
        )
