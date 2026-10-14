"""Next.js RSC ("flight") pages of deweloperuch.pl: how to request them, how to decode them.

The one implementation, shared by the package's RSC adapter and the ``recon/`` scripts
(through ``recon/config.py``; ``recon/flight.py`` re-exports it and adds a CLI)::

    rsc_token(target)            -> ``_rsc`` value for a path with query (deterministic)
    with_rsc_token(target)       -> the path with ``_rsc=<token>`` appended to its query
    flight_from_html(html)       -> concatenated flight text from the inline scripts of a page
                                    (``self.__next_f.push``)
    flight(path)                 -> the same for a saved HTML page
    find_json_after(text, prop)  -> every JSON value that follows ``"prop":`` in flight text
                                    (works on raw RSC responses too)
    rows(payload)                -> the rows of a flight stream (``Row``: id, tag, data)
    component_props(payload)     -> (name, value) of every client component prop
    error_digests(payload)       -> ``digest`` of every error row (e.g. Next.js 404)

``payload`` is a raw RSC response (bytes, as received) or flight text (``str``, e.g.
from ``flight_from_html``); lengths in the stream count UTF-8 bytes either way.

Keep this module free of imports outside the standard library: ``recon/`` scripts load
it without installing the package or its dependencies.
"""

import hashlib
import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)

# The wire format as the site's React reads it ([P z kodu] ReactFlightClient in chunk
# 1517-4dca600cb4fa56f9.js, read 2026-10-10; tests/fixtures/rsc/ holds real payloads):
#
# - a row starts with `<hex id>:` (hints are sent with an empty id) and a tag;
# - `T` (text) and the binary rows (typed arrays) then give `<hex length>,` and exactly
#   that many BYTES of data, with no newline after them: the next row starts right there;
# - every other row ends at `\n`. Its tag is an uppercase letter, `#`, `r` or `x`
#   (`I` import, `H` hint, `E` error, ...); any other character starts the data of a
#   model row (JSON: elements and their props), which has no tag.
_LENGTH_TAGS = frozenset(b"TAOoUSsLlGgMmV")
_LINE_TAGS = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ#rx") - _LENGTH_TAGS
_ROW_ID = re.compile(rb"([0-9a-fA-F]*):")
_LENGTH = re.compile(rb"([0-9a-fA-F]+),")


def rsc_token(target: str) -> str:
    """``_rsc`` for a path with query: stable, so Cloudflare can cache the RSC response.

    Cloudflare ignores ``Vary: RSC``, so without ``_rsc`` the page comes back as cached
    HTML (docs/discovery/pages-rsc.md). ``target`` is the percent-encoded path and query
    without the token, e.g. ``/ceny-ofertowe/warszawa/mieszkania?page=2``; non-ASCII
    raises ``UnicodeEncodeError``.
    """
    return hashlib.sha256(target.encode("ascii")).hexdigest()[:8]


def with_rsc_token(target: str) -> str:
    """``target`` with ``_rsc=<rsc_token(target)>`` as the last query parameter."""
    return target + ("&" if "?" in target else "?") + "_rsc=" + rsc_token(target)


def flight_from_html(html: str) -> str:
    """Concatenated, unescaped flight text from the inline scripts of a page."""
    return "".join(json.loads(f'"{chunk}"') for chunk in _PUSH.findall(html))


def flight(path: str | os.PathLike[str]) -> str:
    """Concatenated flight text from a saved HTML page."""
    with open(path, encoding="utf-8") as page:
        return flight_from_html(page.read())


def find_json_after(text: str, key: str) -> list[Any]:
    """Every JSON value right after ``"key":`` in ``text``, in order; undecodable ones skipped."""
    decoder = json.JSONDecoder()
    out = []
    for match in re.finditer(re.escape(f'"{key}":'), text):
        try:
            value, _ = decoder.raw_decode(text, match.end())
        except (ValueError, RecursionError):
            continue
        out.append(value)
    return out


