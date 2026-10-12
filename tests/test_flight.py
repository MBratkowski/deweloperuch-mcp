"""The flight decoder (``deweloperuch_mcp.flight``, re-exported by recon/flight.py).

Rows are split the way the site's React reads them; the real payloads in
tests/fixtures/rsc/ pin it (text rows without a newline, lengths in bytes).
"""

import ast
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import flight as recon_flight
from deweloperuch_mcp import flight as package_flight
from deweloperuch_mcp.flight import Row, error_digests, rows
from deweloperuch_mcp.infrastructure.deweloperuch.dto import OffersPageDto
from flight import component_props, find_json_after, flight, flight_from_html
from rsc_fixtures import OFFERS_UNKNOWN_CITY, OFFERS_WARSZAWA, raw

REPO = Path(__file__).resolve().parent.parent
FLIGHT = REPO / "recon" / "flight.py"
NOT_FOUND_DIGEST = "NEXT_HTTP_ERROR_FALLBACK;404"

# A raw RSC response (text/x-component) as the service sends it for `RSC: 1`.
RSC = (
    '0:{"P":null,"b":"build-id","p":"","c":["","ceny-ofertowe"],"i":false}\n'
    '1:I[12345,["static/chunks/1.js"],"OffersList"]\n'
    '2:["$","div",null,{"className":"page","children":['
    '["$","$L1",null,{"initialData":{"data":[{"sale_id":1}],"pagination":{"page":1}},'
    '"initialSortBy":"amount","children":"$undefined"}],'
    '["$","$L1",null,{"filters":[],"initialData":"$2:props:initialData"}]]}]\n'
    '3:T1a,text with "initialData":{ broken\n'
)


def html_page(*rows: str) -> str:
    """Rows wrapped the way Next.js inlines them into HTML (raw UTF-8, not ``\\u`` escapes)."""
    pushes = "".join(
        f"<script>self.__next_f.push([1,{json.dumps(row, ensure_ascii=False)}])</script>"
        for row in rows
    )
    return f"<!DOCTYPE html><html><body>{pushes}</body></html>"


def test_find_json_after_returns_every_decodable_value_in_order() -> None:
    values = find_json_after(RSC, "initialData")

    assert values == [
        {"data": [{"sale_id": 1}], "pagination": {"page": 1}},
        "$2:props:initialData",
    ]


def test_find_json_after_without_match() -> None:
    assert find_json_after(RSC, "missing") == []


def test_flight_from_html_joins_decoded_chunks() -> None:
    rows = ['0:{"b":"x"}\n', '2:["$","$L1",null,{"initialData":{"a":"ł\\"q"}}]\n']

    assert flight_from_html(html_page(*rows)) == "".join(rows)


