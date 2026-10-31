"""``OffersApi`` (D17 reference): the offers of the service, the ``OfferCatalog`` port.

- the offers search: prop ``initialData`` of ``/ceny-ofertowe/{city}/mieszkania`` (RSC)
  [P], since 2.0 the props ``sales`` and ``serverPaginationData`` [P 2026-10-30]
  (``OffersPageDto.from_props``), the address from ``OffersQuery``;
- the price events of one offer: ``GET /api/sale-events?saleId=`` [P].
"""

from functools import partial

from deweloperuch_mcp.api.dto.offers_page_dto import OFFERS_PROPS, OffersPageDto
from deweloperuch_mcp.api.dto.sale_events_dto import SaleEventsDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.rsc_page import RscPage
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.queries.offers_query import OffersQuery
from deweloperuch_mcp.models.offer import OfferSearchCriteria, OfferSearchPage
from deweloperuch_mcp.models.price_history import PriceEvent
from deweloperuch_mcp.models.values import OfferId


class OffersApi:
    """``usecases.ports.OfferCatalog`` of the service; ``offers_page`` and ``sale_events``
    are its resources as the service sends them (DTOs)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def search(self, criteria: OfferSearchCriteria) -> OfferSearchPage:
        return self.offers_page(OffersQuery(criteria)).to_model()

    def price_events(self, offer_id: OfferId) -> tuple[PriceEvent, ...]:
        return self.sale_events(offer_id.value).to_model()

    def offers_page(self, query: OffersQuery) -> OffersPageDto:
        """The offers list at ``query``'s address: ``initialData``, or the 2.0 props [P]."""
        path = query.path()
        page = RscPage(self._http, path, query.params())
        return page.props(OFFERS_PROPS, partial(OffersPageDto.from_props, path=path))

    def sale_events(self, sale_id: int) -> SaleEventsDto:
        """``GET /api/sale-events?saleId=`` [P]: the price events of one offer."""
        target = HttpClient.target("/api/sale-events", [("saleId", int(sale_id))])
        return JsonEndpoint(self._http, target).get(SaleEventsDto)
