# `deweloperuch stats market`
Shows statistics of the active developer offers of one city: counts, distributions of price, price per m² and area, and the largest developers, as of the day the service gives its offers for. Equivalent to the MCP tool [`get_market_statistics`](../../mcp/tools/get_market_statistics.md).

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
| `--json` | flag | off | Print the result as JSON (the domain model; it has `as_of` and `developer_name` of each developer). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0 (also when no offer matches the filters), 2 (`CITY=polska` or not a slug, a reversed range, `--top` outside 1–30; a `CITY` that is not a slug gets `Błąd: city: oczekiwano slug jednego miasta z search_locations: małe litery, bez polskich znaków (np. warszawa, sopot; nie polska); podano 'Kraków'.`), 3 STOP, 4 service error, 6 the service moved or removed the route or sent data off the contract (`Błąd: Statystyki rynku w 'sopot': Narzędzie nie może pobrać tych danych, …`), 7 unknown city (`Błąd: Serwis nie zna miasta 'nieistniejace-miasto' albo nie ma w nim ofert. Podaj city_slug z search_locations (miejscowości z offer_count=0 nie mają statystyk; statystyki rynku są tylko dla jednego miasta).`, with a `Szczegóły:` line: the target, the status and the media type).

## Examples
```
deweloperuch stats market sopot
deweloperuch stats market warszawa --price-max 700000 --area-min 40 --top 3
deweloperuch stats market sopot --json
```

Output of the first call (`tests/golden/cli/stats_market.json`, a mocked service replaying the real list of Sopot captured on 2026-10-31). The head line ends with the day of the data (`stan na RRRR-MM-DD`), and each developer is shown as its name and its slug:

```
Rynek ofert [sopot] · aktywne oferty: 8 · inwestycje: 2 · deweloperzy: 1 · stan na 2026-10-31.
Te oferty na deweloperuch.pl: https://deweloperuch.pl/ceny-ofertowe/sopot/mieszkania?perPage=10
                        min        p25    mediana        p75        max
Cena (PLN)        1 261 250  1 534 860  1 616 858  1 661 530  3 735 107
Cena za m² (PLN)     24 289     25 224     25 808     26 383     39 115
Metraż (m²)           48,73      58,11      64,69      66,02      95,49
Najwięcej ofert (pokazano 1 z 1):
  Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna] · oferty 8 · inwestycje 2 · mediana 25 808 PLN/m²
      https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna
```

`developers get SLUG` shows the developer's investments and cities (the slug is the `developer_slug` of `developers get`).

_Source: `src/deweloperuch_mcp/consumers/cli/commands/stats_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/get_market_statistics_cli_presenter.py`, `uv run deweloperuch stats market --help`_
