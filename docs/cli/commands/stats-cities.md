# `deweloperuch stats cities`
Shows a ranking of places or powiats by RCN transactions (the number of transactions and the transaction price per m²), or of the 66 cities with powiat rights by a GUS or NBP indicator. Equivalent to the MCP tool [`rank_locations`](../../mcp/tools/rank_locations.md).

## Usage
```
deweloperuch stats cities [OPTIONS]
```

`--help` description: „Pokaż ranking miejscowości albo powiatów według transakcji RCN albo miast według wskaźnika GUS lub NBP.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `--level` | `city` \| `powiat` | `city` | `city`: places (small towns too); `powiat`: powiats. Help text: „city: miejscowości (także małe); powiat: powiaty.” |
| `--sort` | `transactions_desc` \| `price_per_m2_desc` \| `price_per_m2_asc` \| `value_desc` \| `value_asc` | `transactions_desc`; with `--indicator` `value_desc` | The most transactions, or by price per m² (descending, ascending), or, with `--indicator`, by the value of the indicator (`value_desc`, `value_asc`; only with `--indicator`). Help text: „Najwięcej transakcji (domyślnie), po cenie za m² (malejąco, rosnąco) albo, z --indicator, po wartości wskaźnika (value_desc domyślnie, value_asc).” |
| `--limit` | int | `20` | How many first positions to show, 1–100. Help text: „Ile pierwszych pozycji pokazać, 1–100.” |
| `--min-transactions` | int | not given | Skip places with fewer transactions. Not given: 20 when sorting by price (both levels), 0 for `transactions_desc`; an explicit value, including 0 (all places), wins. **Behaviour change (BREAKING):** price sorts used to include every place by default. Help text: „Pomiń miejsca z mniejszą liczbą transakcji; domyślnie 20 przy sortowaniu po cenie, 0 po liczbie transakcji (0: wszystkie miejsca).” |
| `--market` | `secondary` \| `primary` \| `all` | not given (`secondary`) | Only with `--level powiat`: the secondary market (default), the primary market, or both in the service's own figure (its count is not always secondary + primary). Powiats without figures for the market are left out (the hint says how many). Help text: „Tylko --level powiat: secondary (rynek wtórny, domyślnie), primary (pierwotny) albo all (oba rynki w zestawieniu serwisu).” |
| `--indicator` | `unemployment_rate` \| `average_wage` \| `dwellings_completed` \| `dwellings_started` \| `average_dwelling_area` \| `natural_increase` \| `nbp_price_per_m2` | not given (a transaction ranking) | Ranks the 66 cities with powiat rights by the indicator instead of by transactions; not with `--level powiat`, `--min-transactions` or `--market`. `average_wage` is the average monthly gross wage, the average for the year. Help text: „Ranking 66 miast na prawach powiatu według wskaźnika GUS albo NBP zamiast transakcji (bez --level powiat, --min-transactions i --market); average_wage to przeciętne miesięczne wynagrodzenie brutto, średnia za rok.” The units and periods of the indicators are listed in [`rank_locations`](../../mcp/tools/rank_locations.md). |
| `--json` | flag | off | Print the result as JSON (the domain model). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (`--level`, `--sort`, `--market` or `--indicator` outside the list, `--limit` outside 1–100, `--min-transactions` outside 0–10 000 000, or a combination the command refuses: `--indicator` with `--level powiat`, `--min-transactions`, `--market` or a price sort, `--sort value_desc`/`value_asc` without `--indicator`, `--market` without `--level powiat`), 3 STOP, 4 service error, 6 the service moved or removed the route.

`--level powiat` works again (0.2.0): it reads `statystyki/powiat-map-stats`, a 12-month window, and names the powiats from the table packaged in the wheel.

## Examples
```
deweloperuch stats cities
deweloperuch stats cities --sort price_per_m2_desc --min-transactions 50 --limit 10
deweloperuch stats cities --level powiat --market primary --sort price_per_m2_asc
deweloperuch stats cities --indicator unemployment_rate --limit 10
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

A powiat ranking names the market and the 12-month window in its head and has no ranking link line (`tests/golden/cli/stats_cities_powiat_primary_price_asc.json`, `stats cities --level powiat --market primary --sort price_per_m2_asc`):

```
Ranking powiatów od najniższej ceny za m² (rynek pierwotny, 2025-11–2026-10): pokazano 3 z 3 (co najmniej 20 transakcji).
1. powiat łosicki [id 2] · transakcji: 59 · 6 263 PLN/m² · 44,9 m² · 284 000 PLN
2. powiat ropczycko-sędziszowski [id 1] · transakcji: 29 · 8 362 PLN/m² · 54,4 m² · 455 000 PLN
3. powiat piaseczyński [id 3] · transakcji: 3 335 · 9 900 PLN/m² · 62,7 m² · 635 049 PLN
Serwis nie podaje, czy ceny i metraż to średnie, czy mediany.
```

An indicator ranking prints the indicator, its period and the order in the head, and one line per city with the value and its unit (`tests/golden/cli/stats_cities_indicator_unemployment.json`, `stats cities --indicator unemployment_rate`):

```
Ranking miast wg wskaźnika: stopa bezrobocia rejestrowanego (2026-08), od najwyższej wartości: pokazano 3 z 3.
1. Białystok [bialystok] · 6 %
2. Bydgoszcz [bydgoszcz] · 2,8 %
3. Warszawa [warszawa] · 1,6 %
```

`--json` prints the same model as the MCP tool plus `null` fields; in an indicator ranking `min_transactions`, `transaction_count` and the price fields are `null`, and each item has `value` and `stats_url` (`tests/golden/cli/stats_cities_indicator_json.json`).

_Source: `src/deweloperuch_mcp/consumers/cli/commands/stats_cities_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/rank_locations_cli_presenter.py`, `uv run deweloperuch stats cities --help`_
