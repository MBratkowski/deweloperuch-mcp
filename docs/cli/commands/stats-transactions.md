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

Output of the first call (`tests/golden/cli/stats_transactions_warszawa.json`, a three-month mocked series):

```
Ceny transakcyjne mieszkań (RCN) · warszawa · miesięcznie
Okresy: pokazano 3 z 3 (dane od 2021-01).
Uwaga: Ostatnie miesiące są niepełne: transakcje trafiają do Rejestru Cen Nieruchomości z kilkumiesięcznym opóźnieniem, więc najnowsze okresy mają zaniżoną liczbę transakcji i mniej pewne ceny. Nie porównuj ich z pełnymi okresami.
Strona na deweloperuch.pl: https://deweloperuch.pl/statystyki/ceny-transakcyjne/mieszkania/warszawa
Okres    Transakcje  Mediana PLN/m²  Średnia PLN/m²  Mediana m²  Mediana ceny PLN
2021-01         963          10 651          10 876        49,4           502 000
2021-02       1 165          10 575          10 854        48,8           495 000
2021-03       1 327          10 858          10 981        48,5           510 000
```

_Source: `src/deweloperuch_mcp/consumers/cli/commands/stats_transactions_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/get_transaction_statistics_cli_presenter.py`, `uv run deweloperuch stats transactions --help`_
