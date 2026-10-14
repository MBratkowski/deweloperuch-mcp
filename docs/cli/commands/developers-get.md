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

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (a capitalised or non-slug `SLUG` or `--city`, `--limit` outside 1–1000), 3 STOP, 4 service error, 6 the page has no expected data, 7 unknown developer (`Błąd: Nie znaleziono dewelopera '…' w '…'. …`).

## Examples
```
deweloperuch developers get atal
deweloperuch developers get atal --city warszawa
deweloperuch developers get atal --limit 5 --json
```

Output of the second call (`tests/golden/cli/developers_get.json`, shortened):

```
ATAL S.A. [atal] · [warszawa]
Profil dewelopera: https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal
Aktywne oferty: 69 · inwestycje: 4 · miasta: 1 · średnio: 1 001 962 PLN · 62,7 m² · 16 111 PLN/m²
Inwestycje: pokazano 4 z 4.
[warszawska-58a] Warszawska 58A · Warszawa · aktywna · aktywne oferty 36 z 73 · 958 593 PLN · 59,67 m² · 16 064 PLN/m²
    https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/warszawska-58a
[nowy-targowek-vi] Nowy Targówek VI · Warszawa · aktywna · aktywne oferty 24 z 75 · 1 098 683 PLN · 62,31 m² · 17 631 PLN/m²
    https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi
(… two more investments, then:)
Miasta dewelopera (cała Polska):
  Poznań [poznan] · inwestycje 4 · aktywne oferty 736 · 709 389 PLN · 11 823 PLN/m²
  (… the other cities)
```

_Source: `src/deweloperuch_mcp/consumers/cli/commands/developers_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/get_developer_cli_presenter.py`, `uv run deweloperuch developers get --help`_
