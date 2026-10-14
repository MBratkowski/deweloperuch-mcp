"""Addresses of the service's public pages, for people (D12, 2026-10-11: links in results).

The ``PageLinks`` port of the domain (``ServicePageLinks``) and the one place that builds
the addresses: from the page routes confirmed [P] in docs/discovery/pages-rsc.md, on
``identity.BASE_URL``. The path and the query of the offers list are the request's
(``queries.offers_query.OffersQuery``), so the link to a list is the request the client
sent, without ``_rsc``; the same holds for the government statistics
(``GovernmentStatisticsApi.path``). The transaction statistics page is linked only,
never requested (a dump, D5). Each address has one private builder (``_*_url``); the
port's methods hand them the identities of the models.

- Segments are percent-encoded as the transport encodes them (``HttpClient.segment``).
- A missing slug (or one that would move the path: ``.``, ``..``, or one that cannot be
  encoded) gives no address (``None``): never a guess, never a crash.
- No ``/api/*`` paths, no ``_rsc``, no page whose route is not [P]: an offer's own page
  (``raport-mieszkania-{slug}``) has a slug rule that is only [P z kodu] and may collide.

The domain holds identities (slugs, the section of a page), never addresses; the use
cases ask this port for them (D13).
"""

import re

from deweloperuch_mcp.api.adapters.developer_profile_api import DeveloperProfileApi
from deweloperuch_mcp.api.adapters.government_statistics_api import GovernmentStatisticsApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.queries.offers_query import OffersQuery
from deweloperuch_mcp.identity import BASE_URL
from deweloperuch_mcp.models.building import BuildingRef
from deweloperuch_mcp.models.offer import InvestmentRef, OfferSearchCriteria
from deweloperuch_mcp.models.transaction_series import TransactionCity
from deweloperuch_mcp.models.values import CitySlug, LocationSlug


class ServicePageLinks:
    """``usecases.ports.PageLinks`` of the service (with ``DeveloperLinks``,
    ``BuildingPageLinks``, ``RankingLinks`` and ``TransactionStatisticsLinks``)."""

    def offers_list(self, criteria: OfferSearchCriteria) -> str | None:
        """The request the client sends for ``criteria`` (``OffersQuery``), without
        ``_rsc``: the same query builder, the same order."""
        query = OffersQuery(criteria)
        return BASE_URL + HttpClient.target(query.path(), query.params())

    def investment(self, investment: InvestmentRef) -> str | None:
        return self._investment_url(
            investment.city_slug, investment.developer.developer_slug, investment.investment_slug
        )

    def developer(self, investment: InvestmentRef) -> str | None:
        return self._developer_url(investment.city_slug, investment.developer.developer_slug)

    def developer_in(self, city: str | None, developer_slug: str | None) -> str | None:
        return self._developer_url(city, developer_slug)

    def developer_profile(self, developer_slug: str, city: CitySlug) -> str | None:
        """``usecases.ports.DeveloperLinks``."""
        # [P] docs/discovery/pages-rsc.md: the profile route (sample page.developer, city
        # ``warszawa``); ``polska`` as its city [P 2026-10-13], the profile of the whole
        # country (tests/fixtures/rsc/developer_atal_polska.rsc).
        return self._developer_url(city.value, developer_slug)

    def government_statistics(self, location: LocationSlug, section: str | None) -> str | None:
        return self._government_stats_url(location.value, section)

    def building(self, building: BuildingRef) -> str | None:
        """``usecases.ports.BuildingPageLinks``."""
        return self._building_url(building.city_slug, building.building_slug)

    def city_ranking(self) -> str | None:
        """``usecases.ports.RankingLinks``."""
        return self._city_ranking_url()

    def transaction_statistics(self, city: TransactionCity) -> str | None:
        """``usecases.ports.TransactionStatisticsLinks``."""
        return self._transaction_stats_url(city.value)

    @staticmethod
    def _developer_url(city_slug: str | None, developer_slug: str | None) -> str | None:
        """``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`` [P]: a developer's profile in
        a city or (``polska``) the whole country; the path is the RSC adapter's own."""
        if city_slug is None or developer_slug is None:
            return None
        if _segments(city_slug, developer_slug) is None:
            return None
        return BASE_URL + DeveloperProfileApi.path(city_slug, developer_slug)

    @staticmethod
    def _investment_url(
        city_slug: str | None, developer_slug: str | None, investment_slug: str | None
    ) -> str | None:
        """``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}/{investmentSlug}`` [P].

        The service ignores the city and developer segments [P]; the real slugs keep the
        link canonical.
        """
        segments = _segments(city_slug, developer_slug, investment_slug)
        if segments is None:
            return None
        city, developer, investment = segments
        return f"{BASE_URL}/ceny-ofertowe/{city}/deweloperzy/{developer}/{investment}"

    @staticmethod
    def _government_stats_url(location: str | None, section: str | None = None) -> str | None:
        """``/statystyki/statystyki-rzadowe/{location}`` [P], at ``#section`` when given.

        ``section`` is the id of a section in the page's table of contents (``tocItems``
        [P]); one that is not such an id is left out (the page without a fragment).
        """
        if location is None or _segments(location) is None:
            return None
        url = BASE_URL + GovernmentStatisticsApi.path(location)
        if section is not None and _SECTION.fullmatch(section):
            url += f"#{section}"
        return url

    @staticmethod
    def _transaction_stats_url(city_slug: str | None) -> str | None:
        """``/statystyki/ceny-transakcyjne/mieszkania/{city}`` [P] (pages-rsc.md, sample
        ``page.stats_transactions``): the transaction prices of flats in a city, for people.

        A link, never a request: the page carries every transaction of the city (D5), so it
        stays in ``allowlist.DUMP_PATHS`` and the transport refuses to fetch it.
        """
        segments = _segments(city_slug)
        if segments is None:
            return None
        return f"{BASE_URL}/statystyki/ceny-transakcyjne/mieszkania/{segments[0]}"

    @staticmethod
    def _city_ranking_url() -> str:
        """``/ceny-transakcyjne/polska/miasta`` [P]: the service's ranking of cities, the page
        whose prop ``cities`` holds the data of ``/api/city-transaction-stats``."""
        return f"{BASE_URL}/ceny-transakcyjne/polska/miasta"

    @staticmethod
    def _building_url(city_slug: str | None, building_slug: str | None) -> str | None:
        """``/ceny-transakcyjne/{city}/adresy/{investRcnSlug}`` [P]: a building of the price
        register with its units and transactions (flats; houses have their own route, which
        no result links to)."""
        segments = _segments(city_slug, building_slug)
        if segments is None:
            return None
        city, building = segments
        return f"{BASE_URL}/ceny-transakcyjne/{city}/adresy/{building}"


# Ids of the sections of a page as its table of contents gives them [P 2026-10-11]
# (``gus-srednia-powierzchnia``, ``nbp``): a fragment of the link, never anything else.
_SECTION = re.compile(r"[a-z0-9][a-z0-9-]*")


def _segments(*slugs: str | None) -> tuple[str, ...] | None:
    """Each slug as one encoded path segment; ``None`` if any is blank, ``.`` or ``..``,
    or cannot be encoded (a lone surrogate)."""
    if any(slug is None or not slug.strip() or slug in (".", "..") for slug in slugs):
        return None
    try:
        return tuple(HttpClient.segment(slug) for slug in slugs if slug is not None)
    except UnicodeEncodeError:
        return None
