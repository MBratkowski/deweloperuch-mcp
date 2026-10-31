"""``OffersQuery``: offer search criteria -> the address of the offers list (D1, D17).

The one place that knows the list's paths and parameters; the request
(``adapters.offers_api.OffersApi``) and the link to the same list
(``links.ServicePageLinks``) both use ``OffersQuery``, so the link is the request without
``_rsc``. Both paths are internal pages of the site's UI (D21): the 2.0 relaunch of
2026-10-29 changed their props and parameters without notice.

- ``/ceny-ofertowe/{city}/mieszkania``: the offers of a city [P 2026-10-31];
- ``/ceny-ofertowe/{city}/{district}/mieszkania``: the offers of one district of the city
  [P 2026-10-31, T70], the district by its slug (``_district_slug``, [W]). It replaces
  ``filterDistrict``, which on 2.0 answers the city list without any offers
  [P 2026-10-31].

Parameters (docs/discovery/pages-rsc.md, "Common list rules" and the offers table), as
seen on the city list. The district route was requested without any (T73), so on it
every one is [W]; tests/e2e/test_live_mcp.py checks a district with filters.

- ``filterPrice``, ``filterSize``, ``filterPricePerM2``: ``min-max``, the upper end included
  [P 2026-10-31, ranges from 0]; a start above 0 is [P] on 1.0 (sample
  ``page.offers_list.filtered``) and [W] on 2.0, included as the domain's ``Range`` says
  (the live suite checks ranges with one); an end left open is sent as 0 or as the UI's
  sentinel (below);
- ``filterPriceChange=decrease`` [P 2026-10-31]: the price is below the first one;
- ``filterStatus=archived`` or ``includeArchived=true`` (``STATUS_PARAMS``); active offers
  (the default) send neither;
- ``sortBy`` with ``sortOrder`` (``SORT_PARAMS``); no sort keeps the service's order;
- ``page`` from the second page on (``FIRST_PAGE``), ``perPage`` always
  (``models.values.PAGE_SIZES``).

The order: the ranges, the change, the status, the order, the page. The UI's own order of
the parameters added after the ranges is not known [W]; the service does not depend on it
as far as seen (the query is a set of named parameters).
"""

import re
import unicodedata
from collections.abc import Mapping

from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.offer import OfferSearchCriteria
from deweloperuch_mcp.models.values import (
    AreaRange,
    OfferSort,
    OfferStatus,
    PricePerM2Range,
    PriceRange,
)

Query = list[tuple[str, str | int]]

# [P z kodu] docs/discovery/pages-rsc.md, "Common list rules": the UI sends a range without
# a lower bound as 0-max and one without an upper bound as min-<sentinel>. A start of 0 is
# [P 2026-10-31] (0-500000 and the like narrow the list). [W] the sentinels on 2.0: the
# 1.0 server treated `filterPrice=0-99999999&filterSize=0-9999` as no filter
# [P 2026-10-10], and they were not sent to 2.0 (T33); tests/e2e/test_live_mcp.py checks
# that ranges open above keep only offers from their start. The values equal the domain's
# largest accepted ones (``AmountPln.MAX``, ``AreaM2.MAX``, ``PricePerM2Pln.MAX``), which
# the domain takes from the same UI, but they are this mapping's own;
# tests/unit/api/queries/test_offers_query.py pins them.
OPEN_LOW = 0
PRICE_SENTINEL = 99_999_999
"""The upper end of ``filterPrice`` when the range has none (PLN)."""
AREA_SENTINEL = 9_999
"""The upper end of ``filterSize`` when the range has none (m²)."""
# [P 2026-10-31] pages-rsc.md: `filterPricePerM2` with a closed range narrows the list by
# `amount / size`, the upper end included (0-15000: 2,855 offers of Warszawa, as many as
# the offer snapshot with at most 15,000 PLN/m²). Its sentinel for an open upper end is
# [P z kodu] and was never sent, on 1.0 either: [W], checked by the live suite with the
# other two.
PRICE_PER_M2_SENTINEL = 999_999
"""The upper end of ``filterPricePerM2`` when the range has none (PLN/m²)."""

# [P 2026-10-31] pages-rsc.md: `filterPriceChange=decrease` keeps the offers whose price is
# below the first one (`start_amount_difference`), not those whose last change was a drop
# ([P 2026-10-10]): 2,167 offers of Warszawa, as many as the snapshot's negative changes.
PRICE_DROPPED = ("filterPriceChange", "decrease")
# [P 2026-10-31] pages-rsc.md: `filterStatus=archived` lists the archived offers (12,471 of
# Warszawa; all rows `archived` on 1.0 [P 2026-10-10], not read on 2.0: the live suite
# checks them). [W] `includeArchived=true` lists the active and the archived ones: on 1.0
# exactly their sum [P 2026-10-10], on 2.0 34,011 against 11,672 active plus 12,471
# archived (T72, the rest unexplained); the live suite checks that every row is active or
# archived. `filterStatus=active` was never tested, so the active offers (the service's
# default) send nothing.
STATUS_PARAMS: Mapping[OfferStatus, tuple[str, str] | None] = {
    OfferStatus.ACTIVE: None,
    OfferStatus.ARCHIVED: ("filterStatus", "archived"),
    OfferStatus.ALL: ("includeArchived", "true"),
}

