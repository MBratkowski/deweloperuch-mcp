"""``InvestmentsApi``: the investments of the service, the ``InvestmentCatalog`` port.

- an investment with its offers: ``GET /api/map/investments/visible/{slug}`` [P];
- the price events of every offer of an investment:
  ``GET /api/investments/{investId}/sale-events`` [P].
"""

from collections.abc import Mapping

from deweloperuch_mcp.api.dto.investment_dto import InvestmentDto
from deweloperuch_mcp.api.dto.investment_sale_events_dto import InvestmentSaleEventsDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.investment import Investment
from deweloperuch_mcp.models.price_history import PriceEvent
from deweloperuch_mcp.models.values import InvestmentSlug


class InvestmentsApi:
    """``usecases.ports.InvestmentCatalog`` of the service; ``visible_investment`` and
    ``investment_sale_events`` are its resources as the service sends them (DTOs)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def investment(self, slug: InvestmentSlug) -> Investment:
        return self.visible_investment(slug.value).to_model()

    def price_events_of_offers(
        self, investment: Investment
    ) -> Mapping[int, tuple[PriceEvent, ...]]:
        return self.investment_sale_events(investment.investment_id).to_model()

    def visible_investment(self, slug: str) -> InvestmentDto:
        """``GET /api/map/investments/visible/{slug}`` [P]: an investment with all its
        offers."""
        target = f"/api/map/investments/visible/{HttpClient.segment(slug)}"
        return JsonEndpoint(self._http, target).get(InvestmentDto)

    def investment_sale_events(self, invest_id: int) -> InvestmentSaleEventsDto:
        """``GET /api/investments/{investId}/sale-events`` [P]: the events of every offer."""
        target = f"/api/investments/{int(invest_id)}/sale-events"
        return JsonEndpoint(self._http, target).get(InvestmentSaleEventsDto)
