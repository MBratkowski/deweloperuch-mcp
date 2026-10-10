"""RSC adapter (channel B, D1): pages fetched as React Server Components, data from props.

A page is requested with ``RSC: 1`` and a deterministic ``_rsc`` token (the same rule
as ``recon/probe.py``, ``deweloperuch_mcp.flight.with_rsc_token``); the response is flight
text (``text/x-component``) whose client components carry the data in props
(docs/discovery/pages-rsc.md). If Cloudflare answers with the cached HTML page instead,
the same flight text is read from its ``self.__next_f.push`` scripts.

Prop names (``initialData``) are an implementation detail of the site's UI [W]: this
module is the only place that knows them, and the contract tests pin them to samples and
to real payloads (tests/fixtures/rsc/).

A page the site does not know (e.g. an unknown city) still answers 200, without the
data prop and with Next.js's 404 marker in an error row (``NOT_FOUND_DIGEST``): that is
a ``NotFoundError``. A page without the prop and without the marker does not match the
contract (``UnexpectedResponseError``).
"""

from collections.abc import Sequence
from functools import partial
from typing import TypeVar

from pydantic import BaseModel

from deweloperuch_mcp.client.dto import OffersPageDto, validate
from deweloperuch_mcp.client.transport import HttpClient, Reply, build_target, path_segment
from deweloperuch_mcp.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError
from deweloperuch_mcp.flight import (
    component_props,
    error_digests,
    flight_from_html,
    with_rsc_token,
)
from deweloperuch_mcp.http_policy import is_html

M = TypeVar("M", bound=BaseModel)

RSC_HEADERS = {"RSC": "1"}

NOT_FOUND_DIGEST = "NEXT_HTTP_ERROR_FALLBACK;404"
"""``digest`` of the error row of a page Next.js answers with ``notFound()``.

[P 2026-10-10] tests/fixtures/rsc/unknown_city_perPage10.rsc (an unknown city: HTTP 200,
no ``initialData``, docs/discovery/pages-rsc.md "Nieznane miasto"); the page of a known
city has no error row. The ``notFound`` prop is on every page, so it is no marker.
"""


def offers_list(
    http: HttpClient, city: str, params: Sequence[tuple[str, str | int]]
) -> OffersPageDto:
    """Prop ``initialData`` of ``/ceny-ofertowe/{city}/mieszkania?<params>`` [P].

    ``city`` is a city slug or ``polska``; ``params`` go to the query in the given order.
    """
    path = f"/ceny-ofertowe/{path_segment(city)}/mieszkania"
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


def _decode(path: str, prop: str, model: type[M], reply: Reply) -> M:
    # The body as received: text rows give their length in bytes (deweloperuch_mcp.flight).
    payload: str | bytes = reply.body
    if is_html(reply.headers, reply.body):
        try:
            payload = flight_from_html(reply.body.decode("utf-8", "replace"))
        except ValueError as err:
            raise UnexpectedResponseError(
                f"Serwis zwrócił stronę z nieczytelnymi danymi. {SERVICE_CHANGED}",
                detail=f"{path}: HTML z nieczytelnymi danymi RSC: {err}",
            ) from err
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
