"""``GovernmentStatisticsApi``: the government statistics (GUS, NBP) of a location, the
``GovernmentStatisticsSource`` port: the page ``/statystyki/statystyki-rzadowe/{location}``
(RSC, D1) [P], read into ``GovernmentStatsPageDto``."""

from functools import partial

from deweloperuch_mcp.api.dto.government_stats_page_dto import GovernmentStatsPageDto
from deweloperuch_mcp.api.http.rsc_page import RscPage
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.government_statistics import Dataset, LocationStatistics
from deweloperuch_mcp.models.values import LocationSlug


class GovernmentStatisticsApi:
    """``usecases.ports.GovernmentStatisticsSource`` of the service: one page request per
    location (the transport's cache answers the next datasets of the same location);
    ``statistics_page`` is its resource as the service sends it (DTO)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def location_statistics(self, location: LocationSlug, dataset: Dataset) -> LocationStatistics:
        page = self.statistics_page(location.value)
        return page.to_model(location, dataset, path=self.path(location.value))

    def statistics_page(self, location: str) -> GovernmentStatsPageDto:
        """The table of contents, the list of locations and every data prop the page has
        (``GovernmentStatsPageDto.from_payload``, with its errors)."""
        path = self.path(location)
        decode = partial(GovernmentStatsPageDto.from_payload, path=path, location=location)
        return RscPage(self._http, path).read(decode)

    @staticmethod
    def path(location: str) -> str:
        """``/statystyki/statystyki-rzadowe/{location}`` [P]: ``polska``, an aggregate or a
        city of the page's list (``sortedLocations``).

        Also the path of the link to these statistics (``links``, D12).
        """
        return f"/statystyki/statystyki-rzadowe/{HttpClient.segment(location)}"
