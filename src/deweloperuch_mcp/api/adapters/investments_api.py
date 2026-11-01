"""``InvestmentsApi``: the investments of the service, the ``InvestmentCatalog`` port.

One route, ``GET /api/map/investments/visible/{slug}`` [P]: an investment with all its
offers and, since the service's 2.0, each offer's price events [P 2026-10-30].
"""

from collections.abc import Mapping

from deweloperuch_mcp.api.dto.investment_dto import InvestmentDto
from deweloperuch_mcp.api.dto.investment_price_events_dto import InvestmentPriceEventsDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.investment import Investment
from deweloperuch_mcp.models.price_history import PriceEvent
from deweloperuch_mcp.models.values import InvestmentSlug


class InvestmentsApi:
    """``usecases.ports.InvestmentCatalog`` of the service; ``visible_investment`` and
    ``visible_price_events`` are its answer as the service sends it (DTOs)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def investment(self, slug: InvestmentSlug) -> Investment:
        return self.visible_investment(slug.value).to_model()

    def price_events_of_offers(self, slug: InvestmentSlug) -> Mapping[int, tuple[PriceEvent, ...]]:
        return self.visible_price_events(slug.value).to_model()

    def visible_investment(self, slug: str) -> InvestmentDto:
        """An investment with all its offers."""
        return JsonEndpoint(self._http, self._visible(slug)).get(InvestmentDto)

    def visible_price_events(self, slug: str) -> InvestmentPriceEventsDto:
        """The events of every offer, from the same answer as ``visible_investment``: the
        same request, so after it the client's cache (D2) serves the answer again and the
        events cost no request of their own. The route sends ``public, max-age=28800,
        s-maxage=3600`` [P 2026-10-30], which the cache keeps; an answer it may not keep
        (``no-store``, ``no-cache``, a freshness of 0) costs one more request, whose answer
        may be a later one with other offers: ``OfferListing.with_price_events`` refuses
        events that miss an offer of the first answer.

        Read apart from the investment, so an answer whose events are off the contract
        fails the events only: ``investment`` stays readable."""
        return JsonEndpoint(self._http, self._visible(slug)).get(InvestmentPriceEventsDto)

    @staticmethod
    def _visible(slug: str) -> str:
        # An internal route of the service's UI (D21): it may change without notice. A
        # removed route (an HTML 404) or a redirect reads as a changed service, never as
        # an unknown investment (JsonEndpoint); an unknown slug is a JSON 404
        # {"error": "Investment not found"} [P 2026-10-30, endpoints.md section 9].
        return f"/api/map/investments/visible/{HttpClient.segment(slug)}"
