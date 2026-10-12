"""Use case: an investment with its developer and offers."""

from dataclasses import dataclass

from deweloperuch_mcp.application.failures import reported_as
from deweloperuch_mcp.domain.investments import Investment, OfferListing
from deweloperuch_mcp.domain.ports import InvestmentCatalog, PageLinks
from deweloperuch_mcp.domain.values import InvestmentSlug, OffersLimit


@dataclass(frozen=True)
class FoundInvestment:
    """The investment as a result shows it, with the pages of the investment and of its
    developer (D12)."""

    listing: OfferListing
    investment_url: str | None
    developer_url: str | None


def investment_of(catalog: InvestmentCatalog, slug: InvestmentSlug) -> Investment:
    """The investment, or a ``NotFoundError`` that says where slugs come from."""
    with reported_as(
        f"Inwestycja {slug.value!r}",
        not_found=(
            f"Nie znaleziono inwestycji {slug.value!r}. Slug inwestycji podaje search_offers "
            "(pole investment_slug)."
        ),
    ):
        return catalog.investment(slug)


class GetInvestment:
    """Active offers first, at most ``limit`` (``Investment.listing``); with the price
    history of every offer kept when asked (one more request)."""

    def __init__(self, catalog: InvestmentCatalog, links: PageLinks) -> None:
        self._catalog = catalog
        self._links = links

    def __call__(
        self,
        slug: InvestmentSlug,
        *,
        include_history: bool = False,
        limit: OffersLimit | None = None,
    ) -> FoundInvestment:
        investment = investment_of(self._catalog, slug)
        listing = investment.listing(limit)
        if include_history:
            with reported_as(
                f"Historia cen inwestycji {slug.value!r}",
                not_found=(
                    f"Serwis nie ma historii cen ofert inwestycji {slug.value!r}. Pobierz "
                    "inwestycję bez include_history, a historię pojedynczej oferty przez "
                    "get_offer."
                ),
            ):
                events = self._catalog.price_events_of_offers(investment)
            listing = listing.with_price_events(events)
        return FoundInvestment(
            listing=listing,
            investment_url=self._links.investment(investment.ref),
            developer_url=self._links.developer(investment.ref),
        )
