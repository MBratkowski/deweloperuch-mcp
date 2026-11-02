# `get_transaction_statistics`
> Zwraca ceny transakcyjne mieszkań w mieście z Rejestru Cen Nieruchomości (RCN) od 2017 r., w kolejnych miesiącach albo kwartałach: liczbę transakcji i ceny za m². To ceny faktycznych sprzedaży, a nie ceny ofertowe deweloperów (search_offers, get_market_statistics) ani oficjalne ceny NBP (get_government_statistics).
>
> granularity=month (domyślnie): tylko rynek wtórny; mediana i średnia ceny za m², mediana metrażu i mediana ceny mieszkania. granularity=quarter: tylko mediana ceny za m² i liczba transakcji; rynek nieokreślony. Miesiące i kwartały to różne statystyki: nie łącz ich w jeden wykres ani szereg.
>
> Ograniczenia: tylko mieszkania i całe miasta (city_slug z search_locations; bez dzielnic, ulic, agregatów (np. 7-miast) i całej Polski). Domyślnie ostatnie 12 okresów; truncated=true znaczy, że są starsze (zwiększ periods, najwyżej 60; całą historię od 2017 r. daje tylko quarter). Dane RCN spływają z opóźnieniem, więc najnowsze okresy są niepełne: okres z incomplete=true pomiń, nie podawaj jego cen jako trendu. Okres bez transakcji nie ma cen. Trend kończ na last_complete_period (jego dane też mogą się zmienić); brak pola (za mało transakcji): czytaj hint.

Title: „Ceny transakcyjne w czasie”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `city` | string | yes | — | „city_slug miasta z search_locations, np. warszawa, krakow, gdansk (małe litery bez polskich znaków). Statystyki są dla całych miast; dzielnice, ulice, agregaty miast (np. 7-miast) i cała Polska (polska) nie są obsługiwane.” |
| `granularity` | `month` \| `quarter` | no | `month` | „month (domyślnie): miesiące, tylko rynek wtórny, z medianą i średnią ceny za m², medianą metrażu i medianą ceny mieszkania; quarter: kwartały, tylko mediana ceny za m² i liczba transakcji (rynek nieokreślony), za to cała historia od 2017 r. w jednym wywołaniu (periods=60).” |
| `periods` | integer 1-60 | no | `12` | „Ile ostatnich okresów (miesięcy albo kwartałów) zwrócić, 1–60, domyślnie 12. 60 miesięcy to ok. 9 tys. znaków; dla trendu wieloletniego wybierz quarter zamiast wielu miesięcy.” |

The aggregates (`7-miast`, `9-miast`, `10-miast`, `6-miast-bez-warszawy`) and `polska` are refused before any request (they have no transaction statistics here); for aggregate data use `get_government_statistics`.

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Description |
|---|---|
| `city_slug`, `granularity` | The city and `month` or `quarter`. |
| `periods` | Oldest first. Month: `period` (`2021-01`), `transactions`, `median_price_per_m2`, `average_price_per_m2`, `median_area_m2`, `median_price`. Quarter: `period` (`2017-Q1`), `transactions`, `median_price_per_m2`. A period without transactions has no prices. Each period may also carry `incomplete: true` (only present when true): fewer than half of the usual number of transactions because the RCN data is still incomplete; do not draw conclusions from its prices or count. |
| `total`, `returned`, `truncated`, `available_from` | How many periods exist, how many were returned, whether older ones were cut, the first available period. |
| `last_complete_period` | The newest period with a usual number of transactions (not `incomplete`), shown or not; end the trend there, although its data may still change. Omitted when the history is too short or has too few transactions to judge. |
| `hint` | What to do next: when the result is truncated, has `incomplete` periods (it names them and `last_complete_period`) or has too few transactions to judge them. |
| `note` | A warning that the newest periods are incomplete (RCN data lag). Read it before describing a trend. |
| `stats_url` | The transaction statistics page of the city on deweloperuch.pl, `https://deweloperuch.pl/statystyki/{city}/transakcje`: give it to the user as a link. |

**Quarters carry the median.** The `quarter` value `median_price_per_m2` is the median of the price per m². The service names its field `avgPriceSqm`, but it is the median (in Warszawa 2017-Q1 to 2025-Q4 it lies within 2.41 PLN/m² of the median of the statistics page and 165 PLN/m² or more from its mean, [P 2026-10-30]), so 0.1.x labelled it wrongly as `average_price_per_m2`; that key is gone from the MCP result (the CLI `--json` keeps it and sets it to `null`). Quarters have no market: it is not specified (T45 in [open-questions.md](../../open-questions.md): they count 2-4 % more transactions than the secondary-market months of the same quarters).

