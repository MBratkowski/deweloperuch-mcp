# `deweloperuch stats market`
Shows statistics of the active developer offers of one city: counts, distributions of price, price per m² and area, and the largest developers. Equivalent to the MCP tool [`get_market_statistics`](../../mcp/tools/get_market_statistics.md).

## Usage
```
deweloperuch stats market [OPTIONS] CITY
```

`--help` description: „Pokaż statystyki aktywnych ofert miasta: ceny, metraże, największych deweloperów.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `CITY` (argument, required) | text | — | The slug of one city (e.g. krakow; given by `locations search`), not `polska`. Help text: „Slug jednego miasta (np. krakow; podaje go `locations search`), nie polska.” |
| `--price-min` | int | none | The lowest price in PLN. Help text: „Najniższa cena w PLN.” |
| `--price-max` | int | none | The highest price in PLN. Help text: „Najwyższa cena w PLN.” |
| `--area-min` | int | none | The smallest area in m². Help text: „Najmniejszy metraż w m².” |
| `--area-max` | int | none | The largest area in m². Help text: „Największy metraż w m².” |
| `--top` | int | `10` | How many of the largest developers to show (1–30). Help text: „Ilu największych deweloperów pokazać (1–30).” |
| `--json` | flag | off | Print the result as JSON (the domain model). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0 (also when no offer matches the filters), 2 (`CITY=polska` or not a slug, a reversed range, `--top` outside 1–30), 3 STOP, 4 service error, 7 unknown city (`Błąd: Serwis nie zna miasta 'nieznane'. …`).

## Examples
```
deweloperuch stats market sopot
deweloperuch stats market krakow --price-min 400000 --price-max 700000 --area-max 60 --top 5
deweloperuch stats market sopot --json
```

Output of the first call (`tests/golden/cli/stats_market.json`):

```
Rynek ofert [sopot] · aktywne oferty: 6 · inwestycje: 2 · deweloperzy: 1.
Te oferty na deweloperuch.pl: https://deweloperuch.pl/ceny-ofertowe/sopot/mieszkania?perPage=10
                        min        p25    mediana        p75        max
Cena (PLN)        1 399 205  1 588 164  1 616 463  1 646 230  1 679 796
Cena za m² (PLN)     22 931     23 559     24 533     25 309     27 037
Metraż (m²)            56,5      61,21         67       68,7       69,5
Najwięcej ofert (pokazano 1 z 1):
  invest-komfort-spolka-akcyjna · oferty 6 · inwestycje 2 · mediana 24 533 PLN/m²
      https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna
```

Developers are listed by slug; `developers get SLUG` gives the name.

_Source: `src/deweloperuch_mcp/consumers/cli/commands/stats_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/get_market_statistics_cli_presenter.py`, `uv run deweloperuch stats market --help`_
