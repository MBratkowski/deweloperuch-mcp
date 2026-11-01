"""``OffersApi`` (D17 reference): the offers of the service, the ``OfferCatalog`` port.

- the offers search: the props ``sales`` and ``serverPaginationData`` of the offers list of
  a city or of one of its districts (RSC) [P 2026-10-31], the address from
  ``OffersQuery``. Both lists are internal pages of the site's UI (D21): the relaunch of
  2026-10-29 renamed their props without notice, and they may change again;
- the price events of one offer: ``GET /api/sale-events?saleId=`` [P].
"""

from collections.abc import Sequence

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.offers_page_dto import OffersPageDto
from deweloperuch_mcp.api.dto.sale_events_dto import SaleEventsDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.rsc_page import RscPage
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.queries.offers_query import OffersQuery
from deweloperuch_mcp.models.errors import NotFoundError
from deweloperuch_mcp.models.offer import OfferSearchCriteria, OfferSearchPage
from deweloperuch_mcp.models.price_history import PriceEvent
from deweloperuch_mcp.models.values import OfferId

PAGE_PROPS = ("sales", "serverPaginationData")
"""The props of a page of the list [P 2026-10-31]: its offers and its paging."""


class OffersApi:
    """``usecases.ports.OfferCatalog`` of the service; ``offers_page`` and ``sale_events``
    are its resources as the service sends them (DTOs)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def search(self, criteria: OfferSearchCriteria) -> OfferSearchPage:
        """One page of the list ``OffersQuery`` gives for ``criteria``. A district whose
        name gives no slug has no list: ``NotFoundError``, without a request."""
        query = OffersQuery(criteria)
        path = query.path()
        if path is None:
            raise NotFoundError(
                "Serwis nie zna żądanych danych (strona nie istnieje).",
                detail="nazwa dzielnicy bez liter i cyfr, z których serwis tworzy adres listy",
            )
        return self.offers_page(path, query.params()).to_model()

    def price_events(self, offer_id: OfferId) -> tuple[PriceEvent, ...]:
        return self.sale_events(offer_id.value).to_model()

    def offers_page(self, path: str, params: Sequence[tuple[str, str | int]]) -> OffersPageDto:
        """The props ``PAGE_PROPS`` of the list at ``path`` with ``params``, from one request,
        checked as ``OffersPageDto`` inside the transport's decode: a page that does not match
        is never cached (``RscPage.props``).

        A list the service does not know (an unknown city or district) answers 200 with
        Next.js's 404 marker [P 2026-10-31, endpoints.md section 9, "Pages"]: a
        ``NotFoundError`` (``RscPage.props``). Neither list was seen to answer a 404, so no
        404 of theirs is to be read as unknown: it is a changed service (D21).
        """
        source = f"{path} (propsy {', '.join(PAGE_PROPS)})"
        return RscPage(self._http, path, params).props(
            PAGE_PROPS, decode=lambda props: Dto.validated(OffersPageDto, props, source)
        )

    def sale_events(self, sale_id: int) -> SaleEventsDto:
        """``GET /api/sale-events?saleId=`` [P]: the price events of one offer."""
        target = HttpClient.target("/api/sale-events", [("saleId", int(sale_id))])
        return JsonEndpoint(self._http, target).get(SaleEventsDto)