def test_flight_reads_a_saved_page(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text(html_page(RSC), encoding="utf-8")

    assert flight(page) == RSC
    assert flight(str(page)) == RSC


def test_component_props_lists_client_component_props_in_document_order() -> None:
    props = [(name, value) for name, value in component_props(RSC)]

    assert props == [
        ("initialData", {"data": [{"sale_id": 1}], "pagination": {"page": 1}}),
        ("initialSortBy", "amount"),
        ("filters", []),
        ("initialData", "$2:props:initialData"),
    ]


def test_cli_prints_prop_summary(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text(html_page(RSC), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(FLIGHT), str(page), "initialData"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == "{'data': 'list[1]', 'pagination': 'dict[1]'}"
    assert lines[1] == '   data [0]= {"sale_id": 1}'
    assert lines[2] == "str $2:props:initialData"


def test_config_is_imported_first_and_file_parses_on_old_python() -> None:
    """config's version check can only run if Python 3.9 compiles flight.py first."""
    source = FLIGHT.read_text(encoding="utf-8")
    ast.parse(source, feature_version=(3, 9))
    body = ast.parse(source).body
    first = body[1] if isinstance(body[0], ast.Expr) else body[0]  # skip the docstring

    assert isinstance(first, ast.Import)
    assert [alias.name for alias in first.names] == ["config"]


def test_cli_on_old_python_exits_with_the_version_message(tmp_path: Path) -> None:
    code = f"""
import runpy, sys
sys.version_info = (3, 9, 6, "final", 0)
sys.path.insert(0, {str(FLIGHT.parent)!r})
sys.argv = ["flight.py", "page.html", "initialData"]
runpy.run_path({str(FLIGHT)!r}, run_name="__main__")
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=30,
        check=False,
    )

    assert result.returncode == 1
    assert "3.11" in result.stderr
    assert "Traceback" not in result.stderr


# --- one implementation ------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["component_props", "find_json_after", "flight", "flight_from_html"]
)
def test_recon_flight_reexports_the_package_decoder(name: str) -> None:
    """One implementation: recon and the package's RSC adapter decode the same way."""
    assert getattr(recon_flight, name) is getattr(package_flight, name)


def test_recon_flight_defines_no_decoder_of_its_own() -> None:
    tree = ast.parse(FLIGHT.read_text(encoding="utf-8"))
    defined = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert defined == {"_main"}


# --- the _rsc token ------------------------------------------------------------------


def test_rsc_token_is_a_short_hash_of_path_and_query() -> None:
    target = "/ceny-ofertowe/warszawa/mieszkania?page=2&perPage=50"

    assert package_flight.rsc_token(target) == hashlib.sha256(target.encode()).hexdigest()[:8]
    assert package_flight.rsc_token(target) != package_flight.rsc_token(target + "0")


@pytest.mark.parametrize(
    ("target", "expected_separator"),
    [
        ("/ceny-ofertowe/warszawa/mieszkania", "?"),
        ("/ceny-ofertowe/warszawa/mieszkania?page=2", "&"),
    ],
)
def test_with_rsc_token_appends_the_token_as_the_last_parameter(
    target: str, expected_separator: str
) -> None:
    token = package_flight.rsc_token(target)

    assert package_flight.with_rsc_token(target) == f"{target}{expected_separator}_rsc={token}"


def test_rsc_token_refuses_unencoded_targets() -> None:
    with pytest.raises(UnicodeEncodeError):
        package_flight.rsc_token("/ceny-ofertowe/kraków/mieszkania")


# --- rows of the wire format -----------------------------------------------------------


def split(payload: str | bytes) -> list[tuple[str, str, bytes]]:
    return [(row.id, row.tag, row.data) for row in rows(payload)]


def text_row(row_id: str, text: str) -> str:
    """``<id>:T<length in bytes, hex>,<text>``: no newline after it, as on the wire."""
    return f"{row_id}:T{len(text.encode('utf-8')):x},{text}"


def test_rows_split_ids_tags_and_data() -> None:
    payload = (
        '1:"$Sreact.fragment"\n'
        '2:I[4242,["static/chunks/4242.js"],"OffersList"]\n'
        ':HL["/_next/static/css/a.css","style"]\n'
        '0:{"b":"build"}\n'
        'f:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}\n'
        "11:null\n"
    )

    assert split(payload) == [
        ("1", "", b'"$Sreact.fragment"'),
        ("2", "I", b'[4242,["static/chunks/4242.js"],"OffersList"]'),
        ("", "H", b'L["/_next/static/css/a.css","style"]'),
        ("0", "", b'{"b":"build"}'),
        ("f", "E", b'{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}'),
        ("11", "", b"null"),
    ]


def test_hint_rows_have_an_empty_id() -> None:
    """Next.js sends hints (`:HL[...]`, preload a stylesheet) without an id; React reads
    an empty id as 0. The hint code (`L`) is part of the data."""
    assert split(':HL["/a.css","style"]\n0:{}\n') == [
        ("", "H", b'L["/a.css","style"]'),
        ("0", "", b"{}"),
    ]


def test_text_rows_are_followed_directly_by_the_next_row() -> None:
    payload = text_row("16", "first") + text_row("19", "second") + '1a:["$","$L18",null,{}]\n'

    assert split(payload) == [
        ("16", "T", b"first"),
        ("19", "T", b"second"),
        ("1a", "", b'["$","$L18",null,{}]'),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Średnia cena za m²: 18 187 zł",  # 2-byte letters and a no-break space
        "Mieszkania z obniżką względem ceny startowej",
        "dom 🏠 przy ulicy",  # a 4-byte character
        'tekst z "initialData":{ i\nnową linią\r\n',  # looks like data, is text
    ],
)
def test_text_row_length_counts_utf8_bytes_not_characters(text: str) -> None:
    payload = text_row("16", text) + '17:["$","$L1",null,{"p":{"a":1}}]\n'

    for given in (payload, payload.encode("utf-8")):
        assert split(given) == [
            ("16", "T", text.encode("utf-8")),
            ("17", "", b'["$","$L1",null,{"p":{"a":1}}]'),
        ]
    assert list(component_props(payload)) == [("p", {"a": 1})]


def test_text_row_of_length_zero() -> None:
    assert split('5:T0,6:{"a":1}\n') == [("5", "T", b""), ("6", "", b'{"a":1}')]


def test_text_row_at_the_end_of_the_stream() -> None:
    assert split('0:{"a":1}\n' + text_row("1", "koniec")) == [
        ("0", "", b'{"a":1}'),
        ("1", "T", b"koniec"),
    ]


@pytest.mark.parametrize("cut", ["1:T10,abc", "1:T10", "1:T", "1:Tzz,abc"])
def test_a_cut_off_text_row_ends_the_stream(cut: str) -> None:
    """Its declared length runs past the end (or is unreadable): no partial text, and
    nothing after it can be a row."""
    assert split('0:{"a":1}\n' + cut) == [("0", "", b'{"a":1}')]


def test_the_last_row_may_lack_its_newline() -> None:
    assert split('0:{"a":1}\n1:["$","$L1",null,{"p":{}}]') == [
        ("0", "", b'{"a":1}'),
        ("1", "", b'["$","$L1",null,{"p":{}}]'),
    ]


def test_crlf_line_endings() -> None:
    """React splits rows on LF only; the CR stays in the data and JSON ignores it."""
    payload = '0:{"a":1}\r\n1:["$","$L1",null,{"p":{"x":1}}]\r\n' + text_row("2", "a\r\nb")
    payload += '\r\n3:["$","$L1",null,{"q":{}}]\r\n'

    assert split(payload)[:3] == [
        ("0", "", b'{"a":1}\r'),
        ("1", "", b'["$","$L1",null,{"p":{"x":1}}]\r'),
        ("2", "T", b"a\r\nb"),
    ]
    assert list(component_props(payload)) == [("p", {"x": 1}), ("q", {})]


def test_blank_and_garbage_lines_are_skipped() -> None:
    assert split("\n\nnot a row\n0:{}\n\n1:[]\n") == [("0", "", b"{}"), ("1", "", b"[]")]


def test_binary_rows_are_read_by_length_too() -> None:
    """Typed arrays (`o`, `A`, `U`, ...) carry a byte length like `T` ([P z kodu]: the
    site's React, chunk 1517-4dca600cb4fa56f9.js); a newline inside is data."""
    payload = b'1:o3,\n\n\n2:A2,\x00\n3:{"a":1}\n'

    assert split(payload) == [
        ("1", "o", b"\n\n\n"),
        ("2", "A", b"\x00\n"),
        ("3", "", b'{"a":1}'),
    ]


def test_a_tag_is_an_uppercase_letter_hash_r_or_x() -> None:
    """Any other first character belongs to the data of a model row."""
    payload = '1:D{"a":1}\n2:#x\n3:r1\n4:x2\n5:[1]\n6:"s"\n7:123\n8:true\n'

    assert [(row.id, row.tag) for row in rows(payload)] == [
        ("1", "D"),
        ("2", "#"),
        ("3", "r"),
        ("4", "x"),
        ("5", ""),
        ("6", ""),
        ("7", ""),
        ("8", ""),
    ]
    assert next(rows(payload)).data == b'{"a":1}'


def test_row_text_is_the_decoded_data() -> None:
    row = Row("1", "T", "zł".encode())

    assert row.text == "zł"
    assert Row("1", "T", b"\xff").text == "�"


def test_error_digests_lists_the_digest_of_every_error_row() -> None:
    payload = (
        'f:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}\n'
        '1a:E{"message":"no digest"}\n'
        "1b:E{broken\n"
        '1c:{"digest":"not an error row"}\n'
        '1d:E{"digest":"NEXT_REDIRECT;replace;/x;307;"}\n'
    )

    assert error_digests(payload) == [NOT_FOUND_DIGEST, "NEXT_REDIRECT;replace;/x;307;"]
    assert error_digests('0:{"a":1}\n') == []


# --- the real payloads -----------------------------------------------------------------


def test_the_real_offers_page_has_text_rows_right_before_the_data_row() -> None:
    """The shape behind the bug of 2026-10-10: JSON-LD text rows, then the data row
    without a newline in between."""
    found = list(rows(raw(OFFERS_WARSZAWA)))
    text_rows = [row for row in found if row.tag == "T"]
    after = found[found.index(text_rows[-1]) + 1]

    assert [(row.id, len(row.data)) for row in text_rows] == [("16", 0x5ED), ("19", 0x1A27)]
    # Byte lengths: each text is whole JSON-LD (Polish letters in it); counting
    # characters would cut it and swallow the start of the next row.
    assert [json.loads(row.text)["@type"] for row in text_rows] == ["WebPage", "ItemList"]
    assert all(len(row.text) < len(row.data) for row in text_rows)
    assert after.tag == ""
    assert b'"initialData":' in after.data


def test_component_props_finds_the_offers_in_the_real_payload() -> None:
    values = [
        value for name, value in component_props(raw(OFFERS_WARSZAWA)) if name == "initialData"
    ]

    assert len(values) == 1
    page = OffersPageDto.model_validate(values[0])
    assert len(page.data) == 10
    assert page.pagination.perPage == 10
    assert page.pagination.page == 1
    assert page.pagination.total > 10
    assert all(offer.invest.city_slug == "warszawa" for offer in page.data)


def test_component_props_on_the_real_payload_inlined_in_html() -> None:
    """The HTML fallback: the same flight text in `self.__next_f.push` chunks."""
    text = raw(OFFERS_WARSZAWA).decode("utf-8")
    chunks = [text[i : i + 4096] for i in range(0, len(text), 4096)]

    names = [name for name, _ in component_props(flight_from_html(html_page(*chunks)))]

    assert "initialData" in names


def test_the_real_unknown_city_page_has_the_404_digest_and_no_data() -> None:
    payload = raw(OFFERS_UNKNOWN_CITY)

    assert error_digests(payload) == [NOT_FOUND_DIGEST]
    assert "initialData" not in [name for name, _ in component_props(payload)]
    # `notFound` is a prop of the layout on every page, so it says nothing by itself.
    assert b"notFound" in payload and b"notFound" in raw(OFFERS_WARSZAWA)
    assert error_digests(raw(OFFERS_WARSZAWA)) == []


# The decoder before 2026-10-10: JSON rows only at the start of a line.
_OLD_JSON_ROW = re.compile(r"^[0-9a-f]+:(?=[\[{])", re.M)


def old_component_props(text: str) -> Iterator[tuple[str, Any]]:
    decoder = json.JSONDecoder()
    for row in _OLD_JSON_ROW.finditer(text):
        try:
            tree, _ = decoder.raw_decode(text, row.end())
        except ValueError:
            continue
        stack: list[Any] = [tree]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                stack.extend(node.values())
            elif isinstance(node, list):
                if len(node) >= 4 and node[0] == "$" and str(node[1]).startswith("$L"):
                    yield from node[3].items()
                stack.extend(node)


def test_regression_line_based_rows_miss_the_real_offers() -> None:
    """Why `search_offers` failed on the live service: the data row follows a text row
    on the same line, so a decoder that looks for rows at line starts never sees it."""
    text = raw(OFFERS_WARSZAWA).decode("utf-8")

    assert "initialData" not in [name for name, _ in old_component_props(text)]
    assert "initialData" in [name for name, _ in component_props(text)]
