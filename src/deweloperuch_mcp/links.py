"""Addresses of the service's public pages, for people (D12, 2026-10-11: links in results).

The one place that builds them: from the page routes confirmed [P] in
docs/discovery/pages-rsc.md, on ``identity.BASE_URL``. The path of the offers list is
the RSC adapter's own (``rsc.offers_list_path``), so the link to a list is the request
the client sent, without ``_rsc``; the dependency runs one way (links -> client).

- Segments are percent-encoded as the client encodes them (``path_segment``).
- A missing slug (or one that would move the path: ``.``, ``..``, or one that cannot be
  encoded) gives no address (``None``): never a guess, never a crash.
- No ``/api/*`` paths, no ``_rsc``, no page whose route is not [P]: an offer's own page
  (``raport-mieszkania-{slug}``) has a slug rule that is only [P z kodu] and may collide.

The CLI and the MCP server never import this module (D6): they get the addresses in the
domain model.
"""

from collections.abc import Sequence

from deweloperuch_mcp.client.rsc import offers_list_path
from deweloperuch_mcp.client.transport import build_target, path_segment
from deweloperuch_mcp.identity import BASE_URL


def offers_list_url(city_slug: str, params: Sequence[tuple[str, str | int]]) -> str:
    """The list of offers with ``params`` as the query, in their order.

    Pass the parameters the service sends (``services.search_offers``): the same list
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


def _segments(*slugs: str | None) -> tuple[str, ...] | None:
    """Each slug as one encoded path segment; ``None`` if any is blank, ``.`` or ``..``,
    or cannot be encoded (a lone surrogate)."""
    if any(slug is None or not slug.strip() or slug in (".", "..") for slug in slugs):
        return None
    try:
        return tuple(path_segment(slug) for slug in slugs if slug is not None)
    except UnicodeEncodeError:
        return None
