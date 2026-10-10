"""Samples from docs/discovery/samples/ as test data, without their trimming markers.

The samples are trimmed (CLAUDE.md, "Próbki"): a list ends with the string
``"... (N more, M total)"`` and a big id-keyed map has the key ``"..."``. DTOs do not
tolerate these markers, so tests remove them before validating. ``rsc_payload`` builds a
synthetic RSC response around props, for tests that need a particular shape; payloads
as the service sends them are in tests/fixtures/rsc/ (``rsc_fixtures``).
"""

import json
import re
from pathlib import Path
from typing import Any

SAMPLES = Path(__file__).resolve().parent.parent / "docs" / "discovery" / "samples"

LIST_MARKER = re.compile(r"\.\.\. \(\d+ more, \d+ total\)")
MAP_MARKER = "..."


def envelope(name: str) -> dict[str, Any]:
    """The whole sample file ``<name>.json`` (``_request``, ``_captured``, ...)."""
    data: dict[str, Any] = json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    return data


def untrimmed(value: Any) -> Any:
    """``value`` without trimming markers: the trailing list marker and the ``"..."`` key."""
    if isinstance(value, list):
        items = list(value)
        if items and isinstance(items[-1], str) and LIST_MARKER.fullmatch(items[-1]):
            items.pop()
        return [untrimmed(item) for item in items]
    if isinstance(value, dict):
        return {key: untrimmed(item) for key, item in value.items() if key != MAP_MARKER}
    return value


def body(name: str) -> Any:
    """The data of a sample (``response`` of an API sample, ``value`` of a page prop),
    without trimming markers."""
    data = envelope(name)
    return untrimmed(data["response"] if "response" in data else data["value"])


def request_target(name: str) -> str:
    """Path and query of the sample's request: ``GET /api/x?q=1`` -> ``/api/x?q=1``."""
    request = envelope(name)["_request"]
    assert isinstance(request, str)
    method, target = request.removesuffix(" (RSC)").split(" ", 1)
    assert method == "GET"
    return target


def rsc_payload(props: dict[str, Any]) -> bytes:
    """A synthetic RSC response (``text/x-component``) whose client component ``$L1f`` has
    ``props``: compact JSON, an import row, the data element nested in a server element,
    and a second element with a reference to the prop.

    Only for tests that need such a shape (a missing prop, a reference first, injected
    text). It lacks what the real pages have (text rows without a newline right before
    the data row), so data tests use ``rsc_fixtures.offers_payload`` instead.
    """
    encoded = json.dumps(props, ensure_ascii=False, separators=(",", ":"))
    return (
        '0:{"P":null,"b":"build-id","p":"","c":["","ceny-ofertowe"],"i":false}\n'
        '1f:I[4242,["static/chunks/4242.js"],"OffersList"]\n'
        '2:["$","div",null,{"className":"page","children":['
        f'["$","$L1f",null,{encoded}],'
        '["$","$L1f",null,{"initialData":"$2:props:initialData"}]]}]\n'
    ).encode()
