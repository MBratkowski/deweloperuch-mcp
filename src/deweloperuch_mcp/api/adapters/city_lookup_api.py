"""``CityLookupApi``: a place by its slug, the ``PlaceDirectory`` port.

- ``GET /api/city-lookup?slug=&source=transactions`` [P 2026-10-30, P 2026-11-01]
  (docs/discovery/endpoints.md, ``city-lookup``; ``CityLookupDto``). Always with
  ``source=transactions``: the transactions dictionary is the wider one (villages too),
  and without ``source`` the offers dictionary makes a name of a slug it does not hold
  (``ignatki-osiedle`` -> ``Ignatki-Osiedle``), so its answer proves nothing [P 2026-11-01].
- The route answers an unknown place with a 200 and null fields, so a 404 of any kind is
  no answer of it: a changed service (D21), never "not found".
"""

# [W] docs/discovery/endpoints.md, `cities` and `city-lookup`: the transactions dictionary is
# taken for a superset of the places the tools know (the offers dictionary's included), so
# "no such place" there means no place the tools could have data for. Seen only so far as
# the samples go: the offers dictionary's `krak` matches that both samples show (Kraków,
# Krakowiany) are in the transactions one with the same slugs (api.cities_q,
# api.cities_q.transactions; tests/contract/api/dto/test_city_lookup_dto.py). The tools'
# message for a place not found therefore still covers a slug from search_locations.

from deweloperuch_mcp.api.dto.city_lookup_dto import CityLookupDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.place import Place
from deweloperuch_mcp.models.values import Slug


class CityLookupApi:
    """``usecases.ports.PlaceDirectory`` of the service; ``place_of_slug`` is its resource
    as the service sends it (DTO)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def lookup(self, slug: Slug) -> Place | None:
        return self.place_of_slug(slug.value).to_model()

    def place_of_slug(self, slug: str) -> CityLookupDto:
        """``GET /api/city-lookup?slug=&source=transactions``: the place of ``slug``."""
        target = HttpClient.target("/api/city-lookup", [("slug", slug), ("source", "transactions")])
        return JsonEndpoint(self._http, target, unknown=()).get(CityLookupDto)
