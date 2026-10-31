# `deweloperuch offers search`
Searches developers' apartment offers (asking prices, primary market) in one city or one of its districts, with price, area, price-per-m², district, status and price-drop filters and sorting; at most 20 pages of results. `polska` is refused: the service has no list of offers of the whole country. Equivalent to the MCP tool [`search_offers`](../../mcp/tools/search_offers.md).

## Usage
```
deweloperuch offers search [OPTIONS] CITY
```

`--help` description: „Szukaj ofert mieszkań w mieście albo w jego dzielnicy; najwyżej 20 stron wyników.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `CITY` (argument, required) | text | — | The slug of one city (e.g. warszawa; given by `locations search`), not `polska`. Help text: „Slug jednego miasta (np. warszawa; podaje go `locations search`), nie polska.” |
| `--price-min` | int | none | The lowest price in PLN. Help text: „Najniższa cena w PLN.” |
| `--price-max` | int | none | The highest price in PLN. Help text: „Najwyższa cena w PLN.” |
| `--area-min` | int | none | The smallest area in m². Help text: „Najmniejszy metraż w m².” |
| `--area-max` | int | none | The largest area in m². Help text: „Największy metraż w m².” |
| `--price-per-m2-min` | int | none | The lowest price per m² in PLN (0–999 999). Help text: „Najniższa cena za m² w PLN.” |
| `--price-per-m2-max` | int | none | The highest price per m² in PLN. Help text: „Najwyższa cena za m² w PLN.” |
| `--district` | text | none | A district of the city, by its name as in `locations search` (kind `dzielnica`), e.g. Mokotów, Praga-Południe; the tool reads that district's own list. Help text: „Dzielnica miasta: jej nazwa jak w `locations search` (np. Praga-Południe).” |
| `--price-dropped` | flag | off | Only offers cheaper than their first price. Help text: „Tylko oferty tańsze niż ich pierwsza cena.” |
| `--status` | `active` \| `archived` \| `all` | `active` | `active`, `archived` (withdrawn) or `all` (both; the `total` of `all` can exceed the two together, the service counts them unclearly). Help text: „active (domyślnie), archived (wycofane) albo all (obie).” |
| `--sort` | `price_asc` \| `price_desc` \| `price_per_m2_asc` \| `price_per_m2_desc` \| `area_asc` \| `area_desc` \| `biggest_drop` | none (the service's order) | The order: by price, price per m², area, or the biggest drop from the first price first; without the option the service's default order, which is not a ranking (usually the oldest offers, grouped by investment), so give `--sort` to browse a city. Help text: „Kolejność: po cenie, cenie za m², metrażu albo najpierw największa obniżka od pierwszej ceny; bez opcji domyślna kolejność serwisu.” |
| `--page` | int | `1` | The page number, 1-20. Help text: „Numer strony, 1–20.” |
| `--per-page` | `10` \| `50` \| `100` | `10` | The number of offers per page. Help text: „Liczba ofert na stronie.” |
| `--json` | flag | off | Print the result as JSON (the domain model; with links: `list_url` in the result and `investment_url` in every item). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

Links to service pages: in text mode the line „Ta lista na deweloperuch.pl: …” (this list on deweloperuch.pl: the city's or the district's, with the same filters, sorting and page, and never `page=1`) under the header and the investment page address under each offer (not a single offer). A missing slug means no line.

In text mode an offer's second line names the investment, its slug, the developer and the city; the district is only in `--json` (`items[].district`, next to `city` and `city_slug`).

The filter ranges are 0-99 999 999 PLN and 0-9 999 m² (range limits taken from the service client, not market data); `--price-per-m2-*` is 0-999 999 PLN. A reversed range (`--price-min` greater than `--price-max`, likewise for area and price per m²) is an error (code 2), as is `CITY=polska` (with or without `--district`), `--district` blank or outside 2-100 characters.

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common:

| Code | Meaning |
|---|---|
| 0 | A page of offers (also an empty one). |
| 2 | A bad or reversed filter; `CITY=polska` (`Błąd: city=polska nie działa przy wyszukiwaniu ofert: serwis nie ma jednej listy ofert całej Polski. Podaj city_slug jednego miasta z search_locations (np. warszawa); oferty kilku miast wyszukaj osobno dla każdego.`, no request is sent); `--sort`, `--status` or `--per-page` outside the list; a `CITY` that is not a slug (a name, capital letters, an empty string: `Błąd: city: oczekiwano city_slug jednego miasta (małe litery bez polskich znaków, np. warszawa, krakow), nie polska; slug podaje search_locations; podano 'Kraków'.`). |
| 3 | STOP. |
| 4 | Service error (5xx, network). |
| 6 | The page does not match the contract, or the service moved or removed the list (a redirect, a removed route, a 410): `Błąd: Wyszukiwanie ofert w 'warszawa': Na stronie serwisu brakuje oczekiwanych danych. Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.` |
| 7 | Unknown city: `Błąd: Serwis nie zna miasta 'nieistniejace-miasto'. Podaj city_slug miasta z search_locations.` Unknown district: `Błąd: Serwis nie zna dzielnicy 'Nieistniejąca Dzielnica' w mieście 'warszawa'. Podaj nazwę dzielnicy tak, jak zwraca ją search_locations (kind=district, pole name), razem z city_slug jej miasta.` A `--page` above 1 that is not found: `Serwis nie ma strony 2 tej listy albo nie zna miasta 'sopot': lista może mieć mniej stron (pages_available podaje page=1); jeśli page=1 też zawiedzie, podaj city_slug miasta z search_locations.` (on the redesigned service a page past the last one is answered like an unknown city). Each is followed by a `Szczegóły:` line with the target and what the page lacked. |

The error texts are shared with the MCP tool, so they name `search_locations`; in the CLI that is `locations search`.

## Examples
```
deweloperuch offers search warszawa
deweloperuch offers search warszawa --price-max 1000000 --sort price_asc
deweloperuch offers search krakow --area-min 40 --area-max 60 --per-page 50 --page 2
deweloperuch offers search warszawa --district Mokotów --price-dropped --sort biggest_drop
deweloperuch offers search warszawa --district Praga-Południe --json
```

Output of the first call (default `--per-page 10`) from `tests/golden/cli/offers_search.json` (a mocked service replaying the real list of Warszawa captured on 2026-10-31): `total` comes from that capture. The first 2 of 10 items are shown, the remaining 8 omitted:

```
Pasujące oferty: 11 672 · strona 1 z 20 (po 10) · pokazano 10 · obcięte: serwis pozwala przejrzeć najwyżej 20 stron.
Wskazówka: Pasujących ofert jest 11672, a serwis pozwala przejrzeć najwyżej 20 stron po 10 (200). Zawęź filtry (dzielnica, cena, metraż) albo zwiększ per_page do 100.
Ta lista na deweloperuch.pl: https://deweloperuch.pl/ceny-ofertowe/warszawa/mieszkania?perPage=10
[4487] A2 · 810 660 PLN · 35,4 m² · 22 900 PLN/m² · aktywna · od pierwszej ceny +660 PLN (+0,08%)
    Apartamenty Beethovena [apartamenty-beethovena] · Dom Development S.A. · Warszawa
    https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/dom-development/apartamenty-beethovena
[4527] B36 · 1 324 896 PLN · 59,68 m² · 22 200 PLN/m² · aktywna · od pierwszej ceny +14 896 PLN (+1,14%)
    Apartamenty Beethovena [apartamenty-beethovena] · Dom Development S.A. · Warszawa
    https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/dom-development/apartamenty-beethovena
(… 8 pozostałych ofert pominięto …)
Szczegóły oferty: deweloperuch offers get OFFER_ID --investment INVESTMENT_SLUG
```

With `--district Mokotów` (`tests/golden/cli/offers_search_district.json`) the command sends one request, for the district's list, and the head changes (the hint no longer suggests the district; the items are the same in the mocked service):

```
Pasujące oferty: 959 · strona 1 z 20 (po 10) · pokazano 10 · obcięte: serwis pozwala przejrzeć najwyżej 20 stron.
Wskazówka: Pasujących ofert jest 959, a serwis pozwala przejrzeć najwyżej 20 stron po 10 (200). Zawęź filtry (cena, metraż) albo zwiększ per_page do 100.
Ta lista na deweloperuch.pl: https://deweloperuch.pl/ceny-ofertowe/warszawa/mokotow/mieszkania?perPage=10
```

_Source: `src/deweloperuch_mcp/consumers/cli/commands/offers_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/search_offers_cli_presenter.py`, `src/deweloperuch_mcp/usecases/search_offers.py`, `uv run deweloperuch offers search --help`_