# [P 2026-10-31] pages-rsc.md: `sortBy=amount&sortOrder=desc` orders the list by price,
# dearest first. [P 2026-10-10] on 1.0 also `amount` ascending and `price_per_sqm`, `size`
# and `start_amount_difference_percent` ascending. [W] every order but the first on 2.0,
# and the descending ones by price per m² and area on any build: tests/e2e/test_live_mcp.py
# checks the order of each on the live service.
SORT_PARAMS: Mapping[OfferSort, tuple[str, str]] = {
    OfferSort.PRICE_ASC: ("amount", "asc"),
    OfferSort.PRICE_DESC: ("amount", "desc"),
    OfferSort.PRICE_PER_M2_ASC: ("price_per_sqm", "asc"),
    OfferSort.PRICE_PER_M2_DESC: ("price_per_sqm", "desc"),
    OfferSort.AREA_ASC: ("size", "asc"),
    OfferSort.AREA_DESC: ("size", "desc"),
    # The most negative change since the first price first: the largest drop.
    OfferSort.BIGGEST_DROP: ("start_amount_difference_percent", "asc"),
}
"""``sortBy`` and ``sortOrder`` of each order."""

# [P 2026-10-29] pages-rsc.md: the 2.0 service answers `page=1` with 308 to the same address
# without `page` (and without `_rsc`), so the first page is the address without it. With an
# empty `_rsc` `page=1` was not tried (T77); the client never sends it.
FIRST_PAGE = 1
"""The page sent without a ``page`` parameter."""

_SLUG_WORDS = re.compile(r"[a-z0-9]+")


class OffersQuery:
    """The address of the offers list for ``criteria``: ``path()`` and ``params()``."""

    def __init__(self, criteria: OfferSearchCriteria) -> None:
        self._criteria = criteria

    def path(self) -> str | None:
        """The list of the city, or of its district [P 2026-10-31]; ``None`` for a district
        whose name gives no slug, which no list of the service has."""
        city = HttpClient.segment(self._criteria.city.value)
        district = self._criteria.district
        if district is None:
            return f"/ceny-ofertowe/{city}/mieszkania"
        slug = self._district_slug(district.text)
        return f"/ceny-ofertowe/{city}/{slug}/mieszkania" if slug else None

    def params(self) -> Query:
        """The query parameters, in a fixed order."""
        criteria = self._criteria
        params: Query = []
        if criteria.price is not None:
            params.append(("filterPrice", self._bounds(criteria.price, PRICE_SENTINEL)))
        if criteria.area is not None:
            params.append(("filterSize", self._bounds(criteria.area, AREA_SENTINEL)))
        if criteria.price_per_m2 is not None:
            bounds = self._bounds(criteria.price_per_m2, PRICE_PER_M2_SENTINEL)
            params.append(("filterPricePerM2", bounds))
        if criteria.price_dropped:
            params.append(PRICE_DROPPED)
        status = STATUS_PARAMS[criteria.status]
        if status is not None:
            params.append(status)
        if criteria.sort is not None:
            sort_by, sort_order = SORT_PARAMS[criteria.sort]
            params += [("sortBy", sort_by), ("sortOrder", sort_order)]
        if criteria.page.value > FIRST_PAGE:
            params.append(("page", criteria.page.value))
        params.append(("perPage", criteria.per_page.value))
        return params

    @staticmethod
    def _district_slug(name: str) -> str:
        """The district's slug in the service's addresses, from its name: ``Praga-Południe``
        -> ``praga-poludnie``; ``""`` for a name without a Latin letter or a digit.

        [W] pages-rsc.md, the district list: the service addresses a district by an ASCII
        slug, while the locations search gives only its name. The slug is made here, without
        a request: Polish letters to ASCII (``ł`` to ``l``, the others without their marks),
        lowercase, each run of other characters one hyphen, none at the ends.

        Evidence (tests/unit/api/queries/test_offers_query.py): it is the service's own slug
        for the 36 districts the service named with one on 2026-10-31, 18 of Warszawa and 18
        of Kraków. For the 18 of Warszawa the whole path is compared with the ``href`` of the
        prop ``items`` of the city's offers list (tests/fixtures/rsc/offers_warszawa_20261031
        .rsc); for both cities the slug with ``{name, slug}`` of ``city-districts``
        (tests/fixtures/api/city_districts_*_tx_20261031.json). The live suite checks it on
        Praga-Południe. The service's rule for districts is not known.

        The client's slugify of an offer's name [P z kodu] (pages-rsc.md, the offer report:
        "Polish characters → ASCII, lowercase, remove everything except ``[a-z0-9\\s-]``,
        spaces → ``-``") gives the same 36 slugs. It differs on what no district seen has:
        it removes punctuation and turns each space into a hyphen, so ``Św.Katarzyny`` is
        ``swkatarzyny`` there and ``sw-katarzyny`` here, ``Praga - Południe``
        ``praga---poludnie`` there and ``praga-poludnie`` here. Which the service would use
        for such a name is not known [H]; a wrong guess reads as an unknown district.
        """
        folded = unicodedata.normalize("NFKD", name.lower().replace("ł", "l"))
        plain = "".join(char for char in folded if not unicodedata.combining(char))
        return "-".join(_SLUG_WORDS.findall(plain))

    @staticmethod
    def _bounds(found: PriceRange | AreaRange | PricePerM2Range, sentinel: int) -> str:
        low = OPEN_LOW if found.low is None else found.low.value
        high = sentinel if found.high is None else found.high.value
        return f"{low}-{high}"
