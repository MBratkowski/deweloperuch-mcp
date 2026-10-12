"""RSC adapter (channel B, D1): pages fetched as React Server Components, data from props.

A page is requested with ``RSC: 1`` and a deterministic ``_rsc`` token (the same rule
as ``recon/probe.py``, ``deweloperuch_mcp.flight.with_rsc_token``); the response is flight
text (``text/x-component``) whose client components carry the data in props
(docs/discovery/pages-rsc.md). If Cloudflare answers with the cached HTML page instead,
the same flight text is read from its ``self.__next_f.push`` scripts.

Prop names (``initialData``, ``tocItems``...) are an implementation detail of the site's
UI [W]: this module is the only place that knows them, and the contract tests pin them to
samples and to real payloads (tests/fixtures/rsc/). Two pages are read:

- the list of offers, ``/ceny-ofertowe/{city}/mieszkania``: prop ``initialData``;
- the government statistics, ``/statystyki/statystyki-rzadowe/{location}``: the table
  of contents, the list of locations and several props all called ``data``, told apart
  by the keys of their rows (``STATS_SHAPES``).

A page the site does not know (e.g. an unknown city) still answers 200, without the
data prop and with Next.js's 404 marker in an error row (``NOT_FOUND_DIGEST``): that is
a ``NotFoundError``. A page without the prop and without the marker does not match the
contract (``UnexpectedResponseError``).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any, TypeVar

from pydantic import BaseModel

from deweloperuch_mcp.domain.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError
from deweloperuch_mcp.flight import (
    component_props,
    error_digests,
    flight_from_html,
    with_rsc_token,
)
from deweloperuch_mcp.http_policy import is_html
from deweloperuch_mcp.infrastructure.deweloperuch.dto import (
    GovernmentStatsPageDto,
    OffersPageDto,
    validate,
)
from deweloperuch_mcp.infrastructure.deweloperuch.transport import (
    HttpClient,
    Reply,
    build_target,
    path_segment,
)

M = TypeVar("M", bound=BaseModel)

RSC_HEADERS = {"RSC": "1"}

NOT_FOUND_DIGEST = "NEXT_HTTP_ERROR_FALLBACK;404"
"""``digest`` of the error row of a page Next.js answers with ``notFound()``.

[P 2026-10-10] tests/fixtures/rsc/unknown_city_perPage10.rsc (an unknown city: HTTP 200,
no ``initialData``, docs/discovery/pages-rsc.md "Nieznane miasto"); the page of a known
city has no error row. The ``notFound`` prop is on every page, so it is no marker.
"""


def offers_list_path(city: str) -> str:
    """``/ceny-ofertowe/{city}/mieszkania`` [P]: ``city`` is a city slug or ``polska``.

    Also the path of the link to this list (``links``, D12).
    """
    return f"/ceny-ofertowe/{path_segment(city)}/mieszkania"


def offers_list(
    http: HttpClient, city: str, params: Sequence[tuple[str, str | int]]
) -> OffersPageDto:
    """Prop ``initialData`` of ``/ceny-ofertowe/{city}/mieszkania?<params>`` [P].

    ``city`` is a city slug or ``polska``; ``params`` go to the query in the given order.
    """
    path = offers_list_path(city)
    return page_prop(http, path, params, "initialData", OffersPageDto)


def page_prop(
    http: HttpClient,
    path: str,
    params: Sequence[tuple[str, str | int]],
    prop: str,
    model: type[M],
) -> M:
    """The first object-valued prop ``prop`` of a client component on the page, as ``model``."""
    target = with_rsc_token(build_target(path, params))
    return http.get(target, headers=RSC_HEADERS, decode=partial(_decode, path, prop, model))


def _flight_payload(path: str, reply: Reply) -> str | bytes:
    """The flight stream of a reply: the body as received (text rows give their length in
    bytes, deweloperuch_mcp.flight), or the stream of an HTML page's scripts."""
    if not is_html(reply.headers, reply.body):
        return reply.body
    try:
        return flight_from_html(reply.body.decode("utf-8", "replace"))
    except ValueError as err:
        raise UnexpectedResponseError(
            f"Serwis zwrócił stronę z nieczytelnymi danymi. {SERVICE_CHANGED}",
            detail=f"{path}: HTML z nieczytelnymi danymi RSC: {err}",
        ) from err


def _decode(path: str, prop: str, model: type[M], reply: Reply) -> M:
    payload = _flight_payload(path, reply)
    found: list[str] = []
    for name, value in component_props(payload):
        if name == prop and isinstance(value, dict):
            return validate(model, value, f"{path} (prop {prop})")
        if isinstance(value, dict | list) and name not in found:
            found.append(name)
    if NOT_FOUND_DIGEST in error_digests(payload):
        raise NotFoundError(
            "Serwis nie zna żądanych danych (strona nie istnieje).",
            detail=f"{path}: brak propsa {prop!r}, strona zgłasza {NOT_FOUND_DIGEST}",
        )
    names = ", ".join(found[:10]) or "brak"
    raise UnexpectedResponseError(
        f"Na stronie serwisu brakuje oczekiwanych danych. {SERVICE_CHANGED}",
        detail=f"{path} nie zawiera danych w propsie {prop!r} (propsy z danymi: {names})",
    )


# --- government statistics: /statystyki/statystyki-rzadowe/{location} ---------------------

STATS_WHOLE_COUNTRY = "polska"
"""The location of the root page of these statistics; its ``currentSlug`` is ``null`` [P]."""


@dataclass(frozen=True)
class StatsShape:
    """How rows of one kind of data prop look: every row has ``keys``.

    ``field``: where ``GovernmentStatsPageDto`` keeps them; ``group``: one table of the
    page (a page with two props of one group is ambiguous).
    """

    field: str
    group: str
    keys: frozenset[str]


