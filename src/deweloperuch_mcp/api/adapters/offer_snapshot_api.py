"""``OfferSnapshotApi``: every active offer of a city, the ``CityOffersSource`` port (D20):
``GET /api/map/offer-snapshot/{citySlug}`` [P 2026-10-31]."""

from deweloperuch_mcp.api.dto.offer_snapshot_dto import OfferSnapshotDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError
from deweloperuch_mcp.models.market_statistics import CityOffers
from deweloperuch_mcp.models.values import CitySlug

# An internal route of the service's UI (D21), not a published API: the 2.0 client reads it
# for its statistics page [P z kodu 2026-10-30], so it may change without notice. A removed
# route (the HTML 404 page) or a redirect reads as a changed service, never as an unknown
# city (the transport, D21). docs/discovery/endpoints.md section 2 [P 2026-10-31]:
# - every active offer of the city, and only active ones (Warszawa: 11,672, the `totalCount`
#   of the city's offer list the same day);
# - `citySlug` is the slug asked for (sopot, warszawa): a snapshot of another city is a
#   changed service, never the market of the city asked for;
# - an unknown city is a 404 JSON `{"error":"Unknown city"}` (section 9): the default
#   "unknown" answer of `JsonEndpoint`;
# - requested for sopot and warszawa only; that other cities have the same shape is [W],
#   which the live suite checks on krakow (tests/e2e/test_live_mcp.py, the market tests);
# - `polska` was never requested and is never sent: the use case refuses it first (D20).


class OfferSnapshotApi:
    """``usecases.ports.CityOffersSource`` of the service; ``offer_snapshot`` is its
    resource as the service sends it (DTO)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def city_offers(self, city: CitySlug) -> CityOffers:
        snapshot = self.offer_snapshot(city.value)
        if snapshot.citySlug != city.value:
            raise UnexpectedResponseError(
                f"Serwis zwrócił oferty innego miasta niż żądane. {SERVICE_CHANGED}",
                detail=f"{self._path(city.value)}: citySlug {snapshot.citySlug[:60]!r}",
            )
        return snapshot.to_model(city)

    def offer_snapshot(self, city_slug: str) -> OfferSnapshotDto:
        """``GET /api/map/offer-snapshot/{citySlug}``: every active offer of a city in
        compact rows (Warszawa about 0.5 MB). A documented read channel, not a dump of
        ``DUMP_PATHS`` (D20); only the domain's aggregates leave the process."""
        return JsonEndpoint(self._http, self._path(city_slug)).get(OfferSnapshotDto)

    @staticmethod
    def _path(city_slug: str) -> str:
        return f"/api/map/offer-snapshot/{HttpClient.segment(city_slug)}"
