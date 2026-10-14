# `deweloperuch buildings get`
Shows a building from the transaction price register (RCN) with its units and their transactions: prices for which units were sold, not asking prices. Equivalent to the MCP tool [`get_building`](../../mcp/tools/get_building.md).

## Usage
```
deweloperuch buildings get [OPTIONS] SLUG
```

`--help` description: „Pokaż budynek z lokalami i ich transakcjami (ceny transakcyjne, nie ofertowe). Lokale od tego z najnowszą transakcją, transakcje każdego lokalu od najstarszej.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `SLUG` (argument, required) | text | — | The building slug, e.g. 23-marca-79c-sopot: the last segment of the address of the building's transaction page on deweloperuch.pl. Help text: „Slug budynku, np. 23-marca-79c-sopot: ostatni człon adresu strony budynku z cenami transakcyjnymi na deweloperuch.pl.” |
| `--limit` | int | all units | The maximum number of units shown (those with the newest transactions), 0–100000; `0` shows only the summary. In MCP `limit` defaults to 10 with a maximum of 50. Help text: „Najwięcej pokazanych lokali (tych z najnowszymi transakcjami); domyślnie wszystkie.” |
| `--trend` | flag | off | Add the average price per m² of transactions around the building, quarter by quarter (one more request). Help text: „Dołącz średnią cenę za m² transakcji w okolicy budynku, kwartał po kwartale (jedno zapytanie więcej).” |
| `--json` | flag | off | Print the result as JSON (the domain model). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (a non-slug `SLUG`, `--limit` outside 0–100000), 3 STOP, 4 service error (also a failed `--trend` request), 6 unexpected response, 7 no such building.

## Examples
```
deweloperuch buildings get 23-marca-79c-sopot
deweloperuch buildings get 23-marca-79c-sopot --limit 1 --trend
deweloperuch buildings get 23-marca-79c-sopot --json
```

Output of the first call (`tests/golden/cli/buildings_get.json`; the register identifier of each unit is printed at the end of the unit line):

```
23 Marca 79C [23-marca-79c-sopot]
Strona budynku: https://deweloperuch.pl/ceny-transakcyjne/sopot/adresy/23-marca-79c-sopot
Miejsce: Sopot [sopot] · 54.44706, 18.54342
Średnio (wg serwisu): 1 324 115 PLN · 61,6 m² · 21 494,72 PLN/m²
Lokale: 3 · transakcje: 3 (od 2025-09-12 do 2025-11-17) · pokazano 3.
piętro 1 · 5 pok. · 122,01 m² · 226401_4.4191.4568_BUD.3_LOK
  2025-11-17  1 900 000,47 PLN · 15 572,5 PLN/m² · rynek pierwotny · zwykła · kupujący: osoba fizyczna · sprzedający: osoba prawna
(… two more units)
```

With `--trend` the output ends with `Trend w okolicy (promień 1 km): średnia cena za m² i liczba transakcji.` and lines such as `  2006-Q2  5 706 PLN/m² · transakcji: 25`.

_Source: `src/deweloperuch_mcp/consumers/cli/commands/buildings_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/get_building_cli_presenter.py`, `uv run deweloperuch buildings get --help`_