@dataclass(frozen=True)
class Row:
    """One row of a flight stream: ``<id>:<tag><data>``.

    ``tag`` is ``""`` for a model row (JSON) or one character (``I``, ``H``, ``E``,
    ``T``...). ``data`` is everything after the tag (after ``<length>,`` for a text or
    binary row), without the newline that ends a row.
    """

    id: str
    tag: str
    data: bytes

    @property
    def text(self) -> str:
        """``data`` decoded as UTF-8 (invalid bytes replaced)."""
        return self.data.decode("utf-8", "replace")


def rows(payload: str | bytes) -> Iterator[Row]:
    """The rows of a flight stream, in order.

    A line that does not start like a row (blank, a stray ``\\r``, garbage) is skipped.
    A text or binary row whose length runs past the end, or cannot be read, ends the
    stream: everything after its header would be part of its data. The last row may
    lack its newline. References (``"$..."``) are not resolved.
    """
    data = payload.encode("utf-8", "surrogatepass") if isinstance(payload, str) else payload
    end = len(data)
    pos = 0
    while pos < end:
        head = _ROW_ID.match(data, pos)
        if head is None:
            newline = data.find(b"\n", pos)
            if newline < 0:
                return
            pos = newline + 1
            continue
        row_id = head[1].decode("ascii")
        pos = head.end()
        tag = data[pos] if pos < end else -1
        if tag in _LENGTH_TAGS:
            length = _LENGTH.match(data, pos + 1)
            if length is None:
                return
            start = length.end()
            stop = start + int(length[1], 16)
            if stop > end:
                return
            yield Row(row_id, chr(tag), data[start:stop])
            pos = stop
            continue
        name = ""
        if tag in _LINE_TAGS:
            name, pos = chr(tag), pos + 1
        newline = data.find(b"\n", pos)
        stop = end if newline < 0 else newline
        yield Row(row_id, name, data[pos:stop])
        pos = stop + 1


def component_props(payload: str | bytes) -> Iterator[tuple[str, Any]]:
    """``(name, value)`` of each prop of each client component, in document order.

    Client components are elements ``["$", "$L<id>", key, {props}]`` in model rows;
    their props carry the page data (``initialData``, ``serverPaginationData``, ...).
    ``children`` is skipped. Values that are references (``"$2:props:..."``) are
    yielded as they are.
    """
    for tree in _model_trees(payload):
        for node in _lists_in(tree):
            if _is_client_element(node):
                yield from ((k, v) for k, v in node[3].items() if k != "children")


NOT_FOUND_DIGEST = "NEXT_HTTP_ERROR_FALLBACK;404"
"""``digest`` of the error row of a page Next.js answers with ``notFound()``.

[P 2026-10-10] tests/fixtures/rsc/unknown_city_perPage10.rsc (an unknown city: HTTP 200,
no ``initialData``, docs/discovery/pages-rsc.md "Nieznane miasto"); the page of a known
city has no error row. The ``notFound`` prop is on every page, so it is no marker.
"""


def error_digests(payload: str | bytes) -> list[str]:
    """``digest`` of each error row (``<id>:E{"digest": ...}``), in order.

    Next.js reports ``notFound()`` of a page this way, in a 200 response
    (``NEXT_HTTP_ERROR_FALLBACK;404``); error rows without a digest are skipped.
    """
    found: list[str] = []
    for row in rows(payload):
        if row.tag != "E":
            continue
        try:
            value = json.loads(row.text)
        except (ValueError, RecursionError):
            continue
        if isinstance(value, dict) and isinstance(value.get("digest"), str):
            found.append(value["digest"])
    return found


def _model_trees(payload: str | bytes) -> Iterator[Any]:
    """The decoded JSON of each model row (untagged), in order; rows that are not JSON
    are skipped."""
    for row in rows(payload):
        if row.tag:
            continue
        try:
            tree = json.loads(row.text)
        except (ValueError, RecursionError):
            continue
        yield tree


def _lists_in(tree: Any) -> Iterator[list[Any]]:
    """Every list in ``tree``, ``tree`` included, in document order (depth first)."""
    stack: list[Any] = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            stack.extend(reversed(node.values()))
        elif isinstance(node, list):
            yield node
            stack.extend(reversed(node))


def _is_client_element(node: list[Any]) -> bool:
    return (
        len(node) >= 4
        and node[0] == "$"
        and isinstance(node[1], str)
        and node[1].startswith("$L")
        and isinstance(node[3], dict)
    )
