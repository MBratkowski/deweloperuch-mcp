"""``OffersQuery``: offer search criteria -> the address of ``/ceny-ofertowe/{city}/mieszkania``
(D1, D17).

The one place that knows the page's path and parameters; the request
(``adapters.offers_api.OffersApi``) and the link to the same list
(``links.ServicePageLinks``) both use ``OffersQuery``, so the link is the request without
``_rsc``. Parameters (docs/discovery/pages-rsc.md):

- ``filterPrice`` / ``filterSize`` [P], ``filterPricePerM2`` ([P z kodu], see
  ``PRICE_PER_M2_SENTINEL``): ``min-max``; an end left open is sent as 0 or as the UI's
  sentinel;
- ``filterDistrict`` [P 2026-10-10]: the district's name as the locations search gives it;
- ``filterPriceChange=decrease`` [P 2026-10-10]: the price is below the first one;
- ``filterStatus=archived`` [P] or ``includeArchived=true`` [P]; active offers (the
  default) send neither;
- ``sortBy`` with ``sortOrder`` (``SORT_PARAMS``); no sort keeps the service's order;
- ``page`` and ``perPage``, always.

The order: the ranges, the district, the change, the status, the order, the page. The UI's
own order of the parameters added after the ranges is not known [W]; the service does not
depend on it as far as seen (the query is a set of named parameters).
"""

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

# [P z kodu] docs/discovery/pages-rsc.md, "Wspólne reguły list": the UI sends a range
# without a lower bound as 0-max and one without an upper bound as min-<sentinel>. What
# the server does with them is [W]; tests/unit/api/queries/test_offers_query.py pins the
# values. They equal the domain's largest accepted values (``AmountPln.MAX``,
# ``AreaM2.MAX``, ``PricePerM2Pln.MAX``), which the domain takes from the same UI, but
# they are this mapping's own.
OPEN_LOW = 0
PRICE_SENTINEL = 99_999_999
"""The upper end of ``filterPrice`` when the range has none (PLN)."""
AREA_SENTINEL = 9_999
"""The upper end of ``filterSize`` when the range has none (m²)."""
# [P z kodu] the same section: `filterPricePerM2` and its sentinel are the UI's; that the
# server narrows the list by them is [W] (only filterPrice and filterSize were tested).
# tests/e2e/test_live_mcp.py checks it on the live service: every offer within the range.
PRICE_PER_M2_SENTINEL = 999_999
"""The upper end of ``filterPricePerM2`` when the range has none (PLN/m²)."""

# [P 2026-10-10] pages-rsc.md: `filterPriceChange=decrease` keeps the offers whose price is
# below the first one (`start_amount_difference*`), not those whose last change was a drop.
PRICE_DROPPED = ("filterPriceChange", "decrease")
# [P] pages-rsc.md: `filterStatus=archived` gives archived offers only, `includeArchived=true`
# active and archived ones together; `filterStatus=active` was never tested, so the active
# ones (the service's default) send nothing.
STATUS_PARAMS: Mapping[OfferStatus, tuple[str, str] | None] = {
    OfferStatus.ACTIVE: None,
    OfferStatus.ARCHIVED: ("filterStatus", "archived"),
    OfferStatus.ALL: ("includeArchived", "true"),
}

SORT_PARAMS: Mapping[OfferSort, tuple[str, str]] = {
    OfferSort.PRICE_ASC: ("amount", "asc"),
    OfferSort.PRICE_DESC: ("amount", "desc"),
    # [P 2026-10-10] pages-rsc.md: `price_per_sqm`, `size` and
    # `start_amount_difference_percent` order the list as their values; checked ascending.
    # Descending is [W] (as `amount`, whose both orders are [P]); tests/e2e/test_live_mcp.py
    # checks the order of both descending ones on the live service.
    OfferSort.PRICE_PER_M2_ASC: ("price_per_sqm", "asc"),
    OfferSort.PRICE_PER_M2_DESC: ("price_per_sqm", "desc"),
    OfferSort.AREA_ASC: ("size", "asc"),
    OfferSort.AREA_DESC: ("size", "desc"),
    # The most negative change since the first price first: the largest drop [P].
    OfferSort.BIGGEST_DROP: ("start_amount_difference_percent", "asc"),
}
"""``sortBy`` and ``sortOrder`` of each order."""


class OffersQuery:
    """The address of the offers list for ``criteria``: ``path()`` and ``params()``."""

    def __init__(self, criteria: OfferSearchCriteria) -> None:
        self._criteria = criteria

    def path(self) -> str:
        """``/ceny-ofertowe/{city}/mieszkania`` [P]: the city slug or ``polska``."""
        return f"/ceny-ofertowe/{HttpClient.segment(self._criteria.city.value)}/mieszkania"

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
        if criteria.district is not None:
            params.append(("filterDistrict", criteria.district.text))
        if criteria.price_dropped:
            params.append(PRICE_DROPPED)
        status = STATUS_PARAMS[criteria.status]
        if status is not None:
            params.append(status)
        if criteria.sort is not None:
            sort_by, sort_order = SORT_PARAMS[criteria.sort]
            params += [("sortBy", sort_by), ("sortOrder", sort_order)]
        params.append(("page", criteria.page.value))
        params.append(("perPage", criteria.per_page.value))
        return params

    @staticmethod
    def _bounds(found: PriceRange | AreaRange | PricePerM2Range, sentinel: int) -> str:
        low = OPEN_LOW if found.low is None else found.low.value
        high = sentinel if found.high is None else found.high.value
        return f"{low}-{high}"
