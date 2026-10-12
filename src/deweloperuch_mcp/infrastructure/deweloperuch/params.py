"""Offer search criteria -> the query of ``/ceny-ofertowe/{city}/mieszkania`` (D1, D13).

The one place that knows the page's parameters; the request (``offers.ServiceOfferCatalog``)
and the link to the same list (``links.ServicePageLinks``) both use ``offers_list_query``,
so the link is the request without ``_rsc``. Only [P] parameters (pages-rsc.md), in the
order the UI sends them:

- ``filterPrice`` / ``filterSize``: ``min-max``; an end left open is sent as 0 or as the
  UI's sentinel (``PRICE_SENTINEL``, ``AREA_SENTINEL``);
- ``sortBy=amount`` with ``sortOrder``: only ``amount`` is [P]; no sort keeps the
  service's default order;
- ``page`` and ``perPage``, always.
"""

from collections.abc import Mapping

from deweloperuch_mcp.domain.offers import OfferSearchCriteria
from deweloperuch_mcp.domain.values import AreaRange, OfferSort, PriceRange

Query = list[tuple[str, str | int]]

# [P z kodu] docs/discovery/pages-rsc.md, "Wspólne reguły list": the UI sends a range
# without a lower bound as 0-max and one without an upper bound as min-<sentinel>. What
# the server does with them is [W]; tests/test_params.py pins the values. They equal the
# domain's largest accepted values (``AmountPln.MAX``, ``AreaM2.MAX``), which the
# domain takes from the same UI, but they are this mapping's own.
OPEN_LOW = 0
PRICE_SENTINEL = 99_999_999
"""The upper end of ``filterPrice`` when the range has none (PLN)."""
AREA_SENTINEL = 9_999
"""The upper end of ``filterSize`` when the range has none (m²)."""

SORT_PARAMS: Mapping[OfferSort, tuple[str, str]] = {
    OfferSort.PRICE_ASC: ("amount", "asc"),
    OfferSort.PRICE_DESC: ("amount", "desc"),
}
"""``sortBy`` and ``sortOrder`` of each order."""


def _bounds(found: PriceRange | AreaRange, sentinel: int) -> str:
    low = OPEN_LOW if found.low is None else found.low.value
    high = sentinel if found.high is None else found.high.value
    return f"{low}-{high}"


def offers_list_query(criteria: OfferSearchCriteria) -> Query:
    """The query parameters of the offers list for ``criteria``, in the UI's order."""
    params: Query = []
    if criteria.price is not None:
        params.append(("filterPrice", _bounds(criteria.price, PRICE_SENTINEL)))
    if criteria.area is not None:
        params.append(("filterSize", _bounds(criteria.area, AREA_SENTINEL)))
    if criteria.sort is not None:
        sort_by, sort_order = SORT_PARAMS[criteria.sort]
        params += [("sortBy", sort_by), ("sortOrder", sort_order)]
    params.append(("page", criteria.page.value))
    params.append(("perPage", criteria.per_page.value))
    return params
