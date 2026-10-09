"""Read channels recon/probe.py may call (stdlib only).

Every entry comes from the discovery docs; change the docs first (recon-verifier), then
this file. tests/test_probe_allowlist.py keeps both in sync.

- ``API_PATHS``: each ``GET /api/...`` heading of docs/discovery/endpoints.md except
  ``EXCLUDED_API_PATHS``. The query string is not restricted.
- ``PAGE_ROUTES``: the routes in the headings of docs/discovery/pages-rsc.md, fetched
  as RSC. The query string is not restricted.

Placeholders: ``{name}`` is one path segment or the end of one
(``raport-mieszkania-{slug}``); ``{a|b}`` is one of the listed literals.
There are no server actions here: probe has no POST mode (D1).
"""

import re

API_PATHS = (
    # 1. Lokalizacje i autocomplete
    "/api/popular-search-items",
    "/api/cities",
    "/api/city-lookup",
    "/api/location-search",
    "/api/city-districts",
    "/api/investment-streets",
    "/api/map/city-powiats/{citySlug}",
    "/api/building-outline",
    # 2. Oferty deweloperów
    "/api/developers",
    "/api/investments",
    "/api/offers/city-sales/{citySlug}",
    "/api/map/investments",
    "/api/map/investments/visible/{investmentSlug}",
    "/api/investments/{investId}/sale-events",
    "/api/sale-events",
    "/api/offer-count",
    "/api/price-distribution",
    "/api/size-distribution",
    # 3. Transakcje RCN
    "/api/transaction-count",
    "/api/transaction-price-distribution",
    "/api/transaction-size-distribution",
    "/api/map/powiat-stats",
    "/api/map/powiat-investments/{powiatId}",
    "/api/map/powiat-sales/{powiatId}",
    "/api/map/transactions/visible/{investRcnSlug}",
    "/api/sale-events-rcn/batch",
    # 4. Statystyki
    "/api/monthly-transaction-stats",
    "/api/statystyki/powiat-price-trend",
    "/api/avg-price-trend/city/{citySlug}",
    "/api/avg-price-trend/building/{investRcnId}",
    "/api/city-transaction-stats",
    "/api/announcement-stats",
    # 5. Wycena
    "/api/standalone-valuation",
)

EXCLUDED_API_PATHS = (
    # Generates a PDF with its own rate limit; out of the project's scope (CLAUDE.md).
    "/api/valuation-pdf",
)

PAGE_ROUTES = (
    # Ceny ofertowe
    "/ceny-ofertowe/{city}/mieszkania",
    "/ceny-ofertowe/{city}/inwestycje",
    "/ceny-ofertowe/{city}/deweloperzy",
    "/ceny-ofertowe/{city}/deweloperzy/{developerSlug}",
    "/ceny-ofertowe/{city}/deweloperzy/{developerSlug}/{investmentSlug}",
    "/ceny-ofertowe/{city}/deweloperzy/{developerSlug}/{investmentSlug}/raport-mieszkania-{slug}",
    "/ceny-ofertowe/{city}/deweloperzy/{developerSlug}/{investmentSlug}/raport-inwestycji",
    "/ceny-ofertowe/{city}/mapa",
    # Ceny transakcyjne (RCN)
    "/ceny-transakcyjne/{city}/{mieszkania|domy|adresy}",
    "/ceny-transakcyjne/{city}/{adresy|domy}/{investRcnSlug}",
    "/ceny-transakcyjne/polska/miasta",
    # Statystyki
    "/statystyki/ceny-transakcyjne/{mieszkania|domy}/{city}",
    "/statystyki/ceny-transakcyjne/{type}/{city}/mapa",
    "/statystyki/statystyki-rzadowe/{location}",
    "/statystyki/portale-ogloszeniowe/{type}/{region}",
    # Inne
    "/zglos-dewelopera/mapa-zgloszen",
)

_PLACEHOLDER = re.compile(r"\{([^{}/]*)\}")


def compile_template(template: str) -> re.Pattern[str]:
    """Regex that fully matches the paths ``template`` stands for."""
    parts = []
    end = 0
    for match in _PLACEHOLDER.finditer(template):
        parts.append(re.escape(template[end : match.start()]))
        inner = match.group(1)
        if "|" in inner:
            parts.append("(?:" + "|".join(re.escape(alt) for alt in inner.split("|")) + ")")
        else:
            parts.append("[^/]+")
        end = match.end()
    parts.append(re.escape(template[end:]))
    return re.compile("".join(parts))


_API = tuple((template, compile_template(template)) for template in API_PATHS)
_EXCLUDED = tuple((template, compile_template(template)) for template in EXCLUDED_API_PATHS)
_PAGES = tuple((template, compile_template(template)) for template in PAGE_ROUTES)


def _first_match(path: str, patterns: tuple[tuple[str, re.Pattern[str]], ...]) -> str | None:
    return next((template for template, regex in patterns if regex.fullmatch(path)), None)


def match_api(path: str) -> str | None:
    """The ``API_PATHS`` entry that ``path`` (without query) matches, if any."""
    return _first_match(path, _API)


def match_excluded_api(path: str) -> str | None:
    """The ``EXCLUDED_API_PATHS`` entry that ``path`` (without query) matches, if any."""
    return _first_match(path, _EXCLUDED)


def match_page(path: str) -> str | None:
    """The ``PAGE_ROUTES`` entry that ``path`` (without query) matches, if any."""
    return _first_match(path, _PAGES)
