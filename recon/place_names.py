#!/usr/bin/env python3
"""Write the package's table of place names from saved responses of the service.

    python3 recon/place_names.py <tx-cities.json> <gov-map-stats.json> \\
        src/deweloperuch_mcp/api/data/place_names.json

Offline and standard library only: it reads two saved bodies (``GET /api/map/tx-cities``
and ``GET /api/statystyki/gov-map-stats``, docs/discovery/endpoints.md, sections 3 and 4)
and sends nothing. The package never fetches ``tx-cities`` at run time (3.3 MB, D19): it
reads this table to name the powiats of ``statystyki/powiat-map-stats`` (which carries
ids only) and the cities of ``statystyki/gov-map-stats`` (which carries slugs only).

The table: ``powiats`` {id: name} for every ``powiatId`` of ``tx-cities`` (380, one name
each [P 2026-11-01]) and ``cities`` {slug: name} for the slugs of ``gov-map-stats`` (66).
Powiat names are as ``tx-cities`` gives them. A city is the place of its slug whose powiat
is the place itself (``powiat Rzeszów`` for ``Rzeszów``; a slug shared by several places,
``ambiguous``, keeps only that one), named as its powiat writes it: the place's own
``name`` keeps the register's lowercase after a hyphen (``Bielsko-biała``,
``Jastrzębie-zdrój``), the powiat and the service's pages do not (``Bielsko-Biała``)
[P 2026-11-02]. Slugs and names are compared without regard to case and Polish letters
(``Tarnobrzeg`` is a slug of ``tx-cities`` [P 2026-11-01]). A slug without one such name
is left out: the package then shows the slug.
"""

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_POLISH_LETTERS = str.maketrans("ąćęłńóśźż", "acelnoszz")


def fold(slug: str) -> str:
    """``" ŁÓDŹ "`` -> ``lodz``, as the package looks slugs up (``PlaceNames.fold``)."""
    return slug.strip().lower().translate(_POLISH_LETTERS)


def powiats(rows: Sequence[dict[str, Any]]) -> dict[str, str]:
    """Every powiat's name by its id, in the order of the ids; ``ValueError`` for an id
    with two names."""
    names: dict[int, str] = {}
    for row in rows:
        known = names.setdefault(row["powiatId"], row["powiat"])
        if known != row["powiat"]:
            raise ValueError(f"powiat {row['powiatId']}: {known!r} albo {row['powiat']!r}")
    return {str(powiat_id): names[powiat_id] for powiat_id in sorted(names)}


def city(rows: Sequence[dict[str, Any]], slug: str) -> str | None:
    """The name of the city with powiat rights ``slug`` names, as its powiat writes it:
    among the places of the slug, the one whose powiat is the place itself (compared
    without regard to case and Polish letters), named by its powiat without the prefix
    (``powiat Bielsko-Biała`` -> ``Bielsko-Biała``; the place's own ``name`` is the
    register's ``Bielsko-biała`` [P 2026-11-02]). ``None`` when no single name is left."""
    same = [row for row in rows if fold(row["slug"]) == fold(slug)]
    found = {own for row in same if fold(own := _own_powiat(row)) == fold(row["name"])}
    return found.pop() if len(found) == 1 else None


def _own_powiat(row: dict[str, Any]) -> str:
    """``powiat Bielsko-Biała`` -> ``Bielsko-Biała``."""
    return str(row["powiat"]).removeprefix("powiat ").strip()


def table(tx_cities: dict[str, Any], gov_map_stats: dict[str, Any]) -> dict[str, Any]:
    rows = tx_cities["cities"]
    cities = {fold(row["slug"]): city(rows, row["slug"]) for row in gov_map_stats["rows"]}
    return {
        "powiats": powiats(rows),
        "cities": {slug: name for slug, name in sorted(cities.items()) if name is not None},
    }


def main(argv: Sequence[str]) -> None:
    tx_cities, gov_map_stats, output = (Path(arg) for arg in argv)
    found = table(json.loads(tx_cities.read_bytes()), json.loads(gov_map_stats.read_bytes()))
    text = json.dumps(found, ensure_ascii=False, indent=1) + "\n"
    output.write_text(text, encoding="utf-8")
    print(f"{output}: {len(found['powiats'])} powiatów, {len(found['cities'])} miast")


if __name__ == "__main__":
    main(sys.argv[1:])
