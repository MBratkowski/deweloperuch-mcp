"""Use case ``SearchOffers`` (D17 reference): one page of developer offers in a city or in
the whole country, with what to do next and the links of D12."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.errors import TrueOrFalse, ValueName
from deweloperuch_mcp.models.offer import OfferSearchCriteria, OfferSearchPage
from deweloperuch_mcp.models.values import (
    BROWSABLE_PAGES,
    DEFAULT_PAGE_SIZE,
    PAGE_SIZES,
    AreaRange,
    CitySlug,
    DistrictName,
    OfferSort,
    OfferStatus,
    PageNumber,
    PageSize,
    PricePerM2Range,
    PriceRange,
)
from deweloperuch_mcp.usecases.ports import OfferCatalog, PageLinks
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs


@dataclass(frozen=True, kw_only=True)
class SearchOffersRequest:
    """What a search asks for, checked (``parse``) before anything is sent."""

    criteria: OfferSearchCriteria

    @classmethod
    def parse(  # noqa: PLR0913 - one keyword per argument of the tool and the command (D17)
        cls,
        *,
        city: object,
        price_min: object = None,
        price_max: object = None,
        area_min: object = None,
        area_max: object = None,
        price_per_m2_min: object = None,
        price_per_m2_max: object = None,
        district: object = None,
        price_dropped: object = False,
        status: object = None,
        sort: object = None,
        page: object = 1,
        per_page: object = DEFAULT_PAGE_SIZE,
    ) -> Self:
        """The arguments as the CLI and the MCP server take them, checked in this order:
        city, price, area, price per m², district, price dropped, status, sort, page, page
        size; last, a district against the whole country. A refusal names the parameter
        (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(
                criteria=OfferSearchCriteria(
                    city=CitySlug.parse(city),
                    price=PriceRange.parse(price_min, price_max),
                    area=AreaRange.parse(area_min, area_max),
                    price_per_m2=PricePerM2Range.parse(price_per_m2_min, price_per_m2_max),
                    district=DistrictName.parse(district),
                    price_dropped=TrueOrFalse().check(ValueName.PRICE_DROPPED, price_dropped),
                    status=OfferStatus.parse(status),
                    sort=OfferSort.parse(sort),
                    page=PageNumber.parse(page),
                    per_page=PageSize.parse(per_page),
                )
            )


@dataclass(frozen=True, kw_only=True)
class SearchOffersResult:
    """A page of an offers search (for ``criteria``) with the links of D12: the same list
    on the service, and the page of each offer's investment (aligned with
    ``page.items``)."""

    criteria: OfferSearchCriteria
    page: OfferSearchPage
    list_url: str | None
    investment_urls: tuple[str | None, ...]

    @property
    def whole_country(self) -> bool:
        """The search covers the whole country (``polska``), not one city."""
        return self.criteria.city.whole_country

    @property
    def hint(self) -> str | None:
        """What to do about a page that does not show every match (D4), an empty search
        or a page past the last one; ``None`` otherwise."""
        page = self.page
        if page.truncated:
            larger = page.per_page < max(PAGE_SIZES)
            return (
                f"Pasujących ofert jest {page.total}, a serwis pozwala przejrzeć najwyżej "
                f"{BROWSABLE_PAGES} stron po {page.per_page} ({page.browsable}). Zawęź filtry "
                f"(cena, metraż)"
                + (f" albo zwiększ per_page do {max(PAGE_SIZES)}." if larger else ".")
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

    def execute(self, request: SearchOffersRequest) -> SearchOffersResult:
        criteria = request.criteria
        with ReportedAs(
            f"Wyszukiwanie ofert w {criteria.city.value!r}",
            not_found=self._unknown_city(criteria),
        ):
            page = self._catalog.search(criteria)
        return SearchOffersResult(
            criteria=criteria,
            page=page,
            list_url=self._links.offers_list(criteria),
            investment_urls=tuple(self._links.investment(item.investment) for item in page.items),
        )

    @staticmethod
    def _unknown_city(criteria: OfferSearchCriteria) -> str:
        return (
            f"Serwis nie zna miasta {criteria.city.value!r}. Podaj city_slug z search_locations "
            "albo polska (cały kraj)."
        )
