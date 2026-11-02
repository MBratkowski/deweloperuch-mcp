"""``CityIndicatorsApi``: the official indicators of the 66 cities with powiat rights, the
``CityIndicatorSource`` port, over ``/api/statystyki/gov-map-stats`` [P 2026-11-01] (sample
``api.gov_map_stats``), sent without a query (docs/discovery/endpoints.md, section 4).
"""

from deweloperuch_mcp.api.dto.gov_map_stats_dto import GovMapStatsDto
from deweloperuch_mcp.api.dto.place_names_dto import PlaceNamesDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.indicator_ranking import Indicator, IndicatorValues

CITY_INDICATORS = "/api/statystyki/gov-map-stats"


class CityIndicatorsApi:
    """``usecases.ports.CityIndicatorSource`` of the service: one request for all seven
    indicators; the others come from the client's cache within its TTL (D2, D19).
    ``gov_map_stats`` is its resource as the service sends it (DTO); the cities are named
    from the packaged table (``PlaceNamesDto``)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def indicator(self, indicator: Indicator) -> IndicatorValues:
        names = PlaceNamesDto.packaged().to_model()
        return self.gov_map_stats().to_model(indicator, names, path=CITY_INDICATORS)

    def gov_map_stats(self) -> GovMapStatsDto:
        """``GET /api/statystyki/gov-map-stats`` [P 2026-11-01], without a query."""
        return JsonEndpoint(self._http, CITY_INDICATORS).get(GovMapStatsDto)
