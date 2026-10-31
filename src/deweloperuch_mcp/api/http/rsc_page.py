"""Reading a page as React Server Components (channel B, D1): ``RscPage``.

A page is requested with ``RSC: 1`` and an empty ``_rsc`` (the same request as
``recon/probe.py``: ``deweloperuch_mcp.flight.with_rsc_token``, with the evidence); the
response is flight text (``text/x-component``) whose client components carry the data in
props (docs/discovery/pages-rsc.md). If Cloudflare answers with the cached HTML page
instead, the same flight text is read from its ``self.__next_f.push`` scripts. A redirect,
a 410 or a 404 of another media type is a changed service (the transport, D21).

Prop names (``initialData``, ``tocItems``...) are an implementation detail of the site's
UI [W]: only the adapters name them, and the contract tests pin them to samples and to
real payloads (tests/fixtures/rsc/).

What a page answers for something the site does not know depends on the page
(docs/discovery/endpoints.md section 9, "Pages"), and either way it is a ``NotFoundError``:

- the offer lists and the developer page (an unknown city, district or developer): 200,
  without the data prop, with Next.js's 404 marker in an error row (``NOT_FOUND_DIGEST``),
  read here [P 2026-10-31; the offers list the same in 1.0, P 2026-10-10];
- the statistics pages (an unknown location): a 404 whose body is a flight stream
  (``text/x-component``), read by the transport for a page that opts in with
  ``unknown_404`` [P 2026-10-31, 2 of 2 routes]. On every other page a 404 is a changed
  service.

A page without the prop and without the marker does not match the contract
(``UnexpectedResponseError``).
"""

import json
from collections.abc import Callable, Iterator, Sequence
from typing import Any, TypeVar, overload

from pydantic import BaseModel

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.http.transport import NOT_FOUND, HttpClient, Reply
from deweloperuch_mcp.flight import (
    NOT_FOUND_DIGEST,
    component_props,
    error_digests,
    flight_from_html,
    rows,
    with_rsc_token,
)
from deweloperuch_mcp.http_policy import is_html
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError

M = TypeVar("M", bound=BaseModel)
T = TypeVar("T")

RSC_HEADERS = {"RSC": "1"}


