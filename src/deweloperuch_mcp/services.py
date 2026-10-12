"""Domain services of the first vertical slice (D6): what the CLI and the MCP server expose.

The CLI and the MCP server open one ``Session`` per process and pass it to the
services; they never import ``deweloperuch_mcp.client``::

    with Session() as session:
        page = search_offers(session, "warszawa", price_max=700_000, sort="price_asc")

Each service checks its input first (``InvalidInputError``, nothing sent), calls the
client and maps DTOs to the domain model (``deweloperuch_mcp.domain``). Only parameters
marked [P] in docs/discovery/ reach the service. Not exposed until verified (flow B):

- list of offers: ``filterPricePerM2``, ``filterDeveloper``, ``filterProject``,
  ``filterDistrict``, ``filterStreet``, ``filterRooms``, ``filterFloors``,
  ``filterPriceChange``, ``filterStatus``, ``filterAnomalies``, ``includeArchived``,
  ``showArchivedInvestments``, ``sortBy`` other than ``amount``, ``perPage`` outside
  {10, 50, 100};
- locations: ``variant`` and ``propertyType``, ``page`` of ``/api/cities``, ``limit``
  values other than the UI's.

Errors are those of ``deweloperuch_mcp.errors``; their messages say, in domain terms,
what happened to the search, the investment or the offer and what to change. Technical
details (paths, statuses, bodies) stay in ``err.detail``.
"""

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Literal, Self

from deweloperuch_mcp import links
from deweloperuch_mcp.client import json_api, rsc
from deweloperuch_mcp.client.dto import InvestmentDto
from deweloperuch_mcp.client.transport import HttpClient
from deweloperuch_mcp.domain import normalize
from deweloperuch_mcp.domain.models import (
    Investment,
    LocationSearchResult,
    OfferDetail,
    OfferSearchResult,
)
from deweloperuch_mcp.errors import InvalidInputError, NotFoundError, ServiceError
from deweloperuch_mcp.throttle import (
    CLEAR_NOTICE_AFTER,
    CLEAR_WAIT_LIMIT,
    DEFAULT_MAX_WAIT,
    RequestLimiter,
)

# The STOP record of the shared limiter, for the CLI (``deweloperuch stop``), which may
# import only the services (D6).
from deweloperuch_mcp.throttle import LockWaitTimeout as LockWaitTimeout
from deweloperuch_mcp.throttle import StopRecord as StopRecord
from deweloperuch_mcp.throttle import StopStatus as StopStatus
from deweloperuch_mcp.throttle import UnreadableStop as UnreadableStop
from deweloperuch_mcp.throttle import format_time as format_time

WHOLE_COUNTRY = "polska"
"""The ``city`` of ``search_offers`` that searches the whole country [P]."""

MAX_PAGES = 20
"""[P] docs/discovery/pages-rsc.md, "Wspólne reguły list": ``page`` > 20 returns page 20."""

PER_PAGE_VALUES = (10, 50, 100)
"""[P] same section: other values (20, 500) silently fall back to 10."""

PerPage = Literal[10, 50, 100]
"""``PER_PAGE_VALUES`` as a type, for the CLI options and the MCP input schema."""

DEFAULT_PER_PAGE: PerPage = 10
"""The service's own default page size [P]."""

# [P z kodu] docs/discovery/pages-rsc.md, "Wspólne reguły list": the UI sends a range
# without a lower bound as 0-max and one without an upper bound as min-<sentinel>. What
# the server does with it is [W]; tests/test_services.py pins the values.
PRICE_LIMIT = 99_999_999
"""Upper sentinel of ``filterPrice`` (PLN); also the largest price accepted."""
AREA_LIMIT = 9_999
"""Upper sentinel of ``filterSize`` (m²); also the largest area accepted."""

CITIES_LIMIT = 8
"""``limit`` of ``/api/cities`` as the UI sends it [P] (sample ``api.cities_q``)."""
SUGGESTIONS_LIMIT = 6
"""``limit`` of ``/api/location-search`` as the UI sends it [P] (``api.location_search``)."""

QUERY_MIN, QUERY_MAX = 2, 100
SLUG_MAX = 200
OFFERS_LIMIT_MAX = 100_000

