"""Raw RSC responses of the service (tests/fixtures/rsc/), as test data.

Unlike the samples in docs/discovery/samples/ (the value of one prop), these are whole
``text/x-component`` bodies as the service sent them: text rows (``<id>:T<len>,``) with
JSON-LD right before the row with the data, no newline after them. Tests that go
through the wire format use these, not a payload built from assumptions
(``samples.rsc_payload``). Where a test needs specific offers, they are
spliced into the real frame (``offers_payload``): every other byte stays as sent.
See tests/fixtures/rsc/README.md for their source.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from support.paths import RSC_FIXTURES as FIXTURES

OFFERS_WARSZAWA = FIXTURES / "warszawa_perPage10.rsc"
"""``/ceny-ofertowe/warszawa/mieszkania?perPage=10``: ``initialData`` with 10 offers."""

OFFERS_UNKNOWN_CITY = FIXTURES / "unknown_city_perPage10.rsc"
"""``/ceny-ofertowe/nieistniejace-miasto/mieszkania?perPage=10``: HTTP 200, no
``initialData``, an error row with the digest ``NEXT_HTTP_ERROR_FALLBACK;404``."""

UNKNOWN_CITY = "nieistniejace-miasto"
"""The city slug the unknown-city payload was requested with."""

STATS_POLSKA = FIXTURES / "stats_gov_polska.rsc"
"""``/statystyki/statystyki-rzadowe/polska`` (build before 2.0): the root page of the
government statistics (GUS, NBP grid of cities), ``currentSlug`` null."""

STATS_WARSZAWA = FIXTURES / "stats_gov_warszawa.rsc"
"""``/statystyki/statystyki-rzadowe/warszawa`` (build before 2.0): a city with its own NBP
prices."""

STATS_WROCLAW_2_0 = FIXTURES / "stats_gov_wroclaw_20261030.rsc"
"""``/statystyki/wroclaw/dane-rzadowe`` of the 2.0 build: ``blocks.govSections``,
``citySlug``, ``data`` rows of dwellings, population and NBP, chart specs for the rest."""

STATS_POLSKA_2_0 = FIXTURES / "stats_gov_polska_20261030.rsc"
"""``/statystyki/polska/dane-rzadowe`` of the 2.0 build: no ``citySlug``, no NBP rows."""

STATS_FIXTURES = {"polska": STATS_POLSKA, "warszawa": STATS_WARSZAWA, "wroclaw": STATS_WROCLAW_2_0}
"""Location -> its real page (``polska`` and ``warszawa`` of the build before 2.0)."""

OFFERS_WROCLAW_2_0 = FIXTURES / "offers_wroclaw_perPage10_20261030.rsc"
"""``/ceny-ofertowe/wroclaw/mieszkania?perPage=10`` of the 2.0 build: ``sales`` with 10
offers and ``serverPaginationData`` (5,836 offers, 20 pages), no ``initialData``."""

DEVELOPER_ARCHICOM_2_0 = FIXTURES / "developer_archicom_polska_20261030.rsc"
"""``/ceny-ofertowe/polska/deweloperzy/archicom`` of the 2.0 build: ``developerName``,
``developerId``, ``investments`` ×6, the chart ``ceny-w-miastach`` with 3 cities."""

DEVELOPER_WARSZAWA = FIXTURES / "developer_atal_warszawa.rsc"
"""``/ceny-ofertowe/warszawa/deweloperzy/atal``: 4 investments, 14 cities."""

DEVELOPER_POLSKA = FIXTURES / "developer_atal_polska.rsc"
"""``/ceny-ofertowe/polska/deweloperzy/atal``: 42 investments, 14 cities (about 2 MB)."""

DEVELOPER_UNKNOWN = FIXTURES / "developer_unknown_warszawa.rsc"
"""``/ceny-ofertowe/warszawa/deweloperzy/nieistniejacy-deweloper``: HTTP 200 without data
and without the 404 digest, the heading „Deweloper nie znaleziony”."""

UNKNOWN_DEVELOPER = "nieistniejacy-deweloper"
"""The developer slug the unknown-developer payload was requested with."""

API_FIXTURES = FIXTURES.parent / "api"
CITY_SALES = {
    "sopot": API_FIXTURES / "city_sales_sopot.json",
    "krakow": API_FIXTURES / "city_sales_krakow.json",
}
"""City -> its real ``/api/offers/city-sales/{city}`` body (tests/fixtures/api/)."""

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


def prop_value_span(
    payload: bytes, prop: str, matches: Callable[[Any], bool] = lambda value: True
) -> tuple[int, int]:
    """Byte offsets (start, end) of the one value after ``"prop":`` that ``matches``.

    The page of the government statistics has several props called ``data``; ``matches``
    picks one by its value (e.g. rows with the key ``averageSizeM2``).
    """
    text = payload.decode("utf-8")
    decoder = json.JSONDecoder()
    key = f'"{prop}":'
    found: list[tuple[int, int]] = []
    start = text.find(key)
    while start >= 0:
        try:
            value, end = decoder.raw_decode(text, start + len(key))
        except ValueError:
            value, end = None, start + len(key)
        if value is not None and matches(value):
            found.append((start + len(key), end))
        start = text.find(key, end)
    assert len(found) == 1, f"{prop}: {len(found)} pasujących wartości"
    char_start, char_end = found[0]
    byte_start = len(text[:char_start].encode("utf-8"))
    return byte_start, byte_start + len(text[char_start:char_end].encode("utf-8"))


def rows_with(key: str) -> Callable[[Any], bool]:
    """A prop value that is a list of rows, the first of which has ``key``."""
    return lambda value: isinstance(value, list) and bool(value) and key in value[0]


def replace_prop(payload: bytes, prop: str, matches: Callable[[Any], bool], value: Any) -> bytes:
    """``payload`` with that one value replaced by ``value`` (compact JSON).

    The values sit in rows that end with a newline, and these pages have no text rows,
    so no byte length in the stream changes.
    """
    start, end = prop_value_span(payload, prop, matches)
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return payload[:start] + encoded + payload[end:]


def swap_props(
    payload: bytes, prop: str, first: Callable[[Any], bool], second: Callable[[Any], bool]
) -> bytes:
    """``payload`` with the values of two ``prop`` props swapped in place (as bytes)."""
    spans = sorted([prop_value_span(payload, prop, first), prop_value_span(payload, prop, second)])
    (a_start, a_end), (b_start, b_end) = spans
    assert a_end <= b_start
    return (
        payload[:a_start]
        + payload[b_start:b_end]
        + payload[a_end:b_start]
        + payload[a_start:a_end]
        + payload[b_end:]
    )