class RscPage:
    """One page of the site at ``path`` with the query ``params`` (in their order), read
    as RSC through ``http`` (one GET under the D2 policy per read).

    ``unknown_404``: the route answers what it does not know with its own 404, a flight
    stream. The two statistics pages do [P 2026-10-31] (their adapters opt in). Without it
    a 404 of the page is a changed service (D21): the offer lists and the developer page
    answer an unknown entity with a 200 and Next.js's 404 marker, so a 404 there means the
    route is gone or was rebuilt.
    """

    def __init__(
        self,
        http: HttpClient,
        path: str,
        params: Sequence[tuple[str, str | int]] = (),
        *,
        unknown_404: bool = False,
    ) -> None:
        self._http = http
        self._path = path
        self._params = params
        self._unknown = (NOT_FOUND,) if unknown_404 else ()

    def prop(self, name: str, model: type[M], *, missing: str | None = None) -> M:
        """The first object-valued prop ``name`` of a client component, as ``model``.

        ``missing``: the ``h1`` of the page the service shows instead of the data when it
        does not know what was asked for (besides Next.js's 404 marker).
        """
        return self.read(lambda payload: self._prop(payload, name, model, missing))

    @overload
    def props(
        self, required: Sequence[str], optional: Sequence[str] = (), *, missing: str | None = None
    ) -> dict[str, Any]: ...

    @overload
    def props(
        self,
        required: Sequence[str],
        optional: Sequence[str] = (),
        *,
        missing: str | None = None,
        decode: Callable[[dict[str, Any]], T],
    ) -> T: ...

    def props(
        self,
        required: Sequence[str],
        optional: Sequence[str] = (),
        *,
        missing: str | None = None,
        decode: Callable[[dict[str, Any]], T] | None = None,
    ) -> dict[str, Any] | T:
        """The props ``required`` and ``optional`` of the page's client components, all from
        one request: name -> its first value that is an object or a list, as
        ``component_props`` yields them (the props of nested elements too); for a name
        with neither, its plain value (the developer page's ``developerName``,
        ``developerId``), which must be one: different plain values of one name in several
        components raise ``UnexpectedResponseError``, equal repeats are one value. ``null``
        and the references of the stream (strings starting with ``$``, e.g. ``$undefined``)
        are no values; an empty list or a 0 is a value. The caller validates each value
        with its own DTO (``Dto.validated``).

        ``decode``: what the caller makes of the props (its DTOs), run inside the transport's
        decode, so a reply whose props it refuses is never cached, as ``prop`` validates its
        model. Without it, the props as found.

        An optional prop that is absent or ``null`` gives ``None`` (a small town's
        ``latestSummary`` [P 2026-10-31]). A required one that is absent raises as ``prop``
        does: ``NotFoundError`` for a page with Next.js's 404 marker or the ``missing``
        heading, otherwise ``UnexpectedResponseError``.
        """

        def decoded(payload: str | bytes) -> dict[str, Any] | T:
            found = self._props(payload, required, optional, missing)
            return found if decode is None else decode(found)

        return self.read(decoded)

    def read(self, decode: Callable[[str | bytes], T]) -> T:
        """The page's flight stream decoded by ``decode`` (a page with several props)."""
        target = with_rsc_token(HttpClient.target(self._path, self._params))
        return self._http.get(
            target,
            headers=RSC_HEADERS,
            decode=lambda reply: decode(self._payload(reply)),
            unknown=self._unknown,
        )

    @staticmethod
    def headings(payload: str | bytes) -> list[str]:
        """The text of each ``h1`` element of the page's model rows, in order (only an
        ``h1`` whose children are plain text)."""
        return [text for tag, text in RscPage._elements(payload) if tag == "h1"]

    def _payload(self, reply: Reply) -> str | bytes:
        """The flight stream of a reply: the body as received (text rows give their length
        in bytes, deweloperuch_mcp.flight), or the stream of an HTML page's scripts."""
        if not is_html(reply.headers, reply.body):
            return reply.body
        try:
            return flight_from_html(reply.body.decode("utf-8", "replace"))
        except ValueError as err:
            raise UnexpectedResponseError(
                f"Serwis zwrócił stronę z nieczytelnymi danymi. {SERVICE_CHANGED}",
                detail=f"{self._path}: HTML z nieczytelnymi danymi RSC: {err}",
            ) from err

    def _prop(self, payload: str | bytes, name: str, model: type[M], missing: str | None) -> M:
        found: list[str] = []
        for prop, value in component_props(payload):
            if prop == name and isinstance(value, dict):
                return Dto.validated(model, value, f"{self._path} (prop {name})")
            if isinstance(value, dict | list) and prop not in found:
                found.append(prop)
        raise self._absent(payload, [name], found, missing)

    def _props(
        self,
        payload: str | bytes,
        required: Sequence[str],
        optional: Sequence[str],
        missing: str | None,
    ) -> dict[str, Any]:
        wanted = dict.fromkeys([*required, *optional])
        data: dict[str, Any] = {}
        plain: dict[str, list[Any]] = {}
        found: list[str] = []
        for prop, value in component_props(payload):
            if isinstance(value, dict | list):
                if prop in wanted:
                    data.setdefault(prop, value)
                if prop not in found:
                    found.append(prop)
            elif prop in wanted and self._is_plain(value):
                seen = plain.setdefault(prop, [])
                if not any(type(value) is type(other) and value == other for other in seen):
                    seen.append(value)
        values = {name: data.get(name, plain.get(name, [None])[0]) for name in wanted}
        absent = [name for name in required if values[name] is None]
        if absent:
            raise self._absent(payload, absent, found, missing)
        ambiguous = [name for name in wanted if name not in data and len(plain.get(name, [])) > 1]
        if ambiguous:
            raise UnexpectedResponseError(
                f"Dane z serwisu nie pasują do kontraktu klienta (inny format). {SERVICE_CHANGED}",
                detail="; ".join(
                    f"{self._path}: prop {name!r} ma kilka różnych wartości w komponentach strony"
                    for name in ambiguous
                ),
            )
        return values

    def _absent(
        self, payload: str | bytes, names: Sequence[str], found: Sequence[str], missing: str | None
    ) -> NotFoundError | UnexpectedResponseError:
        """Why the page lacks the props ``names``: the page of something the service does not
        know (Next.js's 404 marker, the ``missing`` heading), or a changed page; ``found``
        names the props with data the page has."""
        path = self._path
        shown = ", ".join(repr(name) for name in names)
        lacks = f"brak propsa {shown}" if len(names) == 1 else f"brak propsów {shown}"
        if NOT_FOUND_DIGEST in error_digests(payload):
            return NotFoundError(
                "Serwis nie zna żądanych danych (strona nie istnieje).",
                detail=f"{path}: {lacks}, strona zgłasza {NOT_FOUND_DIGEST}",
            )
        if missing is not None and missing in self.headings(payload):
            return NotFoundError(
                "Serwis nie zna żądanych danych (strona nie istnieje).",
                detail=f"{path}: {lacks}, strona ma nagłówek {missing!r}",
            )
        where = f"w propsie {shown}" if len(names) == 1 else f"w propsach {shown}"
        data = ", ".join(found[:10]) or "brak"
        return UnexpectedResponseError(
            f"Na stronie serwisu brakuje oczekiwanych danych. {SERVICE_CHANGED}",
            detail=f"{path} nie zawiera danych {where} (propsy z danymi: {data})",
        )

    @staticmethod
    def _is_plain(value: object) -> bool:
        """A value of a prop that is data although neither an object nor a list: not
        ``null`` and no reference of the stream (a string starting with ``$``; a text that
        starts with ``$`` is sent escaped as ``$$``, so it is skipped too)."""
        return value is not None and not (isinstance(value, str) and value.startswith("$"))

    @staticmethod
    def _elements(payload: str | bytes) -> Iterator[tuple[str, str]]:
        """``(tag, text)`` of each HTML element ``["$", tag, key, {"children": text}]``."""
        for row in rows(payload):
            if row.tag:
                continue
            try:
                tree = json.loads(row.text)
            except (ValueError, RecursionError):
                continue
            yield from RscPage._text_elements(tree)

    @staticmethod
    def _text_elements(tree: object) -> Iterator[tuple[str, str]]:
        """``(tag, text)`` of each element with text children in one decoded row (last
        children first)."""
        stack: list[object] = [tree]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                stack.extend(node.values())
            elif isinstance(node, list):
                element = RscPage._text_element(node)
                if element is not None:
                    yield element
                stack.extend(node)

    @staticmethod
    def _text_element(node: list[object]) -> tuple[str, str] | None:
        """``(tag, text)`` of an element ``["$", tag, key, {"children": text}]``; ``None``
        for any other list."""
        if len(node) < 4 or node[0] != "$":
            return None
        tag, props = node[1], node[3]
        if not isinstance(tag, str) or not isinstance(props, dict):
            return None
        text = props.get("children")
        return (tag, text) if isinstance(text, str) else None
