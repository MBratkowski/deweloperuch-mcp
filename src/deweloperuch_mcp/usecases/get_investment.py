"""Use case ``GetInvestment``: an investment with its developer and offers."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.errors import TrueOrFalse, ValueName
from deweloperuch_mcp.models.investment import OfferListing
from deweloperuch_mcp.models.values import InvestmentSlug, OffersLimit
from deweloperuch_mcp.usecases.ports import InvestmentCatalog, PageLinks
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs
from deweloperuch_mcp.usecases.support.investment_lookup import InvestmentLookup


@dataclass(frozen=True, kw_only=True)
class GetInvestmentRequest:
    """The investment and how much of it to show, checked (``parse``) before anything is
    sent."""

    investment_slug: InvestmentSlug
    include_history: bool = False
    limit: OffersLimit | None = None
    """At most this many offers; ``None``: all of them."""

    @classmethod
    def parse(
        cls, *, investment_slug: object, include_history: object = False, limit: object = None
    ) -> Self:
        """Checked in this order: the investment, the history, the limit. A refusal names
        the parameter (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(
                investment_slug=InvestmentSlug.parse(investment_slug),
                include_history=TrueOrFalse().check(ValueName.HISTORY, include_history),
                limit=OffersLimit.parse(limit),
            )


@dataclass(frozen=True, kw_only=True)
class GetInvestmentResult:
    """The investment as a result shows it, with the pages of the investment and of its
    developer (D12)."""

    listing: OfferListing
    investment_url: str | None
    developer_url: str | None


class GetInvestment:
    """Active offers first, at most ``limit`` (``Investment.listing``); with the price
    history of every offer kept when asked (one more request)."""

    def __init__(self, catalog: InvestmentCatalog, links: PageLinks) -> None:
        self._investments = InvestmentLookup(catalog)
        self._catalog = catalog
        self._links = links

    def execute(self, request: GetInvestmentRequest) -> GetInvestmentResult:
        investment = self._investments.investment(request.investment_slug)
        listing = investment.listing(request.limit)
        if request.include_history:
            with ReportedAs(
                f"Historia cen inwestycji {request.investment_slug.value!r}",
                not_found=self._no_histories(request),
            ):
                events = self._catalog.price_events_of_offers(investment)
            listing = listing.with_price_events(events)
        return GetInvestmentResult(
            listing=listing,
            investment_url=self._links.investment(investment.ref),
            developer_url=self._links.developer(investment.ref),
        )

    @staticmethod
    def _no_histories(request: GetInvestmentRequest) -> str:
        return (
            f"Serwis nie ma historii cen ofert inwestycji {request.investment_slug.value!r}. "
            "Pobierz inwestycję bez include_history, a historię pojedynczej oferty przez "
            "get_offer."
        )
