"""``domain.ports.LocationDirectory`` over ``/api/cities`` and ``/api/location-search`` [P].

Each sent with the ``limit`` the UI sends (``CITIES_LIMIT``, ``SUGGESTIONS_LIMIT``); other
values and the parameters ``variant``, ``propertyType`` and ``page`` are not [P].
"""

from deweloperuch_mcp.domain.locations import LocationMatches
from deweloperuch_mcp.domain.values import LocationQuery
from deweloperuch_mcp.infrastructure.deweloperuch import json_api, mappers
from deweloperuch_mcp.infrastructure.deweloperuch.transport import HttpClient

CITIES_LIMIT = 8
"""``limit`` of ``/api/cities`` as the UI sends it [P] (sample ``api.cities_q``)."""
SUGGESTIONS_LIMIT = 6
"""``limit`` of ``/api/location-search`` as the UI sends it [P] (``api.location_search``)."""


class ServiceLocationDirectory:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def cities(self, query: LocationQuery) -> LocationMatches:
        found = json_api.cities(self._http, query.text, CITIES_LIMIT)
        # [W] docs/discovery/endpoints.md, /api/cities: `hasMore` is in the response, but
        # its meaning is a conclusion (pagination is [H], `hasMore: true` never seen).
        return LocationMatches(
            tuple(mappers.location_from_city(city) for city in found.cityMappings),
            more=found.hasMore,
        )

    def districts_and_streets(self, query: LocationQuery) -> LocationMatches:
        found = json_api.location_search(self._http, query.text, SUGGESTIONS_LIMIT)
        # [W] /api/location-search has no such flag: a full page of suggestions may hide
        # more.
        return LocationMatches(
            tuple(mappers.location_from_suggestion(item) for item in found.suggestions),
            more=len(found.suggestions) >= SUGGESTIONS_LIMIT,
        )
