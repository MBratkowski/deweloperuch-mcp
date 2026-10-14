"""Decode Next.js RSC ("flight") payloads from deweloperuch.pl pages (stdlib only).

The decoder lives in the package (``deweloperuch_mcp.flight``), so recon and the
package's RSC adapter share one implementation; this module re-exports it through
config and adds a CLI:

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

# config goes first: it stops Python < 3.11 with a clear message and puts src/ on
# sys.path, where the decoder lives.
import config  # noqa: F401

# isort: split
import json
import sys

from config import component_props, find_json_after, flight, flight_from_html

__all__ = ["component_props", "find_json_after", "flight", "flight_from_html"]


def _main(page: str, key: str) -> None:
    for value in find_json_after(flight(page), key):
        if not isinstance(value, dict):
            print(type(value).__name__, str(value)[:300])
            continue
        print(
            {
                k: (f"{type(x).__name__}[{len(x)}]" if isinstance(x, list | dict) else x)
                for k, x in value.items()
            }
        )
        for k, x in ((k, x) for k, x in value.items() if isinstance(x, list) and x):
            print("  ", k, "[0]=", json.dumps(x[0], ensure_ascii=False)[:1500])


if __name__ == "__main__":
    _main(sys.argv[1], sys.argv[2])
