"""Use case ``GetDeveloper``: a developer's profile with its investments and cities, in a
city or the whole country."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.developer_profile import DEFAULT_INVESTMENTS_LIMIT, DeveloperListing
from deweloperuch_mcp.models.values import WHOLE_COUNTRY, CitySlug, DeveloperSlug, InvestmentsLimit
from deweloperuch_mcp.usecases.ports import DeveloperDirectory, PageLinks
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs

NO_OFFERS_IN_THE_CITY = " Albo deweloper nie ma w tym mieście aktywnych ofert: spróbuj city=polska."
"""The end of the "not found" message of a developer in a city (``GetDeveloper``)."""

CITIES_OF_INVESTMENTS_ONLY = (
    "Serwis nie podał listy miast dewelopera: cities to tylko miasta inwestycji w city "
    "(wszystkie: city=polska)."
)
"""The hint of a city's profile whose cities come from its investments
(``GetDeveloperResult.hint``)."""


@dataclass(frozen=True, kw_only=True)
class GetDeveloperRequest:
    """The developer, the scope of its profile and the investments shown, checked
    (``parse``) before anything is sent."""

    developer: DeveloperSlug
    city: CitySlug
    limit: InvestmentsLimit

    @classmethod
    def parse(
        cls,
        *,
        developer_slug: object,
        city: object = WHOLE_COUNTRY,
        limit: object = DEFAULT_INVESTMENTS_LIMIT,
    ) -> Self:
        """Checked in this order: the developer, the city, the limit. A refusal names the
        parameter (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(
                developer=DeveloperSlug.parse(developer_slug),
                city=CitySlug.parse(city),
                limit=InvestmentsLimit.parse(limit),
            )


@dataclass(frozen=True, kw_only=True)
class GetDeveloperResult:
    """The profile as a result shows it (``DeveloperProfile.listing``) with the links of
    D12: the developer's profile in the city, and the page of each investment kept
    (aligned with ``listing.investments``)."""

    listing: DeveloperListing
    developer_url: str | None
    investment_urls: tuple[str | None, ...]

    @property
    def hint(self) -> str | None:
        """What to do about a profile without investments in its scope, or about a city's
        profile whose cities may be only that city (the service sent no list of cities,
        ``DeveloperProfile.cities_in_scope_only``); ``None`` otherwise."""
        profile = self.listing.profile
        if not profile.investments:
            if profile.city.whole_country:
                return "Deweloper nie ma inwestycji z aktywnymi ofertami."
            return (
                f"Deweloper nie ma inwestycji z aktywnymi ofertami w {profile.city.value!r}. "
                "Spróbuj city=polska (cała Polska)."
            )
        if profile.cities_in_scope_only:
            return CITIES_OF_INVESTMENTS_ONLY
        return None


class GetDeveloper:
    """One page of the service: the developer's investments in the city (or the whole
    country), the investments with the most active offers first, at most ``limit``."""

    def __init__(self, directory: DeveloperDirectory, links: PageLinks) -> None:
        self._directory = directory
        self._links = links

    def execute(self, request: GetDeveloperRequest) -> GetDeveloperResult:
        slug, city = request.developer, request.city
        with ReportedAs(
            f"Deweloper {slug.value!r}{self._where(city)}", not_found=self._unknown(request)
        ):
            profile = self._directory.developer(slug, city)
        listing = profile.listing(request.limit)
        return GetDeveloperResult(
            listing=listing,
            developer_url=self._links.developer_in(city.value, profile.developer.developer_slug),
            investment_urls=tuple(self._links.investment(item.ref) for item in listing.investments),
        )

    @staticmethod
    def _where(city: CitySlug) -> str:
        return "" if city.whole_country else f" w {city.value!r}"

    @classmethod
    def _unknown(cls, request: GetDeveloperRequest) -> str:
        """What a "not found" means. In a city it may be a known developer without offers
        there (T39: the service may answer so, [H], not requested)."""
        message = (
            f"Nie znaleziono dewelopera {request.developer.value!r}{cls._where(request.city)}. "
            "Slug dewelopera podaje search_developers (po nazwie) albo pole developer_slug w "
            "search_offers, get_investment i get_offer; city to city_slug z search_locations "
            "albo polska (cała Polska)."
        )
        if request.city.whole_country:
            return message
        return message + NO_OFFERS_IN_THE_CITY
