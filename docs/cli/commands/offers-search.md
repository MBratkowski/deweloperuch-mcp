# `deweloperuch offers search`
Searches developers' apartment offers (asking prices, primary market) in a city or the whole of Poland (`polska`), with price, area, price-per-m², district, status and price-drop filters and sorting; at most 20 pages of results. Equivalent to the MCP tool [`search_offers`](../../mcp/tools/search_offers.md).

## Usage
```
deweloperuch offers search [OPTIONS] CITY
```

`--help` description: „Szukaj ofert mieszkań w mieście; najwyżej 20 stron wyników.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `CITY` (argument, required) | text | — | A city slug (e.g. warszawa; given by `locations search`) or polska. Help text: „Slug miasta (np. warszawa; podaje go `locations search`) albo polska.” |
| `--price-min` | int | none | The lowest price in PLN. Help text: „Najniższa cena w PLN.” |
| `--price-max` | int | none | The highest price in PLN. Help text: „Najwyższa cena w PLN.” |
| `--area-min` | int | none | The smallest area in m². Help text: „Najmniejszy metraż w m².” |
| `--area-max` | int | none | The largest area in m². Help text: „Największy metraż w m².” |
| `--price-per-m2-min` | int | none | The lowest price per m² in PLN (0–999 999). Help text: „Najniższa cena za m² w PLN.” |
| `--price-per-m2-max` | int | none | The highest price per m² in PLN. Help text: „Najwyższa cena za m² w PLN.” |
| `--district` | text | none | A district of the city as in `locations search` (kind `dzielnica`), e.g. Mokotów; not with `polska`. Help text: „Dzielnica miasta jak w `locations search` (np. Mokotów); nie z polska.” |
| `--price-dropped` | flag | off | Only offers cheaper than their first price. Help text: „Tylko oferty tańsze niż ich pierwsza cena.” |
| `--status` | `active` \| `archived` \| `all` | `active` | `active`, `archived` (withdrawn) or `all` (both). Help text: „active (domyślnie), archived (wycofane) albo all (obie).” |
| `--sort` | `price_asc` \| `price_desc` \| `price_per_m2_asc` \| `price_per_m2_desc` \| `area_asc` \| `area_desc` \| `biggest_drop` | none (the service's order) | The order: by price, price per m², area, or the biggest drop from the first price first; without the option the service's default order. Sorting by price is confirmed. Help text: „Kolejność: po cenie, cenie za m², metrażu albo najpierw największa obniżka od pierwszej ceny; bez opcji domyślna kolejność serwisu.” |
| `--page` | int | `1` | The page number, 1-20. Help text: „Numer strony, 1–20.” |
| `--per-page` | `10` \| `50` \| `100` | `10` | The number of offers per page. Help text: „Liczba ofert na stronie.” |
| `--json` | flag | off | Print the result as JSON (the domain model; with links: `list_url` in the result and `investment_url` in every item). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

Links to service pages: in text mode the line „Ta lista na deweloperuch.pl: …” (this list on deweloperuch.pl) under the header (the same filters, sorting and page) and the investment page address under each offer (not a single offer). A missing slug means no line.

The filter ranges are 0-99 999 999 PLN and 0-9 999 m² (range limits taken from the service client, not market data); `--price-per-m2-*` is 0-999 999 PLN. A reversed range (`--price-min` greater than `--price-max`, likewise for area and price per m²) is an error (code 2), as is `--district` blank or with `polska`.

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (a bad or reversed filter, `--district` with `polska`, `--sort`, `--status` or `--per-page` outside the list), 3 STOP, 4 service error, 7 unknown city (a `Błąd:` line „Serwis nie zna miasta '<slug>'…” and `Szczegóły:` with a response digest). A `CITY` that is not a slug (a name, capital letters, an empty string) is a validation error with the message „city: oczekiwano slug miasta…”, before any request is sent.

## Examples
```
deweloperuch offers search warszawa
deweloperuch offers search warszawa --price-max 1000000 --sort price_asc
deweloperuch offers search krakow --area-min 40 --area-max 60 --per-page 50 --page 2
deweloperuch offers search warszawa --district Mokotów --price-dropped --sort biggest_drop
deweloperuch offers search polska --json
```

Output of the first call (default `--per-page 10`) from `tests/golden/cli/offers_search.json` (a mocked service): the items are copies of offers from the `page.offers_list` sample, and `total` comes from the sample. The first 2 of 10 items are shown, the remaining 8 omitted:

```
Pasujące oferty: 13 324 · strona 1 z 20 (po 10) · pokazano 10 · obcięte: serwis pozwala przejrzeć najwyżej 20 stron.
Wskazówka: Pasujących ofert jest 13324, a serwis pozwala przejrzeć najwyżej 20 stron po 10 (200). Zawęź filtry (cena, metraż) albo zwiększ per_page do 100.
Ta lista na deweloperuch.pl: https://deweloperuch.pl/ceny-ofertowe/warszawa/mieszkania?perPage=10
[4397] D1.1.1.4 · 994 012 PLN · 55,25 m² · 17 991,17 PLN/m² · aktywna · od pierwszej ceny -5 988 PLN (-0,6%)
    Nowy Targówek VI [nowy-targowek-vi] · ATAL S.A. · Warszawa
    https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi
[4406] D1.2.0.1 · 659 315 PLN · 36,49 m² · 18 068,37 PLN/m² · aktywna · od pierwszej ceny -30 685 PLN (-4,45%)
    Nowy Targówek VI [nowy-targowek-vi] · ATAL S.A. · Warszawa
    https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi
(… 8 pozostałych ofert pominięto …)
Szczegóły oferty: deweloperuch offers get OFFER_ID --investment INVESTMENT_SLUG
```

_Source: `src/deweloperuch_mcp/consumers/cli/commands/offers_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/search_offers_cli_presenter.py`, `uv run deweloperuch offers search --help`_
