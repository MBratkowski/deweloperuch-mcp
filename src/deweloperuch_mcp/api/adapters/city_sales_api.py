"""``CitySalesApi``: every active offer of a city, the ``CityOffersSource`` port (D15):
``GET /api/offers/city-sales/{citySlug}`` [P]."""

from deweloperuch_mcp.api.dto.city_sales_dto import CitySalesDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import NOT_FOUND, HttpClient
from deweloperuch_mcp.models.market_statistics import CityOffers
from deweloperuch_mcp.models.values import CitySlug

# [P 2026-10-10] docs/discovery/endpoints.md: `polska` gives HTTP 400 {"error":"Invalid
# citySlug"}. An unknown city is [H]: a 400 like `polska`, a 404, or a 200 without offers.
# 400 and 404 both mean the service does not know the city; a 200 is read as it is.
CITY_SALES_UNKNOWN = (400, NOT_FOUND)


class CitySalesApi:
    """``usecases.ports.CityOffersSource`` of the service; ``city_sales`` is its resource as
    the service sends it (DTO)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def city_offers(self, city: CitySlug) -> CityOffers:
        return self.city_sales(city.value).to_model(city)

    def city_sales(self, city_slug: str) -> CitySalesDto:
        """``GET /api/offers/city-sales/{citySlug}`` [P]: every active offer of a city,
        compact (Warsaw about 1.3 MB). A documented read channel, not a dump of
        ``DUMP_PATHS`` (D15); only the domain's aggregates leave the process."""
        target = f"/api/offers/city-sales/{HttpClient.segment(city_slug)}"
        return JsonEndpoint(self._http, target, unknown=CITY_SALES_UNKNOWN).get(CitySalesDto)