def _shape(field: str, group: str, *keys: str) -> StatsShape:
    return StatsShape(field, group, frozenset(keys))


# [P 2026-10-11] tests/fixtures/rsc/stats_gov_polska.rsc and stats_gov_warszawa.rsc: the
# page has several props called `data`; each kind has keys no other kind has. A prop
# whose rows match none of these is not read (e.g. the NBP grid of cities on `polska`).
STATS_SHAPES = (
    _shape("dwellings_quarterly", "dwellings_quarterly", "quarter", "oddane", "rozpoczete"),
    _shape("dwellings_monthly", "dwellings_monthly", "month", "oddane", "rozpoczete"),
    _shape("average_area_yearly", "average_area", "year", "averageSizeM2"),
    _shape("demography_yearly", "demography", "year", "urodzenia", "zgony", "przyrostNaturalny"),
    _shape(
        "demography_monthly", "demography", "month", "urodzeniaZywe", "zgony", "przyrostNaturalny"
    ),
    _shape("population_yearly", "population", "year", "totalKobiety", "totalMezczyzni"),
    _shape("unemployment_monthly", "unemployment", "month", "rate"),
    _shape("wages_monthly", "wages", "month", "brutto"),
    _shape("wages_yearly", "wages", "year", "brutto"),
    _shape(
        "nbp_quarterly",
        "nbp",
        "quarter",
        "pierwotnyOfertowa",
        "pierwotnyTransakcyjna",
        "wtornyOfertowa",
        "wtornyTransakcyjna",
    ),
)


def government_stats_path(location: str) -> str:
    """``/statystyki/statystyki-rzadowe/{location}`` [P]: ``polska``, an aggregate or a
    city of the page's list (``sortedLocations``).

    Also the path of the link to these statistics (``links``, D12).
    """
    return f"/statystyki/statystyki-rzadowe/{path_segment(location)}"


def government_stats(http: HttpClient, location: str) -> GovernmentStatsPageDto:
    """The table of contents, the list of locations and every data prop the page has.

    Raises ``NotFoundError`` for a page Next.js answers with ``notFound()`` and
    ``UnexpectedResponseError`` for a page without the table of contents, one that is
    about another location (``currentSlug``), or one whose data props are ambiguous.
    """
    path = government_stats_path(location)
    target = with_rsc_token(build_target(path))
    return http.get(
        target, headers=RSC_HEADERS, decode=partial(_decode_government_stats, path, location)
    )


def _decode_government_stats(path: str, location: str, reply: Reply) -> GovernmentStatsPageDto:
    payload = _flight_payload(path, reply)
    toc: list[Any] | None = None
    locations: list[Any] | None = None
    current: list[object] = []
    tables: dict[str, list[Any]] = {}
    groups: dict[str, str] = {}
    found: list[str] = []
    for name, value in component_props(payload):
        if isinstance(value, dict | list) and name not in found:
            found.append(name)
        if name == "tocItems" and isinstance(value, list) and toc is None:
            toc = value
        elif name == "sortedLocations" and isinstance(value, list) and locations is None:
            locations = value
        elif name == "currentSlug" and (value is None or isinstance(value, str)):
            current.append(value)
        elif shape := _stats_shape(path, name, value):
            if shape.group in groups:
                raise _ambiguous(path, f"dwa propsy z danymi {shape.group}: {name}, {groups}")
            groups[shape.group] = name
            tables[shape.field] = value
    if toc is None:
        if NOT_FOUND_DIGEST in error_digests(payload):
            raise NotFoundError(
                "Serwis nie zna żądanych danych (strona nie istnieje).",
                detail=f"{path}: brak propsa 'tocItems', strona zgłasza {NOT_FOUND_DIGEST}",
            )
        names = ", ".join(found[:10]) or "brak"
        raise UnexpectedResponseError(
            f"Na stronie serwisu brakuje oczekiwanych danych. {SERVICE_CHANGED}",
            detail=f"{path} nie zawiera spisu treści 'tocItems' (propsy z danymi: {names})",
        )
    # [P 2026-10-11] `currentSlug` is the requested city (warszawa) or null (polska). A page
    # about another location (e.g. a fallback for an unknown one, [H]) is not this one's.
    expected = None if location == STATS_WHOLE_COUNTRY else location
    if not current or any(slug != expected for slug in current):
        raise UnexpectedResponseError(
            f"Serwis zwrócił statystyki innej lokalizacji niż żądana. {SERVICE_CHANGED}",
            detail=f"{path}: currentSlug {current!r}, oczekiwano {expected!r}",
        )
    data = {"tocItems": toc, **tables}
    if locations is not None:
        data["sortedLocations"] = locations
    return validate(GovernmentStatsPageDto, data, f"{path} (statystyki rządowe)")


def _stats_shape(path: str, name: str, value: object) -> StatsShape | None:
    """The one shape whose keys every row of ``value`` has; ``None`` for anything else."""
    if not isinstance(value, list) or not value or not all(isinstance(r, dict) for r in value):
        return None
    shapes = [s for s in STATS_SHAPES if all(s.keys <= row.keys() for row in value)]
    if len(shapes) > 1:
        raise _ambiguous(path, f"prop {name} pasuje do {[s.field for s in shapes]}")
    return shapes[0] if shapes else None


def _ambiguous(path: str, what: str) -> UnexpectedResponseError:
    return UnexpectedResponseError(
        f"Dane na stronie serwisu są niejednoznaczne. {SERVICE_CHANGED}",
        detail=f"{path}: {what}",
    )
