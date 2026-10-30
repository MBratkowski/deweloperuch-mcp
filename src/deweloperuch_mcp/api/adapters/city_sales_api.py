"""``CitySalesApi``: every active offer of a city, the ``CityOffersSource`` port (D15):
``GET /api/map/offer-snapshot/{citySlug}`` [P 2026-10-30]. Its predecessor
``/api/offers/city-sales/{citySlug}`` answers 404 for every city since the 2.0 build of
2026-10-29."""

from deweloperuch_mcp.api.dto.city_sales_dto import CitySalesDto, OfferSnapshotDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import NOT_FOUND, HttpClient
from deweloperuch_mcp.models.market_statistics import CityOffers
from deweloperuch_mcp.models.values import CitySlug

# [P 2026-10-30] `nieistniejace-miasto` gives HTTP 404 {"error":"Unknown city"}: a JSON
# 404 is an unknown city, an HTML 404 (no such route) a gone data source (``gone``).
SNAPSHOT_UNKNOWN = (NOT_FOUND,)
SNAPSHOT_GONE = (NOT_FOUND,)


class CitySalesApi:
    """``usecases.ports.CityOffersSource`` of the service; ``offer_snapshot`` is its
    resource as the service sends it, read into ``CitySalesDto``."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def city_offers(self, city: CitySlug) -> CityOffers:
        return self.offer_snapshot(city.value).to_model(city)

    def offer_snapshot(self, city_slug: str) -> CitySalesDto:
        """``GET /api/map/offer-snapshot/{citySlug}`` [P 2026-10-30]: every active offer
        of a city as rows of numbers (Wrocław 5,836 offers, 261 KB). A documented read
        channel, not a dump of ``DUMP_PATHS`` (D15); only the domain's aggregates leave
        the process."""
        target = f"/api/map/offer-snapshot/{HttpClient.segment(city_slug)}"
        endpoint = JsonEndpoint(self._http, target, unknown=SNAPSHOT_UNKNOWN, gone=SNAPSHOT_GONE)
        return endpoint.get(OfferSnapshotDto).city_sales(target)
