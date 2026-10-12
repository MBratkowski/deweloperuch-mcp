"""Addresses of the service's public pages, for people (D12, 2026-10-11: links in results).

The ``PageLinks`` port of the domain (``ServicePageLinks``) and the one place that builds
the addresses: from the page routes confirmed [P] in docs/discovery/pages-rsc.md, on
``identity.BASE_URL``. The path of the offers list is the RSC adapter's own
(``rsc.offers_list_path``) and its query the request's (``params.offers_list_query``), so
the link to a list is the request the client sent, without ``_rsc``; the same holds for
the government statistics (``rsc.government_stats_path``).

- Segments are percent-encoded as the transport encodes them (``path_segment``).
- A missing slug (or one that would move the path: ``.``, ``..``, or one that cannot be
  encoded) gives no address (``None``): never a guess, never a crash.
- No ``/api/*`` paths, no ``_rsc``, no page whose route is not [P]: an offer's own page
  (``raport-mieszkania-{slug}``) has a slug rule that is only [P z kodu] and may collide.

The domain holds identities (slugs, the section of a page), never addresses; the use
cases ask this port for them (D13).
"""

import re
from collections.abc import Sequence

from deweloperuch_mcp.domain.offers import InvestmentRef, OfferSearchCriteria
from deweloperuch_mcp.domain.values import LocationSlug
from deweloperuch_mcp.identity import BASE_URL
from deweloperuch_mcp.infrastructure.deweloperuch.params import offers_list_query
from deweloperuch_mcp.infrastructure.deweloperuch.rsc import (
    government_stats_path,
    offers_list_path,
)
from deweloperuch_mcp.infrastructure.deweloperuch.transport import build_target, path_segment


class ServicePageLinks:
    """``domain.ports.PageLinks`` of the service."""

    def offers_list(self, criteria: OfferSearchCriteria) -> str | None:
        return offers_list_url(criteria.city.value, offers_list_query(criteria))

    def investment(self, investment: InvestmentRef) -> str | None:
        return investment_url(
            investment.city_slug, investment.developer.developer_slug, investment.investment_slug
        )

    def developer(self, investment: InvestmentRef) -> str | None:
        return developer_url(investment.city_slug, investment.developer.developer_slug)

    def government_statistics(self, location: LocationSlug, section: str | None) -> str | None:
        return government_stats_url(location.value, section)


def offers_list_url(city_slug: str, params: Sequence[tuple[str, str | int]]) -> str:
    """The list of offers with ``params`` as the query, in their order.

    Pass the parameters the service gets (``params.offers_list_query``): the same list
    and the same query builder (``build_target``) as the request, without ``_rsc``.
    """
    return BASE_URL + build_target(offers_list_path(city_slug), params)


def developer_url(city_slug: str | None, developer_slug: str | None) -> str | None:
    """``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`` [P]: a developer's profile."""
    segments = _segments(city_slug, developer_slug)
    if segments is None:
        return None
    city, developer = segments
    return f"{BASE_URL}/ceny-ofertowe/{city}/deweloperzy/{developer}"


def investment_url(
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


# Ids of the sections of a page as its table of contents gives them [P 2026-10-11]
# (``gus-srednia-powierzchnia``, ``nbp``): a fragment of the link, never anything else.
_SECTION = re.compile(r"[a-z0-9][a-z0-9-]*")


def government_stats_url(location: str | None, section: str | None = None) -> str | None:
    """``/statystyki/statystyki-rzadowe/{location}`` [P], at ``#section`` when given.

    ``section`` is the id of a section in the page's table of contents (``tocItems``
    [P]); one that is not such an id is left out (the page without a fragment).
    """
    if location is None or _segments(location) is None:
        return None
    url = BASE_URL + government_stats_path(location)
    if section is not None and _SECTION.fullmatch(section):
        url += f"#{section}"
    return url


def _segments(*slugs: str | None) -> tuple[str, ...] | None:
    """Each slug as one encoded path segment; ``None`` if any is blank, ``.`` or ``..``,
    or cannot be encoded (a lone surrogate)."""
    if any(slug is None or not slug.strip() or slug in (".", "..") for slug in slugs):
        return None
    try:
        return tuple(path_segment(slug) for slug in slugs if slug is not None)
    except UnicodeEncodeError:
        return None
