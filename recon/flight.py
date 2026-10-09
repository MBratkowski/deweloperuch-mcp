"""Decode Next.js RSC ("flight") payloads from deweloperuch.pl pages (stdlib only).

flight(path)                 -> concatenated flight text from a saved HTML page
                                (``self.__next_f.push`` chunks)
flight_from_html(html)       -> the same for HTML already in memory
find_json_after(text, prop)  -> every JSON value that follows ``"prop":`` in flight text
                                (works on raw RSC responses too)
component_props(text)        -> (name, value) of every client component prop

CLI: python3 recon/flight.py <page.html> <propName>  (Python 3.11 or newer)

Keep this file parseable by Python 3.9 (no ``match``, no ``except*``): Python compiles
the whole file before config's version check runs.
"""

# config goes first: it stops Python < 3.11 with a clear message before the annotations
# below (``str | os.PathLike[str]``) fail at definition time. No-op when probe imports us.
import config  # noqa: F401

# isort: split
import json
import os
import re
import sys
from collections.abc import Iterator
from typing import Any

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)
# A row of the RSC wire format whose payload is JSON: `<hex id>:[...]` or `<hex id>:{...}`.
# Other rows (`I[...]` imports, `HL[...]` hints, `T<len>,<text>` text) are skipped.
_JSON_ROW = re.compile(r"^[0-9a-f]+:(?=[\[{])", re.M)


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


def _main(page: str, key: str) -> None:
    for value in find_json_after(flight(page), key):
        if isinstance(value, dict):
            print(
                {
                    k: (f"{type(x).__name__}[{len(x)}]" if isinstance(x, list | dict) else x)
                    for k, x in value.items()
                }
            )
            for k, x in value.items():
                if isinstance(x, list) and x:
                    print("  ", k, "[0]=", json.dumps(x[0], ensure_ascii=False)[:1500])
        else:
            print(type(value).__name__, str(value)[:300])


if __name__ == "__main__":
    _main(sys.argv[1], sys.argv[2])
