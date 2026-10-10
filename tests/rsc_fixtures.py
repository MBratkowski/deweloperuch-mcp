"""Raw RSC responses of the service (tests/fixtures/rsc/), as test data.

Unlike the samples in docs/discovery/samples/ (the value of one prop), these are whole
``text/x-component`` bodies as the service sent them: text rows (``<id>:T<len>,``) with
JSON-LD right before the row with the data, no newline after them. Tests that go
through the wire format use these, not a payload built from assumptions
(``discovery_samples.rsc_payload``). Where a test needs specific offers, they are
spliced into the real frame (``offers_payload``): every other byte stays as sent.
See tests/fixtures/rsc/README.md for their source.
"""

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "rsc"

OFFERS_WARSZAWA = FIXTURES / "warszawa_perPage10.rsc"
"""``/ceny-ofertowe/warszawa/mieszkania?perPage=10``: ``initialData`` with 10 offers."""

OFFERS_UNKNOWN_CITY = FIXTURES / "unknown_city_perPage10.rsc"
"""``/ceny-ofertowe/nieistniejace-miasto/mieszkania?perPage=10``: HTTP 200, no
``initialData``, an error row with the digest ``NEXT_HTTP_ERROR_FALLBACK;404``."""

UNKNOWN_CITY = "nieistniejace-miasto"
"""The city slug the unknown-city payload was requested with."""

_PROP = b'"initialData":'


def raw(path: Path = OFFERS_WARSZAWA) -> bytes:
    """The body of a fixture, byte for byte."""
    return path.read_bytes()


def initial_data_span(payload: bytes) -> tuple[int, int]:
    """Byte offsets of the one ``initialData`` value in ``payload`` (start, end)."""
    assert payload.count(_PROP) == 1
    start = payload.index(_PROP) + len(_PROP)
    text = payload.decode("utf-8")
    char_start = len(payload[:start].decode("utf-8"))
    _, char_end = json.JSONDecoder().raw_decode(text, char_start)
    return start, start + len(text[char_start:char_end].encode("utf-8"))


def offers_payload(page: Any = None) -> bytes:
    """The real offers page of Warsaw; with ``page``, its ``initialData`` replaced by it.

    The value sits in a row that ends with a newline, after the text rows, so their
    byte lengths stay right whatever ``page`` is.
    """
    payload = raw(OFFERS_WARSZAWA)
    if page is None:
        return payload
    start, end = initial_data_span(payload)
    value = json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return payload[:start] + value + payload[end:]
