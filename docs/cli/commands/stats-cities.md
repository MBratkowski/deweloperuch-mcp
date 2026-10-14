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
| `--min-transactions` | int | `0` | Skip places with fewer transactions (when sorting by price). Help text: „Pomiń miejsca z mniejszą liczbą transakcji (przy sortowaniu po cenie).” |
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

For powiats the lines read `powiat Kraków [id 14] · transakcji: 225 694 · …`, and there is no ranking link line.

_Source: `src/deweloperuch_mcp/consumers/cli/commands/stats_cities_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/rank_locations_cli_presenter.py`, `uv run deweloperuch stats cities --help`_
