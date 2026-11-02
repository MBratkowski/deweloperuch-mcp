# `deweloperuch stats transactions`
Shows apartment transaction prices from the RCN for one city, month by month or quarter by quarter, since 2017; the months cover the secondary market only. Equivalent to the MCP tool [`get_transaction_statistics`](../../mcp/tools/get_transaction_statistics.md).

## Usage
```
deweloperuch stats transactions [OPTIONS] CITY
```

`--help` description: „Pokaż ceny transakcyjne mieszkań (RCN) w mieście, miesiąc po miesiącu albo kwartałami.” and a second paragraph: „Dane od 2017 r.; miesiące obejmują tylko rynek wtórny.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `CITY` (argument, required) | text | — | A city slug without Polish characters, e.g. warszawa, krakow (given by `locations search`). No districts, streets, aggregates (such as `7-miast`) or the whole of Poland. Help text: „Slug miasta bez polskich znaków, np. warszawa, krakow (podaje go deweloperuch locations search). Bez dzielnic, ulic, agregatów (np. 7-miast) i całej Polski.” |
| `--granularity` | `month` \| `quarter` | `month` | `month`: months of the secondary market (medians and averages); `quarter`: quarters (only the median price per m², the market is not specified). Help text: „month: miesiące, tylko rynek wtórny (mediany i średnie); quarter: kwartały (tylko mediana ceny za m², rynek nieokreślony).” |
| `--periods` | int | `12` | How many latest periods to show (months or quarters), 1–1000. In MCP `periods` is 1–60. Help text: „Ile ostatnich okresów pokazać (miesięcy, kwartałów).” |
| `--json` | flag | off | Print the result as JSON (the domain model). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common:

| Code | Meaning |
|---|---|
| 0 | The periods. |
| 2 | `CITY=polska`, an aggregate (`7-miast`, `9-miast`, `10-miast`, `6-miast-bez-warszawy`), a Polish character or other non-slug `CITY` (`Błąd: city: oczekiwano slug jednego miasta bez polskich znaków, np. warszawa, krakow (nie polska ani agregat miast, np. 7-miast; dane agregatów daje get_government_statistics); slug podaje search_locations (city_slug); podano '6-miast-bez-warszawy'.`; no request is sent), `--granularity` outside the list, `--periods` outside 1–1000. |
| 3 | STOP. |
| 4 | Service error (5xx, network). |
| 6 | The service moved or removed the page (`Błąd: Ceny transakcyjne dla 'warszawa': Narzędzie nie może pobrać tych danych, …`), or a month holds transactions outside the secondary market (`Błąd: Ceny transakcyjne dla 'warszawa': Miesięczne dane serwisu obejmują też transakcje spoza rynku wtórnego, …`; `--granularity quarter` still works). |
| 7 | Not found (months and quarters). After the service's „unknown” one `city-lookup` request tells the cases apart: no such place (`Błąd: Nie znaleziono miejscowości o city_slug 'nieistniejace-miasto'. Jeśli slug nie pochodzi z search_locations, weź go stamtąd; jeśli pochodzi, serwis nie ma dla niej tych danych: powiedz to użytkownikowi i nie ponawiaj.`), or a known city without transaction statistics (`Błąd: Miejscowość 'Kraków' istnieje, ale serwis nie ma dla niej statystyk transakcji. Nie ponawiaj; powiedz to użytkownikowi.`). If the lookup fails, the earlier `Błąd: Serwis nie ma cen transakcyjnych mieszkań dla miasta 'nieistniejace-miasto'. Sprawdź city_slug w search_locations (np. warszawa, krakow); … powiedz to użytkownikowi.` stays. With a `Szczegóły:` line: the target, the status and the media type. |

## Examples
```
deweloperuch stats transactions warszawa
deweloperuch stats transactions warszawa --granularity quarter --periods 40
deweloperuch stats transactions krakow --json
```

Output of the first call (`tests/golden/cli/stats_transactions_warszawa_20261031.json`, a mocked service replaying the real page of 2026-10-31; the first eight periods left out). Incomplete periods are marked with ` *` and a legend line closes the table; the hint names them and the last period with a usual count:

```
Ceny transakcyjne mieszkań (RCN) · warszawa · miesięcznie
Okresy: pokazano 12 z 115 (dane od 2017-01).
Wskazówka: Pokazano ostatnie 12 z 115 okresów (dane od 2017-01); starsze pokaże większa wartość periods. Okresy 2026-05, 2026-06 i 2026-07 mają mniej niż połowę zwykłej liczby transakcji (dane RCN jeszcze niepełne): nie wyciągaj wniosków z ich cen ani liczby transakcji. Ostatni okres ze zwykłą liczbą transakcji: 2026-04 (jego dane też mogą się jeszcze zmienić).
Uwaga: Ostatnie miesiące są niepełne: transakcje trafiają do Rejestru Cen Nieruchomości z kilkumiesięcznym opóźnieniem, więc najnowsze okresy mają zaniżoną liczbę transakcji i mniej pewne ceny. Nie porównuj ich z okresami o zwykłej liczbie transakcji.
Strona na deweloperuch.pl: https://deweloperuch.pl/statystyki/warszawa/transakcje
Okres      Transakcje  Mediana PLN/m²  Średnia PLN/m²  Mediana m²  Mediana ceny PLN
…
2026-04           986          16 558          16 989        48,6           772 500
2026-05 *          22          15 495          16 285        52,2           754 750
2026-06 *           0               –               –           –                 –
2026-07 *          35          33 176          31 187        53,4         1 360 209
* okres niepełny: mniej niż połowa zwykłej liczby transakcji (dane RCN jeszcze niepełne).
```

Quarters (`--granularity quarter`, `tests/golden/cli/stats_transactions_warszawa_quarter.json`) have the columns `Okres`, `Transakcje` and `Mediana PLN/m²`; the quarterly average price per m² is gone (0.1.x showed `Średnia PLN/m²`):

```
Okres    Transakcje  Mediana PLN/m²
2017-Q1       2 922           7 595
2017-Q2       2 854           7 695
2017-Q3       2 893           7 844
```

With `--json` every period has `incomplete` (a bool, `false` included) and the top level has `last_complete_period` (`null` when it cannot be judged; for example in the mocked series of `tests/golden/cli/stats_transactions_warszawa_json.json`). In a quarter `median_price_per_m2` has the value and `average_price_per_m2` is `null` (`tests/golden/cli/stats_transactions_warszawa_quarter_json.json`). Which periods are incomplete is a package rule [W], see [`get_transaction_statistics`](../../mcp/tools/get_transaction_statistics.md#data-limitations).

_Source: `src/deweloperuch_mcp/consumers/cli/commands/stats_transactions_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/get_transaction_statistics_cli_presenter.py`, `uv run deweloperuch stats transactions --help`_
