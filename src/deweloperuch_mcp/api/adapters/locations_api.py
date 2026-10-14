"""``LocationsApi``: the places of the service, the ``LocationDirectory`` port.

- cities by a part of their name: ``GET /api/cities?q=&limit=`` [P];
- districts and streets by a part of their name: ``GET /api/location-search?q=&limit=``
  [P].

Each sent with the ``limit`` the UI sends (``CITIES_LIMIT``, ``SUGGESTIONS_LIMIT``); other
values and the parameters ``variant``, ``propertyType`` and ``page`` are not [P].
"""

from deweloperuch_mcp.api.dto.cities_dto import CitiesDto
from deweloperuch_mcp.api.dto.location_search_dto import LocationSearchDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.location import LocationMatches
from deweloperuch_mcp.models.values import LocationQuery

CITIES_LIMIT = 8
"""``limit`` of ``/api/cities`` as the UI sends it [P] (sample ``api.cities_q``)."""
SUGGESTIONS_LIMIT = 6
"""``limit`` of ``/api/location-search`` as the UI sends it [P] (``api.location_search``)."""


class LocationsApi:
    """``usecases.ports.LocationDirectory`` of the service; ``city_search`` and
    ``location_search`` are its resources as the service sends them (DTOs)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def cities(self, query: LocationQuery) -> LocationMatches:
        return self.city_search(query.text, CITIES_LIMIT).to_model()

    def districts_and_streets(self, query: LocationQuery) -> LocationMatches:
        return self.location_search(query.text, SUGGESTIONS_LIMIT).to_model(SUGGESTIONS_LIMIT)

    def city_search(self, query: str, limit: int) -> CitiesDto:
        """``GET /api/cities?q=&limit=`` [P]: cities whose name contains ``query``."""
        target = HttpClient.target("/api/cities", [("q", query), ("limit", limit)])
        return JsonEndpoint(self._http, target).get(CitiesDto)

    def location_search(self, query: str, limit: int) -> LocationSearchDto:
        """``GET /api/location-search?q=&limit=`` [P]: districts and streets matching
        ``query``."""
        target = HttpClient.target("/api/location-search", [("q", query), ("limit", limit)])
        return JsonEndpoint(self._http, target).get(LocationSearchDto)