OfferSort = Literal["price_asc", "price_desc"]
"""Sort orders of ``search_offers``; ``None`` keeps the service's default order [P]."""

# Only sortBy=amount is [P]; the other sortBy values are [W z kodu] (pages-rsc.md).
_SORT_PARAMS: dict[str, tuple[str, str]] = {
    "price_asc": ("amount", "asc"),
    "price_desc": ("amount", "desc"),
}

# Slugs seen in the samples: lowercase ASCII letters, digits and hyphens. Anything else
# (Polish letters, `/`, `?`, `..`) is not a slug and must not reach a URL path.
_SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")


# --- the session ---------------------------------------------------------------------------


class Session:
    """The connection to the service that a process uses: one per process.

    Owns the HTTP client: the shared limiter (``limiter`` defaults to the lock shared
    with ``recon/``; ``max_wait`` is the longest pause before ``LimiterWaitError``) and
    the in-memory cache. After a STOP (401, 403, 429, challenge) in any session of the
    process, every service call that needs the network raises the same
    ``ServiceBlockedError`` without sending anything; only a new process may try again
    (CLAUDE.md: stop and report). The STOP is also recorded in the shared limiter, so
    other processes stop too until a person removes it (``clear_stop``) or, after a 429,
    until its pause ends. Close it at the end (``close()`` or ``with``); a closed session
    raises ``SessionClosedError``.
    """

    def __init__(
        self, *, limiter: RequestLimiter | None = None, max_wait: float = DEFAULT_MAX_WAIT
    ) -> None:
        self._http = HttpClient(limiter=limiter, max_wait=max_wait)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    @property
    def closed(self) -> bool:
        return self._http.closed


# --- services ------------------------------------------------------------------------------


def search_locations(session: Session, query: str) -> LocationSearchResult:
    """Cities, districts and streets whose name contains ``query``.

    Two requests: ``/api/cities`` (cities, with their offer counts) and
    ``/api/location-search`` (districts and streets with coordinates), both [P]. Use the
    ``city_slug`` of a result in ``search_offers``.
    """
    text = _query(query)
    with _about("Wyszukiwanie miast"):
        cities = json_api.cities(session._http, text, CITIES_LIMIT)
    with _about("Wyszukiwanie dzielnic i ulic"):
        found = json_api.location_search(session._http, text, SUGGESTIONS_LIMIT)
    items = [normalize.location_from_city(city) for city in cities.cityMappings]
    items += [normalize.location_from_suggestion(s) for s in found.suggestions]
    # [W] docs/discovery/endpoints.md, /api/cities: `hasMore` is in the response, but its
    # meaning is a conclusion (pagination is [H], `hasMore: true` never seen).
    # [W] /api/location-search has no such flag: a full page of suggestions may hide more.
    truncated = cities.hasMore or len(found.suggestions) >= SUGGESTIONS_LIMIT
    hint = None
    if truncated:
        hint = "Pasujących lokalizacji może być więcej: doprecyzuj nazwę (np. dodaj miasto)."
    elif not items:
        hint = (
            f"Nic nie pasuje do {text!r}. Sprawdź pisownię (z polskimi znakami) albo podaj "
            "początek nazwy miasta, dzielnicy lub ulicy."
        )
    return LocationSearchResult(
        total=None if truncated else len(items),
        returned=len(items),
        truncated=truncated,
        hint=hint,
        items=items,
    )


