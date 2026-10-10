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
    component_props(text)        -> (name, value) of every client component prop

Keep this module free of imports outside the standard library: ``recon/`` scripts load
it without installing the package or its dependencies.
"""

import hashlib
import json
import os
import re
from collections.abc import Iterator
from typing import Any

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)
# A row of the RSC wire format whose payload is JSON: `<hex id>:[...]` or `<hex id>:{...}`.
# Other rows (`I[...]` imports, `HL[...]` hints, `T<len>,<text>` text) are skipped.
_JSON_ROW = re.compile(r"^[0-9a-f]+:(?=[\[{])", re.M)


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


def component_props(text: str) -> Iterator[tuple[str, Any]]:
    """``(name, value)`` of each prop of each client component, in document order.

    Client components are elements ``["$", "$L<id>", key, {props}]``; their props carry
    the page data (``initialData``, ``serverPaginationData``, ...). ``children`` is
    skipped. Values that are references (``"$2:props:..."``) are yielded as they are.
    """
    decoder = json.JSONDecoder()
    for row in _JSON_ROW.finditer(text):
        try:
            tree, _ = decoder.raw_decode(text, row.end())
        except (ValueError, RecursionError):
            continue
        stack: list[Any] = [tree]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                stack.extend(reversed(node.values()))
            elif isinstance(node, list):
                if _is_client_element(node):
                    yield from ((k, v) for k, v in node[3].items() if k != "children")
                stack.extend(reversed(node))


def _is_client_element(node: list[Any]) -> bool:
    return (
        len(node) >= 4
        and node[0] == "$"
        and isinstance(node[1], str)
        and node[1].startswith("$L")
        and isinstance(node[3], dict)
    )
