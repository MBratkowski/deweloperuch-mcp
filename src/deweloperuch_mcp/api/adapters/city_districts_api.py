"""``CityDistrictsApi``: the districts of a city with offers, the ``DistrictDirectory`` port.

- ``GET /api/city-districts?citySlug=`` [P 2026-11-01] (docs/discovery/endpoints.md, sample
  ``api.city_districts.offers_v2``, raw payload
  tests/fixtures/api/city_districts_warszawa_20261102.json). Sent: ``citySlug`` only, so the
  districts of the offers. Not sent: ``variant=transactions`` (the transactions'
  districts), ``propertyType`` and ``citySlug=all`` (every city at once, size unknown, T67).
"""

from deweloperuch_mcp.api.dto.city_districts_dto import CityDistrictsDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.district import District
from deweloperuch_mcp.models.values import CitySlug


class CityDistrictsApi:
    """``usecases.ports.DistrictDirectory`` of the service; ``city_districts`` is its resource
    as the service sends it (DTO)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def districts(self, city: CitySlug) -> tuple[District, ...]:
        # [W] endpoints.md, city-districts: only Warszawa was requested in the offers variant,
        # and a city the service does not know never was. Its answer is read as either an
        # empty list (no districts) or the JSON 404 of a live route (NotFoundError);
        # tests/unit/api/adapters/test_city_districts_api.py has both, and the use case
        # words its refusal so that it fits an unknown city too.
        return self.city_districts(city.value).to_model()

    def city_districts(self, city_slug: str) -> CityDistrictsDto:
        """``GET /api/city-districts?citySlug=`` [P]: the districts of ``city_slug``."""
        target = HttpClient.target("/api/city-districts", [("citySlug", city_slug)])
        return JsonEndpoint(self._http, target).get(CityDistrictsDto)
