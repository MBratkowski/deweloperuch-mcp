"""recon/place_names.py: the packaged table of place names from a saved ``tx-cities`` body.

Offline: the generator reads the captures of 2026-11-02 (tests/fixtures/api/) and its
output is compared with the table the package ships
(``src/deweloperuch_mcp/api/data/place_names.json``).
"""

import ast
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import place_names
from support.paths import API_FIXTURES, PACKAGE_SOURCE, RECON

TX_CITIES = API_FIXTURES / "tx_cities_20261102.json"
GOV_MAP_STATS = API_FIXTURES / "gov_map_stats_20261102.json"
PACKAGED = PACKAGE_SOURCE / "api" / "data" / "place_names.json"


def body(path: Path) -> Any:
    return json.loads(path.read_bytes())


def test_the_packaged_table_is_the_generators_output(tmp_path: Path) -> None:
    """After a new capture: python3 recon/place_names.py <tx-cities> <gov-map-stats>
    src/deweloperuch_mcp/api/data/place_names.json, then review the diff."""
    written = tmp_path / "place_names.json"

    place_names.main([str(TX_CITIES), str(GOV_MAP_STATS), str(written)])

    assert written.read_bytes() == PACKAGED.read_bytes()


def test_every_powiat_and_every_city_of_the_capture_has_one_name() -> None:
    """[P 2026-11-02]: 380 powiats with one name each, and a name for each of the 66
    cities of the government indicators, the ambiguous slugs included."""
    table = place_names.table(body(TX_CITIES), body(GOV_MAP_STATS))

    assert len(table["powiats"]) == 380
    assert table["powiats"]["302"] == "powiat Warszawa"
    assert len(table["cities"]) == 66
    assert table["cities"]["warszawa"] == "Warszawa"
    # As its powiat and the service's pages write it, not the register's Jastrzębie-zdrój.
    assert table["cities"]["jastrzebie-zdroj"] == "Jastrzębie-Zdrój"


@pytest.mark.parametrize(
    ("slug", "name", "rows"),
    [
        # [P 2026-11-02] the city with powiat rights against a village of the same name
        ("rzeszow", "Rzeszów", 2),
        ("zamosc", "Zamość", 3),
        ("leszno", "Leszno", 2),
        # [P 2026-11-01] the one slug of tx-cities that is not lowercase: two rows of the
        # same powiat, `tarnobrzeg` and `Tarnobrzeg`, with one name
        ("tarnobrzeg", "Tarnobrzeg", 2),
    ],
)
def test_an_ambiguous_slug_takes_the_city_with_powiat_rights(
    slug: str, name: str, rows: int
) -> None:
    cities = body(TX_CITIES)["cities"]
    same = [row for row in cities if row["slug"].lower() == slug]

    assert len(same) == rows
    assert place_names.table(body(TX_CITIES), body(GOV_MAP_STATS))["cities"][slug] == name


@pytest.mark.parametrize("slug", ["bielsko-biala", "jastrzebie-zdroj"])
def test_a_city_is_named_as_its_powiat_writes_it(slug: str) -> None:
    """[P 2026-11-02] the register names the place `Bielsko-biała`, its powiat
    `powiat Bielsko-Biała`; the service's pages write the latter."""
    (row,) = [row for row in body(TX_CITIES)["cities"] if row["slug"] == slug]

    name = place_names.table(body(TX_CITIES), body(GOV_MAP_STATS))["cities"][slug]

    assert row["name"] != name and row["name"].lower() == name.lower()
    assert row["powiat"] == f"powiat {name}"


def test_the_city_of_powiat_rights_is_found_without_regard_to_case() -> None:
    """A village of the same slug in another powiat is left aside; the city's own powiat
    matches its name only when case is ignored."""
    rows = [
        {"slug": "x-y", "name": "X-y", "powiatId": 1, "powiat": "powiat X-Y"},
        {"slug": "x-y", "name": "X-y", "powiatId": 2, "powiat": "powiat iksowski"},
    ]

    table = place_names.table({"cities": rows}, {"rows": [{"slug": "x-y", "values": {}}]})

    assert table["cities"] == {"x-y": "X-Y"}


def test_a_slug_with_two_cities_of_powiat_rights_and_two_names_gets_none() -> None:
    """Never a guess: without one name the city is shown by its slug at run time."""
    rows = [
        {"slug": "x", "name": "Iks", "powiatId": 1, "powiat": "powiat Iks"},
        {"slug": "x", "name": "Iksy", "powiatId": 2, "powiat": "powiat Iksy"},
    ]

    table = place_names.table({"cities": rows}, {"rows": [{"slug": "x", "values": {}}]})

    assert table["cities"] == {}


def test_a_powiat_with_two_names_is_refused() -> None:
    rows = [
        {"slug": "a", "name": "A", "powiatId": 1, "powiat": "powiat A"},
        {"slug": "b", "name": "B", "powiatId": 1, "powiat": "powiat B"},
    ]

    with pytest.raises(ValueError, match="1"):
        place_names.table({"cities": rows}, {"rows": []})


def test_the_script_is_stdlib_only() -> None:
    """Like every script of recon/: it runs as python3 recon/place_names.py."""
    tree = ast.parse((RECON / "place_names.py").read_text(encoding="utf-8"))
    imported = {
        name.split(".")[0]
        for node in ast.walk(tree)
        for name in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else []
        )
    }

    assert imported and imported <= sys.stdlib_module_names
