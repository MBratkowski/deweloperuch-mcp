# `deweloperuch investments search`
Searches development projects (investments) of a city, or by name across Poland. Equivalent to the MCP tool [`search_investments`](../../mcp/tools/search_investments.md).

## Usage
```
deweloperuch investments search [OPTIONS] [CITY]
```

`--help` description: „Szukaj inwestycji w mieście albo po nazwie (w całej Polsce).”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `CITY` (argument, optional) | text | — | A city slug (e.g. sopot; given by `locations search`). Without `CITY` give `--name`. Help text: „Slug miasta (np. sopot; podaje go `locations search`). Bez CITY podaj --name.” |
| `--name` | text | none | A fragment of the investment name (2–100 characters); without `CITY` it searches the whole of Poland. Help text: „Fragment nazwy inwestycji (2–100 znaków); bez CITY w całej Polsce.” |
| `--developer` | SLUG | none | A developer slug (from `developers search`); only with `CITY`. Help text: „Slug dewelopera; tylko z CITY.” |
| `--sort` | `active_offers` \| `price_per_m2_asc` \| `price_per_m2_desc` \| `price_asc` \| `price_desc` \| `name` | `active_offers` | The order; only with `CITY`. Help text: „Kolejność; tylko z CITY. Domyślnie najwięcej aktywnych ofert.” |
| `--limit` | int | `10` | The maximum number of investments shown, 1–500 (by name alone up to 50). In MCP `limit` is 1–30. Help text: „Najwięcej pokazanych inwestycji, 1–500 (po samej nazwie do 50).” |
| `--json` | flag | off | Print the result as JSON (the domain model). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (neither `CITY` nor `--name`, `CITY=polska`, `--developer` or `--sort` without `CITY`, a capitalised or non-slug `CITY`, `--limit` outside the range, `--sort` outside the list), 3 STOP, 4 service error, 6 unexpected response, 7 unknown city (`Błąd: Serwis nie zna miasta 'sopot'. Podaj city_slug z search_locations.`).

## Examples
```
deweloperuch investments search sopot
deweloperuch investments search sopot --developer invest-komfort-spolka-akcyjna --sort price_per_m2_desc --limit 5
deweloperuch investments search --name kolibki
```

Output of the first call (`tests/golden/cli/investments_search.json`):

```
Inwestycje: 2 · pokazano 2.
Nowe Kolibki etap 4 [nowe-kolibki-etap-4] · aktywna · Sopot
    oferty: aktywne 3 z 27 · średnio 1 615 878 PLN · 65,55 m² · 24 756,49 PLN/m²
    Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]
    https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna/nowe-kolibki-etap-4
Smolna [smolna] · aktywna · Sopot, Świemirowo
    oferty: aktywne 3 z 16 · średnio 1 566 392 PLN · 63,97 m² · 24 522,21 PLN/m²
    Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]
    https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna
Oferty inwestycji: deweloperuch investments get INVESTMENT_SLUG
```

By name alone (`--name "nowy targ"`) each investment shows only the slug, the name and `oferty: aktywne N`.

_Source: `src/deweloperuch_mcp/consumers/cli/commands/investment_search_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/search_investments_cli_presenter.py`, `uv run deweloperuch investments search --help`_
