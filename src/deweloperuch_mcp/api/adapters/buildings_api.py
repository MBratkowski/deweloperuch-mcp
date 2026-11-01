"""``BuildingsApi``: buildings of the price register (RCN), the ``BuildingCatalog`` port.

- a building with every unit and its transactions:
  ``GET /api/map/transactions/visible/{investRcnSlug}`` [P] (sample ``api.tx_visible``);
- the trend around it: ``GET /api/avg-price-trend/building/{investRcnId}`` [P] (sample
  ``api.avg_trend_building``), by the building's number: a slug gives 400 [P].

Flats only: ``?type=house`` is never sent (what a house's slug gives without it is not
known).
"""

from functools import partial

from deweloperuch_mcp.api.dto.building_dto import BuildingDto
from deweloperuch_mcp.api.dto.building_trend_dto import BuildingTrendDto
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.http.json_endpoint import JSON_HEADERS, JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient, Reply
from deweloperuch_mcp.models.building import Building, BuildingSlug, NeighbourhoodTrend
from deweloperuch_mcp.models.errors import NotFoundError


class BuildingsApi:
    """``usecases.ports.BuildingCatalog`` of the service; ``visible_building`` and
    ``building_trend`` are its resources as the service sends them (DTOs)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def building(self, slug: BuildingSlug) -> Building:
        return self.visible_building(slug.value).to_model()

    def neighbourhood_trend(self, building: Building) -> NeighbourhoodTrend:
        return self.building_trend(building.building_id).to_model()

    def visible_building(self, slug: str) -> BuildingDto:
        """``GET /api/map/transactions/visible/{investRcnSlug}`` [P]: the building with every
        unit and transaction."""
        target = f"/api/map/transactions/visible/{HttpClient.segment(slug)}"
        return self._http.get(target, headers=JSON_HEADERS, decode=partial(self._building, target))

    def building_trend(self, building_id: int) -> BuildingTrendDto:
        """``GET /api/avg-price-trend/building/{investRcnId}`` [P]: the trend around it."""
        target = f"/api/avg-price-trend/building/{int(building_id)}"
        return JsonEndpoint(self._http, target).get(BuildingTrendDto)

    @staticmethod
    def _building(target: str, reply: Reply) -> BuildingDto:
        data = JsonEndpoint.body(reply, target)
        # [P 2026-10-30] docs/discovery/endpoints.md section 9: the service answers an
        # unknown slug with a JSON 404, {"error":"Investment not found"}, which the transport
        # turns into NotFoundError before this decoder runs. [W] a defence kept from before
        # that answer was known: a 200 with null, or with an error object and no building,
        # was never seen; it still reads as an unknown building, not as a changed service
        # (tests/unit/api/adapters/test_buildings_api.py).
        if data is None or (isinstance(data, dict) and "error" in data and "slug" not in data):
            raise NotFoundError(
                "Serwis nie zna takiego budynku.", detail=f"{target}: 200 bez budynku"
            )
        return Dto.validated(BuildingDto, data, target)
