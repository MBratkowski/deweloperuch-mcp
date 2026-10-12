"""Use cases: search offers, and one offer with its price history."""

from dataclasses import dataclass

from deweloperuch_mcp.application.failures import reported_as
from deweloperuch_mcp.application.investments import investment_of
from deweloperuch_mcp.domain.errors import NotFoundError
from deweloperuch_mcp.domain.investments import OfferDetail
from deweloperuch_mcp.domain.offers import OfferSearchCriteria, OfferSearchPage
from deweloperuch_mcp.domain.ports import InvestmentCatalog, OfferCatalog, PageLinks
from deweloperuch_mcp.domain.values import BROWSABLE_PAGES, PAGE_SIZES, InvestmentSlug, OfferId


@dataclass(frozen=True)
class FoundOffers:
    """A page of an offers search with what to do next (``hint``) and the links of D12:
    the same list on the service, and the page of each offer's investment (aligned with
    ``page.items``)."""

    page: OfferSearchPage
    hint: str | None
    list_url: str | None
    investment_urls: tuple[str | None, ...]


def offers_hint(page: OfferSearchPage) -> str | None:
    """What to do about a page that does not show every match (D4), an empty search or a
    page past the last one; ``None`` otherwise."""
    if page.truncated:
        larger = page.per_page < max(PAGE_SIZES)
        return (
            f"Pasujących ofert jest {page.total}, a serwis pozwala przejrzeć najwyżej "
            f"{BROWSABLE_PAGES} stron po {page.per_page} ({page.browsable}). Zawęź filtry "
            f"(cena, metraż)" + (f" albo zwiększ per_page do {max(PAGE_SIZES)}." if larger else ".")
        )
    if page.total == 0:
        return (
            "Brak ofert spełniających kryteria. Sprawdź slug miasta (search_locations) "
            "i poluzuj filtry."
        )
    if not page.items:
        return f"Strona {page.page} jest pusta; dostępne strony: 1–{page.pages_available}."
    return None


class SearchOffers:
    """One page of developer offers in a city (or the whole country); the page says how
    much of the result can be browsed at all (D4)."""

    def __init__(self, catalog: OfferCatalog, links: PageLinks) -> None:
        self._catalog = catalog
        self._links = links

    def __call__(self, criteria: OfferSearchCriteria) -> FoundOffers:
        city = criteria.city.value
        with reported_as(
            f"Wyszukiwanie ofert w {city!r}",
            not_found=(
                f"Serwis nie zna miasta {city!r}. Podaj city_slug z search_locations "
                "albo polska (cały kraj)."
            ),
        ):
            page = self._catalog.search(criteria)
        return FoundOffers(
            page=page,
            hint=offers_hint(page),
            list_url=self._links.offers_list(criteria),
            investment_urls=tuple(self._links.investment(item.investment) for item in page.items),
        )


@dataclass(frozen=True)
class FoundOffer:
    """One offer with its history, and the pages of its investment and developer."""

    detail: OfferDetail
    investment_url: str | None
    developer_url: str | None


class GetOffer:
    """An offer of an investment with its full price history. The investment is required:
    the service has no confirmed way from an offer id to its investment (T1)."""

    def __init__(
        self, investments: InvestmentCatalog, offers: OfferCatalog, links: PageLinks
    ) -> None:
        self._investments = investments
        self._offers = offers
        self._links = links

    def __call__(self, offer_id: OfferId, slug: InvestmentSlug) -> FoundOffer:
        investment = investment_of(self._investments, slug)
        offer = investment.find_offer(offer_id)
        oid = offer_id.value
        if offer is None:
            raise NotFoundError(
                f"Inwestycja {slug.value!r} nie ma oferty {oid}. Sprawdź offer_id i "
                "investment_slug (oba podaje search_offers); wszystkie oferty inwestycji "
                "zwraca get_investment."
            )
        with reported_as(
            f"Historia ceny oferty {oid}",
            not_found=(
                f"Serwis nie ma historii ceny oferty {oid} z inwestycji {slug.value!r}. "
                "Sprawdź offer_id i investment_slug (oba podaje search_offers); ofertę bez "
                "historii pokazuje get_investment."
            ),
        ):
            events = self._offers.price_events(offer_id)
        return FoundOffer(
            detail=OfferDetail(offer=offer.with_price_events(events), investment=investment),
            investment_url=self._links.investment(investment.ref),
            developer_url=self._links.developer(investment.ref),
        )
