"""Reading a page as React Server Components (channel B, D1): ``RscPage``.

A page is requested with ``RSC: 1`` and a deterministic ``_rsc`` token (the same rule
as ``recon/probe.py``, ``deweloperuch_mcp.flight.with_rsc_token``); the response is flight
text (``text/x-component``) whose client components carry the data in props
(docs/discovery/pages-rsc.md). If Cloudflare answers with the cached HTML page instead,
the same flight text is read from its ``self.__next_f.push`` scripts.

Prop names (``initialData``, ``tocItems``...) are an implementation detail of the site's
UI [W]: only the adapters name them, and the contract tests pin them to samples and to
real payloads (tests/fixtures/rsc/).

A page the site does not know (e.g. an unknown city) still answers 200, without the
data prop and with Next.js's 404 marker in an error row (``NOT_FOUND_DIGEST``): that is
a ``NotFoundError``. A page without the prop and without the marker does not match the
contract (``UnexpectedResponseError``).
"""

import json
from collections.abc import Callable, Iterator, Sequence
from typing import TypeVar

from pydantic import BaseModel

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.http.transport import HttpClient, Reply
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
    as RSC through ``http`` (one GET under the D2 policy per read)."""

    def __init__(
        self, http: HttpClient, path: str, params: Sequence[tuple[str, str | int]] = ()
    ) -> None:
        self._http = http
        self._path = path
        self._params = params

    def prop(self, name: str, model: type[M], *, missing: str | None = None) -> M:
        """The first object-valued prop ``name`` of a client component, as ``model``.

        ``missing``: the ``h1`` of the page the service shows instead of the data when it
        does not know what was asked for (besides Next.js's 404 marker).
        """
        return self.read(lambda payload: self._prop(payload, name, model, missing))

    def read(self, decode: Callable[[str | bytes], T]) -> T:
        """The page's flight stream decoded by ``decode`` (a page with several props)."""
        target = with_rsc_token(HttpClient.target(self._path, self._params))
        return self._http.get(
            target, headers=RSC_HEADERS, decode=lambda reply: decode(self._payload(reply))
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
        path = self._path
        found: list[str] = []
        for prop, value in component_props(payload):
            if prop == name and isinstance(value, dict):
                return Dto.validated(model, value, f"{path} (prop {name})")
            if isinstance(value, dict | list) and prop not in found:
                found.append(prop)
        if NOT_FOUND_DIGEST in error_digests(payload):
            raise NotFoundError(
                "Serwis nie zna żądanych danych (strona nie istnieje).",
                detail=f"{path}: brak propsa {name!r}, strona zgłasza {NOT_FOUND_DIGEST}",
            )
        if missing is not None and missing in self.headings(payload):
            raise NotFoundError(
                "Serwis nie zna żądanych danych (strona nie istnieje).",
                detail=f"{path}: brak propsa {name!r}, strona ma nagłówek {missing!r}",
            )
        names = ", ".join(found[:10]) or "brak"
        raise UnexpectedResponseError(
            f"Na stronie serwisu brakuje oczekiwanych danych. {SERVICE_CHANGED}",
            detail=f"{path} nie zawiera danych w propsie {name!r} (propsy z danymi: {names})",
        )

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
