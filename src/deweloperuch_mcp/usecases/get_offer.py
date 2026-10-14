"""Use case ``GetOffer`` (D17 reference): one offer of an investment with its full price
history and what the history says as of today."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.errors import NotFoundError
from deweloperuch_mcp.models.investment import OfferDetail
from deweloperuch_mcp.models.price_history import PriceFlags
from deweloperuch_mcp.models.values import InvestmentSlug, OfferId
from deweloperuch_mcp.usecases.ports import Clock, InvestmentCatalog, OfferCatalog, PageLinks
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs
from deweloperuch_mcp.usecases.support.investment_lookup import InvestmentLookup


@dataclass(frozen=True, kw_only=True)
class GetOfferRequest:
    """The offer and its investment, checked (``parse``) before anything is sent."""

    offer_id: OfferId
    investment_slug: InvestmentSlug

    @classmethod
    def parse(cls, *, offer_id: object, investment_slug: object) -> Self:
        """Checked in this order: the offer, the investment. A refusal names the parameter
        (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(
                offer_id=OfferId.parse(offer_id),
                investment_slug=InvestmentSlug.parse(investment_slug),
            )


@dataclass(frozen=True, kw_only=True)
class GetOfferResult:
    """One offer with its history and what it says as of today (``price_flags``), and the
    pages of its investment and developer (D12)."""

    detail: OfferDetail
    investment_url: str | None
    developer_url: str | None
    price_flags: PriceFlags | None


class GetOffer:
    """An offer of an investment with its full price history and its price flags as of
    ``clock``'s today. The investment is required: the service has no confirmed way from
    an offer id to its investment (T1)."""

    def __init__(
        self,
        investments: InvestmentCatalog,
        offers: OfferCatalog,
        links: PageLinks,
        clock: Clock,
    ) -> None:
        self._investments = InvestmentLookup(investments)
        self._offers = offers
        self._links = links
        self._clock = clock

    def execute(self, request: GetOfferRequest) -> GetOfferResult:
        investment = self._investments.investment(request.investment_slug)
        offer = investment.find_offer(request.offer_id)
        if offer is None:
            raise NotFoundError(self._no_such_offer(request))
        with ReportedAs(
            f"Historia ceny oferty {request.offer_id.value}",
            not_found=self._no_history(request),
        ):
            events = self._offers.price_events(request.offer_id)
        offer = offer.with_price_events(events)
        return GetOfferResult(
            detail=OfferDetail(offer=offer, investment=investment),
            investment_url=self._links.investment(investment.ref),
            developer_url=self._links.developer(investment.ref),
            price_flags=offer.price_flags(self._clock.today()),
        )

    @staticmethod
    def _no_such_offer(request: GetOfferRequest) -> str:
        return (
            f"Inwestycja {request.investment_slug.value!r} nie ma oferty {request.offer_id.value}. "
            "Sprawdź offer_id i investment_slug (oba podaje search_offers); wszystkie oferty "
            "inwestycji zwraca get_investment."
        )

    @staticmethod
    def _no_history(request: GetOfferRequest) -> str:
        return (
            f"Serwis nie ma historii ceny oferty {request.offer_id.value} z inwestycji "
            f"{request.investment_slug.value!r}. Sprawdź offer_id i investment_slug (oba podaje "
            "search_offers); ofertę bez historii pokazuje get_investment."
        )
