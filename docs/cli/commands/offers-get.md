# `deweloperuch offers get`
Shows one offer with its full price history, investment and developer. Equivalent to the MCP tool [`get_offer`](../../mcp/tools/get_offer.md).

## Usage
```
deweloperuch offers get [OPTIONS] OFFER_ID --investment SLUG
```

`--help` description: „Pokaż ofertę z historią ceny.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `OFFER_ID` (argument, required) | int | — | The offer identifier from `offers search`. Help text: „Identyfikator oferty z `offers search`.” |
| `--investment` | SLUG | — (required) | The slug of the offer's investment. Help text: „Slug inwestycji oferty (investment_slug z `offers search`).” |
| `--json` | flag | off | Print the result as JSON (the domain model; with the links `investment_url` and `developer_url`). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (missing `--investment`, bad `OFFER_ID`), 3 STOP, 7 no such investment, or no such offer in this investment.

## Examples
```
deweloperuch offers get 2377 --investment smolna
deweloperuch offers get 2377 --investment smolna --json
```

Text output (test mock, samples `api.map_inv_visible`, `api.sale_events`):

```
[2377] C224 · aktywna
Cena: 1 620 175 PLN · 69,5 m² · 23 311,87 PLN/m²
Od pierwszej ceny: +175 PLN (+0,01%)
Inwestycja: Smolna [smolna] · Sopot
Strona inwestycji: https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna
Deweloper: Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]
Profil dewelopera: https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna
Daty: dodana 2025-02-25 · ostatnie zdarzenie 2026-10-03 · ostatnia zmiana 2026-10-03
Historia ceny (3):
  2025-02-25  cena          1 620 000 PLN
  2025-02-25  wycofanie     1 620 000 PLN
  2026-10-03  przywrócenie  1 620 175 PLN
```

The lines „Strona inwestycji” (investment page) and „Profil dewelopera” (developer profile) (D12) lead to the investment and developer pages, not to a single offer; a missing slug means no line.

With `--json` the result has all fields of the domain model, also `null` ones (e.g. `developer.website`).

_Source: `src/deweloperuch_mcp/cli.py`, `uv run deweloperuch offers get --help`_
