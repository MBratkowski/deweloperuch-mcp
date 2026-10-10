"""recon/flight.py decodes RSC ("flight") payloads offline with the package's decoder."""

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import flight as recon_flight
from deweloperuch_mcp import flight as package_flight
from flight import component_props, find_json_after, flight, flight_from_html

REPO = Path(__file__).resolve().parent.parent
FLIGHT = REPO / "recon" / "flight.py"

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
    """Rows wrapped the way Next.js inlines them into HTML."""
    pushes = "".join(f"<script>self.__next_f.push([1,{json.dumps(row)}])</script>" for row in rows)
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
