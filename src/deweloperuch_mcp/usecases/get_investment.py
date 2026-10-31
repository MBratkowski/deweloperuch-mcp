"""Use case ``GetInvestment``: an investment with its developer and offers."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.errors import (
    SERVICE_CHANGED,
    TrueOrFalse,
    UnexpectedResponseError,
    ValueName,
)
from deweloperuch_mcp.models.investment import OfferListing
from deweloperuch_mcp.models.values import InvestmentSlug, OffersLimit
from deweloperuch_mcp.usecases.ports import InvestmentCatalog, PageLinks
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs
from deweloperuch_mcp.usecases.support.investment_lookup import InvestmentLookup

_INSTEAD = (
    "Zamiast tego możesz pobrać inwestycję bez include_history albo historię jednej oferty "
    "przez get_offer."
)
"""What to call when only the histories failed: the investment read."""


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
    history of every offer kept when asked, from the same answer of the service (no
    request of its own)."""

    def __init__(self, catalog: InvestmentCatalog, links: PageLinks) -> None:
        self._investments = InvestmentLookup(catalog)
        self._catalog = catalog
        self._links = links

    def execute(self, request: GetInvestmentRequest) -> GetInvestmentResult:
        investment = self._investments.investment(request.investment_slug)
        listing = investment.listing(request.limit)
        if request.include_history:
            listing = self._with_histories(listing, request.investment_slug)
        return GetInvestmentResult(
            listing=listing,
            investment_url=self._links.investment(investment.ref),
            developer_url=self._links.developer(investment.ref),
        )

    def _with_histories(self, listing: OfferListing, slug: InvestmentSlug) -> OfferListing:
        """``listing`` with every offer's history, read after the investment from the same
        answer. A history off the contract, or one that misses an offer kept (another
        answer, read again), fails while the investment read: the message adds what to
        call instead (D12, D21). A not-found or another service error here can only come
        from a second read the cache did not serve, which a call without the history would
        meet too: its message stays as it is."""
        subject = f"Historia cen inwestycji {slug.value!r}"
        try:
            with ReportedAs(subject):
                events = self._catalog.price_events_of_offers(slug)
            return listing.with_price_events(events)
        except UnexpectedResponseError as err:
            raise type(err)(f"{err} {_INSTEAD}", err.pause_seconds, detail=err.detail) from err
        except ValueError as err:  # events that miss an offer kept (OfferListing)
            raise UnexpectedResponseError(
                f"{subject}: dane z serwisu nie mają historii części ofert. {SERVICE_CHANGED} "
                f"{_INSTEAD}",
                detail=str(err),
            ) from err
