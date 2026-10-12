# `deweloperuch investments get`
Shows an investment (a development project) with its developer, the average prices of active offers and a list of offers (active first). Equivalent to the MCP tool [`get_investment`](../../mcp/tools/get_investment.md).

## Usage
```
deweloperuch investments get [OPTIONS] SLUG
```

`--help` description: „Pokaż inwestycję z deweloperem i ofertami.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `SLUG` (argument, required) | text | — | The investment slug (investment_slug from `offers search`). Help text: „Slug inwestycji (investment_slug z `offers search`).” |
| `--history` | flag | off | Attach the price history of each offer (slower). Help text: „Dołącz historię ceny każdej oferty (wolniej).” |
| `--limit` | int | none (all offers) | The maximum number of offers shown (active first); all by default. In MCP `limit` defaults to 20 with a maximum of 200; the CLI without `--limit` shows all offers. Help text: „Najwięcej pokazanych ofert (najpierw aktywne); domyślnie wszystkie.” |
| `--json` | flag | off | Print the result as JSON (the domain model; with the links `investment_url` and `developer_url`, the `offers` entries without links). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (bad slug or `--limit`), 3 STOP, 7 no such investment.

## Examples
```
deweloperuch investments get smolna
deweloperuch investments get smolna --limit 2
deweloperuch investments get smolna --history --json
```

Text output with `--limit 2` (test mock, sample `api.map_inv_visible`):

```
Smolna [smolna] · aktywna
Strona inwestycji: https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna
Miejsce: Sopot [sopot], Świemirowo · 54.42736, 18.55839
Deweloper: Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]
Profil dewelopera: https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna
Średnio (aktywne oferty): 1 566 392 PLN · 63,97 m² · 24 487,63 PLN/m²
Oferty: aktywne 3 z 16 · pokazano 2 · pominięto 1 (zwiększ --limit).
[206087] C234 · 1 679 796 PLN · 65,9 m² · 25 490,08 PLN/m² · aktywna
[2377] C224 · 1 620 175 PLN · 69,5 m² · 23 311,87 PLN/m² · aktywna · od pierwszej ceny +175 PLN (+0,01%)
```

The lines „Strona inwestycji” (investment page) and „Profil dewelopera” (developer profile) (D12) are omitted when the slug is missing.

_Source: `src/deweloperuch_mcp/interfaces/cli/`, `uv run deweloperuch investments get --help`_
