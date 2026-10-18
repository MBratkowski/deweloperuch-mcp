# `deweloperuch stats transactions`
Shows apartment transaction prices from the RCN for one city, month by month or quarter by quarter. Equivalent to the MCP tool [`get_transaction_statistics`](../../mcp/tools/get_transaction_statistics.md).

## Usage
```
deweloperuch stats transactions [OPTIONS] CITY
```

`--help` description: „Pokaż ceny transakcyjne mieszkań (RCN) w mieście, miesiąc po miesiącu albo kwartałami.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `CITY` (argument, required) | text | — | A city slug without Polish characters, e.g. warszawa, krakow (given by `locations search`). No districts, streets or the whole of Poland. Help text: „Slug miasta bez polskich znaków, np. warszawa, krakow (podaje go deweloperuch locations search). Bez dzielnic, ulic i całej Polski.” |
| `--granularity` | `month` \| `quarter` | `month` | `month`: months (medians and averages); `quarter`: quarters (the average price per m², a longer history). Help text: „month: miesiące (mediany i średnie); quarter: kwartały (średnia cena za m², dłuższa historia).” |
| `--periods` | int | `12` | How many latest periods to show (months or quarters), 1–1000. In MCP `periods` is 1–60. Help text: „Ile ostatnich okresów pokazać (miesięcy, kwartałów).” |
| `--json` | flag | off | Print the result as JSON (the domain model). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (`CITY=polska`, a Polish character or other non-slug `CITY`, `--granularity` outside the list, `--periods` outside 1–1000), 3 STOP, 4 service error, 7 the service has no transaction prices for the city.

## Examples
```
deweloperuch stats transactions warszawa
deweloperuch stats transactions warszawa --granularity quarter --periods 40
deweloperuch stats transactions krakow --json
```

Output of the first call (`tests/golden/cli/stats_transactions_warszawa_20261015.json`, a sample of 2026-10-15; the first eight periods left out). Incomplete periods are marked with ` *` and a legend line closes the table; the hint names them and the last period with a usual count:

```
Ceny transakcyjne mieszkań (RCN) · warszawa · miesięcznie
Okresy: pokazano 12 z 67 (dane od 2021-01).
Wskazówka: Pokazano ostatnie 12 z 67 okresów (dane od 2021-01); starsze pokaże większa wartość periods. Okresy 2026-05, 2026-06 i 2026-07 mają mniej niż połowę zwykłej liczby transakcji (dane RCN jeszcze niepełne): nie wyciągaj wniosków z ich cen ani liczby transakcji. Ostatni okres ze zwykłą liczbą transakcji: 2026-04 (jego dane też mogą się jeszcze zmienić).
Uwaga: Ostatnie miesiące są niepełne: transakcje trafiają do Rejestru Cen Nieruchomości z kilkumiesięcznym opóźnieniem, więc najnowsze okresy mają zaniżoną liczbę transakcji i mniej pewne ceny. Nie porównuj ich z okresami o zwykłej liczbie transakcji.
Strona na deweloperuch.pl: <stats link>
Okres      Transakcje  Mediana PLN/m²  Średnia PLN/m²  Mediana m²  Mediana ceny PLN
…
2026-04           987          16 542          16 980        48,6           770 000
2026-05 *          22          15 496          16 285        52,2           754 750
2026-06 *           0               –               –           –                 –
2026-07 *          35          33 176          31 186        53,4         1 360 209
* okres niepełny: mniej niż połowa zwykłej liczby transakcji (dane RCN jeszcze niepełne).
```

With `--json` every period has `incomplete` (a bool, `false` included) and the top level has `last_complete_period` (`null` when it cannot be judged; for example in the mocked series of `tests/golden/cli/stats_transactions_warszawa_json.json`). Which periods are incomplete is a package rule [W], see [`get_transaction_statistics`](../../mcp/tools/get_transaction_statistics.md#data-limitations).

_Source: `src/deweloperuch_mcp/consumers/cli/commands/stats_transactions_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/get_transaction_statistics_cli_presenter.py`, `uv run deweloperuch stats transactions --help`_
