"""``GovernmentStatisticsApi``: the government statistics (GUS, NBP) of a location, the
``GovernmentStatisticsSource`` port: the page ``/statystyki/{location}/dane-rzadowe``
(RSC, D1) [P 2026-10-30], read into ``GovernmentStatsPageDto``. Until the 2.0 build
(2026-10-29) it was ``/statystyki/statystyki-rzadowe/{location}``, which now answers 308."""

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
        """``/statystyki/{location}/dane-rzadowe`` [P 2026-10-30]: ``polska``, an aggregate
        or a city.

        Also the path of the link to these statistics (``links``, D12).
        """
        return f"/statystyki/{HttpClient.segment(location)}/dane-rzadowe"
