"""Use case ``SearchInvestments``: investments in one city or by a part of their name."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.errors import InvalidInputError
from deweloperuch_mcp.models.investment_summary import (
    DEFAULT_INVESTMENT_SORT,
    DEFAULT_INVESTMENTS_LIMIT,
    InvestmentName,
    InvestmentsCity,
    InvestmentSearchCriteria,
    InvestmentSearchResult,
    InvestmentsLimit,
    InvestmentSort,
    InvestmentSummary,
)
from deweloperuch_mcp.models.values import CitySlug, DeveloperSlug
from deweloperuch_mcp.usecases.ports import InvestmentDirectory, PageLinks
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs

NEEDS_CITY_OR_NAME = (
    "Podaj city (slug miasta z search_locations, np. sopot) albo name (fragment nazwy "
    "inwestycji, np. Kolibki); można oba."
)
WHOLE_COUNTRY_INVESTMENTS = (
    "city=polska nie działa przy wyszukiwaniu inwestycji: podaj slug jednego miasta "
    "(search_locations) albo szukaj w całym kraju po nazwie (name, bez city)."
)
DEVELOPER_NEEDS_CITY = (
    "developer_slug działa tylko razem z city: podaj slug miasta (search_locations), w "
    "którym szukać inwestycji dewelopera."
)
SORT_NEEDS_CITY = (
    "sort działa tylko razem z city; wyniki wyszukiwania po samej nazwie są w kolejności "
    "serwisu: pomiń sort albo podaj city."
)


@dataclass(frozen=True, kw_only=True)
class SearchInvestmentsRequest:
    """What a search asks for, checked (``parse``) before anything is sent."""

    criteria: InvestmentSearchCriteria

    @classmethod
    def parse(
        cls,
        *,
        city: object = None,
        name: object = None,
        developer_slug: object = None,
        sort: object = None,
        limit: object = DEFAULT_INVESTMENTS_LIMIT,
    ) -> Self:
        """Checked in this order: city (one city, not the whole country), name, developer,
        sort, limit; then what they need of each other: a city or a name, and the city for
        the developer and the order. A refusal names the parameter
        (``InvalidInputError``)."""
        with ParameterCheck():
            where = None if city is None else InvestmentsCity.parse(city)
            if where is not None and where.whole_country:
                raise InvalidInputError(WHOLE_COUNTRY_INVESTMENTS)
            part = None if name is None else InvestmentName.parse(name)
            developer = None if developer_slug is None else DeveloperSlug.parse(developer_slug)
            order = InvestmentSort.parse(sort)
            count = InvestmentsLimit.parse(limit)
        if where is None and part is None:
            raise InvalidInputError(NEEDS_CITY_OR_NAME)
        if where is None and developer is not None:
            raise InvalidInputError(DEVELOPER_NEEDS_CITY)
        if where is None and order is not None:
            raise InvalidInputError(SORT_NEEDS_CITY)
        return cls(
            criteria=InvestmentSearchCriteria(
                city=where, name=part, developer=developer, sort=order, limit=count
            )
        )


@dataclass(frozen=True, kw_only=True)
class SearchInvestmentsResult:
    """The investments a search shows (``search``), with the pages of each investment and
    of its developer (D12), aligned with ``search.items``; a search by name does not know
    the city and developer they need, so it has none."""

    search: InvestmentSearchResult
    investment_urls: tuple[str | None, ...]
    developer_urls: tuple[str | None, ...]

    @property
    def hint(self) -> str | None:
        """What to do about a result that does not show every match (D4) or shows none."""
        criteria = self.search.criteria
        if criteria.city is not None:
            return self._city_hint(criteria.city)
        assert criteria.name is not None  # InvestmentSearchCriteria: a city or a name
        return self._name_hint(criteria.name)

    def _city_hint(self, city: CitySlug) -> str | None:
        search = self.search
        criteria = search.criteria
        if not search.items and criteria.name is None and criteria.developer is None:
            # [W] the city's list holds the investments with active offers (the map of the
            # city); without them an existing city may have none (see the adapter).
            return (
                f"Serwis nie pokazuje żadnej inwestycji dla {city.value!r}: miasto może nie mieć "
                "aktywnych ofert deweloperów albo slug jest błędny. Sprawdź slug i offer_count "
                "miasta w search_locations; inwestycję po nazwie znajdziesz też bez city (name)."
            )
        if not search.items:
            return (
                f"Żadna inwestycja w {city.value!r} nie pasuje do name i developer_slug. Sprawdź "
                "pisownię albo pomiń te filtry, żeby zobaczyć wszystkie inwestycje miasta."
            )
        if search.truncated:
            sort = criteria.sort or DEFAULT_INVESTMENT_SORT
            return (
                f"Pasujących inwestycji jest {search.total}, pokazano pierwsze {search.returned} "
                f"(sort={sort}). Zawęź wyniki przez name lub developer_slug albo zmień sort."
            )
        return None

    def _name_hint(self, name: InvestmentName) -> str | None:
        search = self.search
        if not search.items:
            return (
                f"Nic nie pasuje do {name.text!r}. Sprawdź pisownię albo podaj krótszy fragment "
                "nazwy; z city przeszukasz inwestycje jednego miasta."
            )
        if search.truncated:
            many = "więcej" if search.total is None else f"{search.total} (wg serwisu)"
            return (
                f"Pasujących inwestycji jest {many}, pokazano {search.returned}. Doprecyzuj "
                "nazwę albo dodaj city."
            )
        return None


class SearchInvestments:
    """The investments of a city (filtered, ordered and cut in the domain) or, without a
    city, the service's matches of a part of the name; the result says what it left
    out (D4)."""

    def __init__(self, directory: InvestmentDirectory, links: PageLinks) -> None:
        self._directory = directory
        self._links = links

    def execute(self, request: SearchInvestmentsRequest) -> SearchInvestmentsResult:
        criteria = request.criteria
        if criteria.city is not None:
            city = criteria.city.value
            with ReportedAs(
                f"Wyszukiwanie inwestycji w {city!r}",
                not_found=f"Serwis nie zna miasta {city!r}. Podaj city_slug z search_locations.",
            ):
                investments = self._directory.in_city(criteria.city)
            search = criteria.select(investments)
        else:
            assert criteria.name is not None  # InvestmentSearchCriteria: a city or a name
            with ReportedAs("Wyszukiwanie inwestycji po nazwie"):
                matches = self._directory.by_name(criteria.name, criteria.shown_at_most)
            search = InvestmentSearchResult.of_matches(criteria, matches)
        pages = [self._pages(item) for item in search.items]
        return SearchInvestmentsResult(
            search=search,
            investment_urls=tuple(investment for investment, _ in pages),
            developer_urls=tuple(developer for _, developer in pages),
        )

    def _pages(self, item: InvestmentSummary) -> tuple[str | None, str | None]:
        """The pages of ``item`` and of its developer; none without its developer."""
        ref = item.ref
        if ref is None:
            return None, None
        return self._links.investment(ref), self._links.developer(ref)