## Data limitations
- Transaction prices from the RCN, not asking prices; apartments only; whole cities only (no districts, streets, aggregates or `polska`).
- Months (`granularity=month`) are read from the statistics page of the city, `/statystyki/{city}/transakcje` (the page's prop `view`, `monthly`, [pages-rsc.md](../../discovery/pages-rsc.md)): flats of the **secondary market only**, one row per month since 2017-01. The page pads its end with empty months up to the current one; the tool drops the months after the newest one with transactions (Warszawa on 2026-10-31: 115 months, the last 3 incomplete). Empty months before it stay, without prices.
- Quarters (`granularity=quarter`) come from the service's price trend of the city, `GET /api/avg-price-trend/city/{city}` ([endpoints.md](../../discovery/endpoints.md)), since 2017; one call with `periods=60` returns the whole history (39 quarters in the recorded case). The market of quarters is not specified.
- If a month of the page holds transactions of another market than the secondary one, the tool does not return the series and says so (see Errors); the quarters can still be asked.
- RCN data reaches the register with a lag of several months: the newest periods have too few transactions and uncertain prices, so a drop there is not a trend. Months and quarters are different statistics (other source, other market); do not mix them in one series. Sources: [endpoints.md](../../discovery/endpoints.md), [open-questions.md](../../open-questions.md).
- Which periods are `incomplete` is a package rule [W], not a service field: the longest trailing run (at most one reference window: 12 months or 4 quarters) whose transaction counts are all below 50% of the median count of the reference window right before it. Not judged (no `incomplete`, no `last_complete_period`) when that median is below 10 transactions or with fewer than 3 reference periods; for such a small series the hint says that there are too few transactions to judge. Open question: T46 in [open-questions.md](../../open-questions.md).
- Size: 12 months (default) about 2 500 characters with the hint, 60 months about 8 900.

## Errors
| Situation | Message |
|---|---|
| `city` not a city slug (`polska`, an aggregate such as `7-miast`, `Kraków`, `warszawa/../x`) | `city: oczekiwano slug jednego miasta bez polskich znaków, np. warszawa, krakow (nie polska ani agregat miast, np. 7-miast; dane agregatów daje get_government_statistics); slug podaje search_locations (city_slug); podano '7-miast'.` No request is sent. |
| No such place (a 404 of the statistics page for months, a JSON 404 of the price trend for quarters, and `city-lookup` finds no place) | `Nie znaleziono miejscowości o city_slug 'nieistniejace-miasto'. Jeśli slug nie pochodzi z search_locations, weź go stamtąd; jeśli pochodzi, serwis nie ma dla niej tych danych: powiedz to użytkownikowi i nie ponawiaj.` (`tests/golden/mcp/transactions_unknown_city_404.json`, `transactions_unknown_city_quarter_404.json`) |
| The city exists, the service has no transaction statistics for it | `Miejscowość 'Kraków' istnieje, ale serwis nie ma dla niej statystyk transakcji. Nie ponawiaj; powiedz to użytkownikowi.` |
| The lookup cannot tell (it failed) | The earlier message stays: `Serwis nie ma cen transakcyjnych mieszkań dla miasta 'nieistniejace-miasto'. Sprawdź city_slug w search_locations (np. warszawa, krakow); statystyki są dla całych miast, nie dla dzielnic ani ulic. Jeśli city_slug pochodzi z search_locations, serwis nie ma dla niego statystyk: powiedz to użytkownikowi.` |
| A month with transactions outside the secondary market | `Ceny transakcyjne dla 'warszawa': Miesięczne dane serwisu obejmują też transakcje spoza rynku wtórnego, a to narzędzie podaje tylko rynek wtórny, więc nie zwraca tego szeregu. To nie znaczy, że argumenty są błędne: nie zmieniaj ich i nie ponawiaj wywołania, powiedz o tym użytkownikowi. Kwartały (granularity=quarter) idą z innego źródła, ale ich rynek jest nieokreślony.` |
| The page was moved or removed (a redirect, an HTML 404, a 410) | `Ceny transakcyjne dla 'warszawa': Narzędzie nie może pobrać tych danych, bo serwis przeniósł je w inne miejsce albo przestał je udostępniać. To nie musi znaczyć, że argumenty są błędne ani że szukanego obiektu nie ma. Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.` |
| `granularity` outside the list | `Błędny argument narzędzia get_transaction_statistics: granularity musi być jedną z wartości month, quarter, podano "year". Popraw i ponów; nic nie zostało wysłane.` |
| `periods` outside 1-60 | `Błędny argument narzędzia get_transaction_statistics: periods musi być liczbą całkowitą z zakresu 1–60, podano 61. Popraw i ponów; nic nie zostało wysłane.` |
| Unknown argument | `Nieznany argument narzędzia get_transaction_statistics: '…'. Dozwolone argumenty: city, granularity, periods. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| STOP, other service error | As in the [MCP overview](../README.md#errors); service errors with the prefix `Ceny transakcyjne dla '<city>': …` |

## Example
Call:

```json
{"name": "get_transaction_statistics", "arguments": {"city": "warszawa", "granularity": "quarter"}}
```

The result from `tests/golden/mcp/transactions_quarters.json` (the first 3 quarters of the mocked series; note `median_price_per_m2`):

```json
{
  "city_slug": "warszawa", "granularity": "quarter",
  "total": 3, "returned": 3, "truncated": false, "available_from": "2017-Q1",
  "note": "Ostatnie kwartały są niepełne: transakcje trafiają do Rejestru Cen Nieruchomości z kilkumiesięcznym opóźnieniem, więc najnowsze okresy mają zaniżoną liczbę transakcji i mniej pewne ceny. Nie porównuj ich z okresami o zwykłej liczbie transakcji.",
  "stats_url": "https://deweloperuch.pl/statystyki/warszawa/transakcje",
  "periods": [
    {"period": "2017-Q1", "transactions": 2922, "median_price_per_m2": 7595},
    {"period": "2017-Q2", "transactions": 2854, "median_price_per_m2": 7695},
    {"period": "2017-Q3", "transactions": 2893, "median_price_per_m2": 7844}
  ]
}
```

A series with incomplete newest months, call `{"city": "warszawa"}` (`tests/golden/mcp/transactions_warszawa_20261031.json`, the real page of 2026-10-31, `tests/fixtures/rsc/stats_tx_warszawa_20261031.rsc`; `stats_url` left out):

```json
{
  "city_slug": "warszawa", "granularity": "month",
  "total": 115, "returned": 12, "truncated": true, "available_from": "2017-01",
  "last_complete_period": "2026-04",
  "hint": "Pokazano ostatnie 12 z 115 okresów (dane od 2017-01); starsze pokaże większe periods (najwyżej 60). Okresy 2026-05, 2026-06 i 2026-07 mają mniej niż połowę zwykłej liczby transakcji (dane RCN jeszcze niepełne): nie wyciągaj wniosków z ich cen ani liczby transakcji. Ostatni okres ze zwykłą liczbą transakcji: 2026-04 (jego dane też mogą się jeszcze zmienić).",
  "note": "Ostatnie miesiące są niepełne: transakcje trafiają do Rejestru Cen Nieruchomości z kilkumiesięcznym opóźnieniem, więc najnowsze okresy mają zaniżoną liczbę transakcji i mniej pewne ceny. Nie porównuj ich z okresami o zwykłej liczbie transakcji.",
  "periods": [
    {"period": "2026-04", "transactions": 986, "median_price_per_m2": 16558, "average_price_per_m2": 16989, "median_area_m2": 48.6, "median_price": 772500},
    {"period": "2026-05", "transactions": 22, "incomplete": true, "median_price_per_m2": 15495, "average_price_per_m2": 16285, "median_area_m2": 52.2, "median_price": 754750},
    {"period": "2026-06", "transactions": 0, "incomplete": true},
    {"period": "2026-07", "transactions": 35, "incomplete": true, "median_price_per_m2": 33176, "average_price_per_m2": 31187, "median_area_m2": 53.4, "median_price": 1360209}
  ]
}
```

(The `periods` list is shortened to its last four of 12 items.)

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_transaction_statistics_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_transaction_statistics_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_transaction_statistics.py`, `src/deweloperuch_mcp/api/adapters/transaction_statistics_api.py`, `tests/snapshots/mcp_tools.json`_
