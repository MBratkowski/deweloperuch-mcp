"""Use case ``SearchOffers`` (D17 reference): one page of developer offers in a city or in
one of its districts, with what to do next and the links of D12."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.errors import InvalidInputError, TrueOrFalse, ValueName
from deweloperuch_mcp.models.offer import OffersCity, OfferSearchCriteria, OfferSearchPage
from deweloperuch_mcp.models.values import (
    BROWSABLE_PAGES,
    DEFAULT_PAGE_SIZE,
    PAGE_SIZES,
    AreaRange,
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

WHOLE_COUNTRY_OFFERS = (
    "city=polska nie działa przy wyszukiwaniu ofert: serwis nie ma jednej listy ofert całej "
    "Polski. Podaj city_slug jednego miasta z search_locations (np. warszawa); oferty kilku "
    "miast wyszukaj osobno dla każdego."
)
"""[P 2026-10-29] pages-rsc.md: the service's list of Poland is a list of cities (308 to
``/ceny-ofertowe/polska/miasta``), not of offers."""


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
        city (one city, not the whole country), price, area, price per m², district, price
        dropped, status, sort, page, page size. A refusal names the parameter
        (``InvalidInputError``)."""
        with ParameterCheck():
            where = OffersCity.parse(city)
            if where.whole_country:
                raise InvalidInputError(WHOLE_COUNTRY_OFFERS)
            return cls(
                criteria=OfferSearchCriteria(
                    city=where,
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
    def narrowing(self) -> str:
        """The filters that narrow a list the service cuts (D4): the district first, unless
        the search is already in one."""
        return "cena, metraż" if self.criteria.district is not None else "dzielnica, cena, metraż"

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
                f"({self.narrowing})"
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
    """One page of developer offers in a city or in one of its districts; the page says how
    much of the result can be browsed at all (D4)."""

    def __init__(self, catalog: OfferCatalog, links: PageLinks) -> None:
        self._catalog = catalog
        self._links = links

    def execute(self, request: SearchOffersRequest) -> SearchOffersResult:
        criteria = request.criteria
        with ReportedAs(self._subject(criteria), not_found=self._not_found(criteria)):
            page = self._catalog.search(criteria)
        return SearchOffersResult(
            criteria=criteria,
            page=page,
            list_url=self._links.offers_list(criteria),
            investment_urls=tuple(self._links.investment(item.investment) for item in page.items),
        )

    @staticmethod
    def _subject(criteria: OfferSearchCriteria) -> str:
        where = f"Wyszukiwanie ofert w {criteria.city.value!r}"
        district = criteria.district
        return where if district is None else f"{where} (dzielnica {district.text!r})"

    @staticmethod
    def _not_found(criteria: OfferSearchCriteria) -> str:
        """What to say about a list the service does not know: an unknown city, or an unknown
        district of a known city [P 2026-10-31]. A district's list of an unknown city was
        not requested; the district's message sends the caller back for both names. A page
        past the last one gets the same marker [P 2026-10-31, live e2e: page 2 of Sopot], so
        a page above 1 names both readings."""
        city, district = criteria.city.value, criteria.district
        if district is None:
            unknown, fix = f"nie zna miasta {city!r}", "podaj city_slug miasta z search_locations"
        else:
            unknown = f"nie zna dzielnicy {district.text!r} w mieście {city!r}"
            fix = (
                "podaj nazwę dzielnicy tak, jak zwraca ją search_locations (kind=district, pole "
                "name), razem z city_slug jej miasta"
            )
        if criteria.page.value > 1:
            return (
                f"Serwis nie ma strony {criteria.page.value} tej listy albo {unknown}: lista może "
                "mieć mniej stron (pages_available podaje page=1); jeśli page=1 też zawiedzie, "
                f"{fix}."
            )
        return f"Serwis {unknown}. {fix[0].upper()}{fix[1:]}."
