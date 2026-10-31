# `deweloperuch developers get`
Shows a developer profile: a summary of active offers, investments with active offers and the developer's cities. Equivalent to the MCP tool [`get_developer`](../../mcp/tools/get_developer.md).

## Usage
```
deweloperuch developers get [OPTIONS] SLUG
```

`--help` description: „Pokaż dewelopera z jego inwestycjami i miastami.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `SLUG` (argument, required) | text | — | The developer slug (from `developers search` or `developer_slug` of `offers search`). Help text: „Slug dewelopera (z `developers search` albo pole developer_slug z `offers search`).” |
| `--city` | text | `polska` | A city slug (e.g. krakow) or `polska` (the whole country); narrows the summary and the investments. Help text: „Slug miasta (np. krakow) albo polska, czyli cała Polska.” |
| `--limit` | int | `20` | The maximum number of investments shown (most active offers first), 1–1000. In MCP `limit` is 1–100. Help text: „Najwięcej pokazanych inwestycji (najpierw z największą liczbą ofert).” |
| `--json` | flag | off | Print the result as JSON (the domain model). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

The `summary` is computed from the investments in the scope (the service's page has no totals), and the output has no developer website or description: `developer` in `--json` has only `developer_slug` and `name`, and a row of `cities` has no `avg_price`. Details: [`get_developer`](../../mcp/tools/get_developer.md#data-limitations).

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (a capitalised or non-slug `SLUG` or `--city`, `--limit` outside 1–1000), 3 STOP, 4 service error, 6 the page has no expected data or the service moved the page, 7 unknown developer (`Błąd: Nie znaleziono dewelopera '…' w '…'. …`, for a city with the end „Albo deweloper nie ma w tym mieście aktywnych ofert: spróbuj city=polska.”).

**Known limitation (not fixed in 0.2.0):** a developer the service knows, asked for with a `--city` the service does not know, can end with exit code 6 and the "service changed" message instead of exit code 7. `--city polska` shows whether the developer exists. A repair is planned (T39).

## Examples
```
deweloperuch developers get atal
deweloperuch developers get atal --city warszawa
deweloperuch developers get atal --limit 5 --json
```

Output of the second call (`tests/golden/cli/developers_get.json`, a mocked service replaying the real page captured on 2026-10-31, shortened):

```
ATAL S.A. [atal] · [warszawa]
Profil dewelopera: https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal
Aktywne oferty: 60 · inwestycje: 4 · miasta: 1 · średnio: 993 384 PLN · 62,3 m² · 16 110 PLN/m²
Inwestycje: pokazano 4 z 4.
[warszawska-58a] Warszawska 58A · Warszawa · aktywna · aktywne oferty 32 z 73 · 966 209 PLN · 59,93 m² · 16 123 PLN/m²
    https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/warszawska-58a
[nowy-targowek-vi] Nowy Targówek VI · Warszawa · aktywna · aktywne oferty 21 z 75 · 1 073 611 PLN · 60,84 m² · 17 646 PLN/m²
    https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi
(… two more investments, then:)
Miasta dewelopera (cała Polska):
  Kraków [krakow] · inwestycje 7 · aktywne oferty 705 · 13 757 PLN/m²
  Poznań [poznan] · inwestycje 4 · aktywne oferty 704 · 11 864 PLN/m²
  (… the other cities)
```

The cities are ordered by active offers, then by price per m², both highest first.

A developer in one city whose page has no chart of cities (`developers get ceres-development --city warszawa`, `tests/golden/cli/developers_get_single_city.json`): the cities come from its investments, and the output says so in a hint and in the header of the list:

```
Ceres Development Sp. z o.o. [ceres-development] · [warszawa]
Profil dewelopera: https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/ceres-development
Aktywne oferty: 110 · inwestycje: 1 · miasta: 1 · średnio: 662 273 PLN · 50,96 m² · 12 996 PLN/m²
Inwestycje: pokazano 1 z 1.
Wskazówka: Serwis nie podał listy miast dewelopera: cities to tylko miasta inwestycji w city (wszystkie: city=polska).
[osiedle-sprawna-warszawa] Osiedle Sprawna · Warszawa · aktywna · aktywne oferty 110 z 114 · 662 273 PLN · 50,96 m² · 12 996 PLN/m²
    https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/ceres-development/osiedle-sprawna-warszawa
Miasta dewelopera (tylko z inwestycji w [warszawa]):
  Warszawa [warszawa] · inwestycje 1 · aktywne oferty 110 · 12 996 PLN/m²
```

_Source: `src/deweloperuch_mcp/consumers/cli/commands/developers_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/get_developer_cli_presenter.py`, `uv run deweloperuch developers get --help`_