def search_offers(
    session: Session,
    city: str,
    *,
    price_min: int | None = None,
    price_max: int | None = None,
    area_min: int | None = None,
    area_max: int | None = None,
    sort: OfferSort | None = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> OfferSearchResult:
    """One page of developer apartment offers in ``city`` (a slug or ``polska``).

    Source: prop ``initialData`` of ``/ceny-ofertowe/{city}/mieszkania`` (RSC) [P].
    Prices in PLN and areas in m² as whole numbers; an open range is fine (only
    ``price_max``, only ``area_min``...). The service lets browse at most ``MAX_PAGES``
    pages of ``per_page``; ``truncated`` says when ``total`` is larger (D4).
    """
    city_slug = _slug(
        city, "city", "slug miasta (np. warszawa) albo polska; slug podaje search_locations"
    )
    params: list[tuple[str, str | int]] = []
    price = _range("price", price_min, price_max, PRICE_LIMIT, "PLN")
    if price is not None:
        params.append(("filterPrice", price))
    area = _range("area", area_min, area_max, AREA_LIMIT, "m²")
    if area is not None:
        params.append(("filterSize", area))
    if sort is not None:
        if not isinstance(sort, str) or sort not in _SORT_PARAMS:
            raise InvalidInputError(
                f"sort musi być jedną z wartości {', '.join(_SORT_PARAMS)} albo pusty "
                f"(domyślna kolejność serwisu), podano {sort!r}."
            )
        sort_by, sort_order = _SORT_PARAMS[sort]
        params += [("sortBy", sort_by), ("sortOrder", sort_order)]
    params.append(
        ("page", _whole("page", page, 1, MAX_PAGES, f" (serwis ma najwyżej {MAX_PAGES} stron)"))
    )
    if not _is_int(per_page) or per_page not in PER_PAGE_VALUES:
        raise InvalidInputError(
            f"per_page musi być jedną z wartości {', '.join(map(str, PER_PAGE_VALUES))} "
            f"(inne serwis zamienia na 10), podano {per_page!r}."
        )
    params.append(("perPage", per_page))
    with _about(
        f"Wyszukiwanie ofert w {city_slug!r}",
        not_found=(
            f"Serwis nie zna miasta {city_slug!r}. Podaj city_slug z search_locations "
            "albo polska (cały kraj)."
        ),
    ):
        page_dto = rsc.offers_list(session._http, city_slug, params)
    # The link to this list: the same parameters the request carried (D12).
    list_url = links.offers_list_url(city_slug, params)
    return normalize.offer_search_result(page_dto, max_pages=MAX_PAGES, list_url=list_url)


def get_investment(
    session: Session,
    investment_slug: str,
    *,
    include_history: bool = False,
    limit: int | None = None,
) -> Investment:
    """An investment with its developer and offers (active first).

    Source: ``/api/map/investments/visible/{slug}`` [P]; with ``include_history`` also
    ``/api/investments/{id}/sale-events`` [P] (one more request, slow when not cached).
    ``limit`` caps the offers returned; ``offers_omitted`` says how many were left out.
    """
    slug = _slug(investment_slug, "investment_slug", _INVESTMENT_SLUG_HELP)
    if not isinstance(include_history, bool):
        raise InvalidInputError(
            f"include_history musi być true albo false, podano {include_history!r}."
        )
    if limit is not None:
        _whole("limit", limit, 0, OFFERS_LIMIT_MAX, " (liczba ofert w wyniku)")
    investment = _investment(session._http, slug)
    history = None
    if include_history:
        with _about(
            f"Historia cen inwestycji {slug!r}",
            not_found=(
                f"Serwis nie ma historii cen ofert inwestycji {slug!r}. Pobierz inwestycję bez "
                "include_history, a historię pojedynczej oferty przez get_offer."
            ),
        ):
            history = json_api.investment_sale_events(session._http, investment.invest_id).root
    return normalize.investment(investment, limit=limit, history=history)


def get_offer(session: Session, offer_id: int, investment_slug: str) -> OfferDetail:
    """One offer of an investment with its full price history.

    Sources: ``/api/map/investments/visible/{slug}`` (the offer and its context) and
    ``/api/sale-events?saleId=`` (the history), both [P]. ``investment_slug`` is
    required: the service has no confirmed way from an offer id to its investment (T1).
    """
    oid = _whole("offer_id", offer_id, 1, 2**63 - 1, " (identyfikator oferty z search_offers)")
    slug = _slug(investment_slug, "investment_slug", _INVESTMENT_SLUG_HELP)
    investment = _investment(session._http, slug)
    sale = next((sale for sale in investment.sale if sale.sale_id == oid), None)
    if sale is None:
        raise NotFoundError(
            f"Inwestycja {slug!r} nie ma oferty {oid}. Sprawdź offer_id i investment_slug "
            "(oba podaje search_offers); wszystkie oferty inwestycji zwraca get_investment."
        )
    with _about(
        f"Historia ceny oferty {oid}",
        not_found=(
            f"Serwis nie ma historii ceny oferty {oid} z inwestycji {slug!r}. Sprawdź offer_id "
            "i investment_slug (oba podaje search_offers); ofertę bez historii pokazuje "
            "get_investment."
        ),
    ):
        events = json_api.sale_events(session._http, oid)
    return normalize.offer_detail(investment, sale, events.events)


# --- the STOP record --------------------------------------------------------------------------


def stop_status(limiter: RequestLimiter | None = None) -> StopStatus:
    """The STOP record of the shared limiter (``limiter`` defaults to the shared lock).

    Offline and immediate: reads a local file without waiting for the limiter's lock
    (``RequestLimiter.stop_status``), creates nothing, sends nothing.
    """
    return (limiter or RequestLimiter()).stop_status()


def clear_stop(
    limiter: RequestLimiter | None = None,
    *,
    wait_limit: float = CLEAR_WAIT_LIMIT,
    notice_after: float = CLEAR_NOTICE_AFTER,
    on_wait: Callable[[], None] | None = None,
) -> StopStatus:
    """Remove the STOP record; returns what it held. For people only: no MCP tool calls it.

    Offline. Waits for the limiter's lock: ``on_wait`` once after ``notice_after`` s,
    ``LockWaitTimeout`` (nothing removed) after ``wait_limit`` s. A process that has
    latched its own STOP still sends nothing until restarted; the pause a 429 recorded
    in the limiter still holds. Raises ``OSError`` when the record cannot be removed.
    """
    return (limiter or RequestLimiter()).clear_stop(
        wait_limit=wait_limit, notice_after=notice_after, on_wait=on_wait
    )


# --- errors of the client in domain terms ----------------------------------------------------


@contextmanager
def _about(subject: str, *, not_found: str | None = None) -> Iterator[None]:
    """Say what a client error is about: ``subject`` (e.g. "Inwestycja 'smolna'").

    ``NotFoundError`` becomes ``not_found`` (default: the subject and the client's
    message); ``ServiceError`` and ``UnexpectedResponseError`` keep their type and pause
    with the subject in front. ``detail`` stays. STOP, limiter and input errors pass
    unchanged: they are about the series of requests, not about this data.
    """
    try:
        yield
    except NotFoundError as err:
        raise NotFoundError(not_found or f"{subject}: {err}", detail=err.detail) from err
    except ServiceError as err:
        raise type(err)(f"{subject}: {err}", err.pause_seconds, detail=err.detail) from err


def _investment(http: HttpClient, slug: str) -> InvestmentDto:
    with _about(
        f"Inwestycja {slug!r}",
        not_found=(
            f"Nie znaleziono inwestycji {slug!r}. Slug inwestycji podaje search_offers "
            "(pole investment_slug)."
        ),
    ):
        return json_api.investment(http, slug)


# --- input ---------------------------------------------------------------------------------

_INVESTMENT_SLUG_HELP = "slug inwestycji, np. smolna; podaje go search_offers (investment_slug)"


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _whole(name: str, value: object, low: int, high: int, note: str = "") -> int:
    if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high:
        return value
    raise InvalidInputError(
        f"{name} musi być liczbą całkowitą z zakresu {low}–{high}{note}, podano {value!r}."
    )


def _range(name: str, low: object, high: object, limit: int, unit: str) -> str | None:
    """``min-max`` for a ``filter*`` parameter; an open end becomes ``0`` or ``limit``."""
    if low is None and high is None:
        return None
    note = f" ({unit})"
    lo = 0 if low is None else _whole(f"{name}_min", low, 0, limit, note)
    hi = limit if high is None else _whole(f"{name}_max", high, 0, limit, note)
    if lo > hi:
        raise InvalidInputError(
            f"{name}_min ({lo}) jest większe niż {name}_max ({hi}); zamień je miejscami."
        )
    return f"{lo}-{hi}"


def _slug(value: object, name: str, help_text: str) -> str:
    slug = value.strip() if isinstance(value, str) else ""
    if not slug or len(slug) > SLUG_MAX or not _SLUG.fullmatch(slug):
        raise InvalidInputError(f"{name}: oczekiwano {help_text}; podano {value!r}.")
    return slug


def _query(value: object) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not QUERY_MIN <= len(text) <= QUERY_MAX:
        raise InvalidInputError(
            f"query: podaj od {QUERY_MIN} do {QUERY_MAX} znaków nazwy miasta, dzielnicy "
            f"lub ulicy, podano {value!r}."
        )
    return text
