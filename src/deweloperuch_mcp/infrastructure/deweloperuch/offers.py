"""``domain.ports.OfferCatalog`` and ``InvestmentCatalog`` of the service (D1).

- the offers search: prop ``initialData`` of ``/ceny-ofertowe/{city}/mieszkania`` (RSC)
  [P], the query from ``params.offers_list_query``;
- an investment with its offers: ``/api/map/investments/visible/{slug}`` [P];
- the price events of one offer: ``/api/sale-events?saleId=`` [P]; of every offer of an
  investment: ``/api/investments/{id}/sale-events`` [P].
"""

from collections.abc import Mapping

from deweloperuch_mcp.domain.investments import Investment
from deweloperuch_mcp.domain.offers import OfferSearchCriteria, OfferSearchPage, PriceEvent
from deweloperuch_mcp.domain.values import InvestmentSlug, OfferId
from deweloperuch_mcp.infrastructure.deweloperuch import json_api, mappers, rsc
from deweloperuch_mcp.infrastructure.deweloperuch.params import offers_list_query
from deweloperuch_mcp.infrastructure.deweloperuch.transport import HttpClient


class ServiceOfferCatalog:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def search(self, criteria: OfferSearchCriteria) -> OfferSearchPage:
        page = rsc.offers_list(self._http, criteria.city.value, offers_list_query(criteria))
        return mappers.offer_search_page(page)

    def price_events(self, offer_id: OfferId) -> tuple[PriceEvent, ...]:
        return mappers.price_events(json_api.sale_events(self._http, offer_id.value).events)


class ServiceInvestmentCatalog:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def investment(self, slug: InvestmentSlug) -> Investment:
        return mappers.investment(json_api.investment(self._http, slug.value))

    def price_events_of_offers(
        self, investment: Investment
    ) -> Mapping[int, tuple[PriceEvent, ...]]:
        found = json_api.investment_sale_events(self._http, investment.investment_id)
        return {offer_id: mappers.price_events(events) for offer_id, events in found.root.items()}
