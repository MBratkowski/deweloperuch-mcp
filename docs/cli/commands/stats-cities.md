# `deweloperuch stats cities`
Shows a ranking of places or powiats by RCN transactions: the number of transactions and the transaction price per m². Equivalent to the MCP tool [`rank_locations`](../../mcp/tools/rank_locations.md).

## Usage
```
deweloperuch stats cities [OPTIONS]
```

`--help` description: „Pokaż ranking miejscowości albo powiatów według transakcji RCN.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `--level` | `city` \| `powiat` | `city` | `city`: places (small towns too); `powiat`: powiats. Help text: „city: miejscowości (także małe); powiat: powiaty.” |
| `--sort` | `transactions_desc` \| `price_per_m2_desc` \| `price_per_m2_asc` | `transactions_desc` | The most transactions, or by price per m² (descending, ascending). Help text: „Najwięcej transakcji albo po cenie za m² (malejąco, rosnąco).” |
| `--limit` | int | `20` | How many first positions to show, 1–100. Help text: „Ile pierwszych pozycji pokazać, 1–100.” |
| `--min-transactions` | int | not given | Skip places with fewer transactions. Not given: 20 when sorting by price (both levels), 0 for `transactions_desc`; an explicit value, including 0 (all places), wins. **Behaviour change (BREAKING):** price sorts used to include every place by default. Help text: „Pomiń miejsca z mniejszą liczbą transakcji; domyślnie 20 przy sortowaniu po cenie, 0 po liczbie transakcji (0: wszystkie miejsca).” |
| `--json` | flag | off | Print the result as JSON (the domain model). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (`--level` or `--sort` outside the list, `--limit` outside 1–100, `--min-transactions` outside 0–10 000 000), 3 STOP, 4 service error.

## Examples
```
deweloperuch stats cities
deweloperuch stats cities --sort price_per_m2_desc --min-transactions 50 --limit 10
deweloperuch stats cities --level powiat --sort price_per_m2_asc --json
```

Output of the first call (`tests/golden/cli/stats_cities.json`, a three-place mocked list):

```
Ranking miejscowości wg liczby transakcji: pokazano 3 z 3.
Ranking miast na deweloperuch.pl: https://deweloperuch.pl/ceny-transakcyjne/polska/miasta
1. Warszawa [warszawa] · transakcji: 3 606 · 16 413 PLN/m² · 48,8 m² · 780 000 PLN
2. Kraków [krakow] · transakcji: 1 492 · 14 606 PLN/m² · 47,4 m² · 675 000 PLN
3. Wrocław [wroclaw] · transakcji: 1 443 · 12 437 PLN/m² · 50,3 m² · 617 000 PLN
Serwis nie podaje okresu ani tego, czy ceny i metraż to średnie, czy mediany.
```

Sorting by price without `--min-transactions` (`tests/golden/cli/stats_cities_price_asc_default_threshold.json`, `stats cities --sort price_per_m2_asc --limit 5`); the head says the applied threshold, the hint says that smaller places were left out:

```
Ranking miejscowości od najniższej ceny za m²: pokazano 5 z 258 (co najmniej 20 transakcji).
Wskazówka: Przy sortowaniu po cenie pominięto miejsca z mniej niż 20 transakcjami (domyślny próg); wszystkie miejsca pokaże min_transactions=0. Pokazano pierwsze 5 z 258 miejscowości; kolejne pokaże większy limit (najwyżej 100).
Ranking miast na deweloperuch.pl: <ranking link>
1. Kamienna Góra [kamienna-gora] · transakcji: 37 · 3 394 PLN/m² · 46,6 m² · 150 000 PLN
2. Boguszów-gorce [boguszow-gorce] · transakcji: 32 · 3 524 PLN/m² · 43,1 m² · 132 500 PLN
…
```

A price or area of 0 from the service is no value: the place sorts last on price and its line shows `?` instead of the amount (`--json`: `null`). `--json` prints `min_transactions` as the applied threshold.

For powiats the lines read `powiat Kraków [id 14] · transakcji: 225 694 · …`, and there is no ranking link line.

_Source: `src/deweloperuch_mcp/consumers/cli/commands/stats_cities_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/rank_locations_cli_presenter.py`, `uv run deweloperuch stats cities --help`_
