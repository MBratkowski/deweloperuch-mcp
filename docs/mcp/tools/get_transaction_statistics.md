# `get_transaction_statistics`
> Zwraca ceny transakcyjne mieszkań w mieście z Rejestru Cen Nieruchomości (RCN) w kolejnych miesiącach albo kwartałach: liczbę transakcji i ceny za m². To ceny faktycznych sprzedaży, a nie ceny ofertowe deweloperów (search_offers, get_market_statistics) ani oficjalne ceny NBP (get_government_statistics).
>
> granularity=month (domyślnie): mediana i średnia ceny za m², mediana metrażu i mediana ceny mieszkania. granularity=quarter: tylko średnia cena za m² i liczba transakcji, za to dłuższa historia. Miesiące i kwartały to różne statystyki: nie łącz ich w jeden wykres ani szereg.
>
> Zwraca periods (od najstarszego; okres bez transakcji nie ma cen) oraz total, returned, truncated, available_from, last_complete_period, hint, note i stats_url (link).
>
> Ograniczenia: tylko mieszkania i całe miasta (city_slug z search_locations; bez dzielnic, ulic i całej Polski). Domyślnie ostatnie 12 okresów; truncated=true znaczy, że są starsze (zwiększ periods, najwyżej 60). Najnowsze okresy są niepełne (opóźnienie RCN). Okres z incomplete=true pomiń: nie podawaj jego cen jako trendu. Trend kończ na last_complete_period (jego dane też mogą się zmienić); brak pola (za mało transakcji): czytaj hint.

Title: „Ceny transakcyjne w czasie”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `city` | string | yes | — | „city_slug miasta z search_locations, np. warszawa, krakow, gdansk (małe litery bez polskich znaków). Statystyki są dla całych miast; dzielnice, ulice i cała Polska (polska) nie są obsługiwane.” |
| `granularity` | `month` \| `quarter` | no | `month` | „month (domyślnie): miesiące, z medianą i średnią ceny za m², medianą metrażu i medianą ceny mieszkania; quarter: kwartały, tylko średnia cena za m² i liczba transakcji, ale dłuższa historia.” |
| `periods` | integer 1-60 | no | `12` | „Ile ostatnich okresów (miesięcy albo kwartałów) zwrócić, 1–60, domyślnie 12. 60 miesięcy to ok. 9 tys. znaków; dla trendu wieloletniego wybierz quarter zamiast wielu miesięcy.” |

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Description |
|---|---|
| `city_slug`, `granularity` | The city and `month` or `quarter`. |
| `periods` | Oldest first. Month: `period` (`2021-01`), `transactions`, `median_price_per_m2`, `average_price_per_m2`, `median_area_m2`, `median_price`. Quarter: `period` (`2017-Q1`), `transactions`, `average_price_per_m2`. A period without transactions has no prices. Each period may also carry `incomplete: true` (only present when true): fewer than half of the usual number of transactions because the RCN data is still incomplete; do not draw conclusions from its prices or count. |
| `total`, `returned`, `truncated`, `available_from` | How many periods exist, how many were returned, whether older ones were cut, the first available period. |
| `last_complete_period` | The newest period with a usual number of transactions (not `incomplete`), shown or not; end the trend there, although its data may still change. Omitted when the history is too short or has too few transactions to judge. |
| `hint` | What to do next: when the result is truncated, has `incomplete` periods (it names them and `last_complete_period`) or has too few transactions to judge them. |
| `note` | A warning that the newest periods are incomplete (RCN data lag). Read it before describing a trend. |
| `stats_url` | The statistics page of the city on deweloperuch.pl: give it to the user as a link. |

## Data limitations
- Transaction prices from the RCN, not asking prices; apartments only; whole cities only (no districts, streets or `polska`).
- RCN data reaches the register with a lag of several months: the newest periods have too few transactions and uncertain prices, so a drop there is not a trend. Months and quarters are different statistics; do not mix them in one series. Sources: [endpoints.md](../../discovery/endpoints.md), [open-questions.md](../../open-questions.md).
- Which periods are `incomplete` is a package rule [W], not a service field: the longest trailing run (at most one reference window: 12 months or 4 quarters) whose transaction counts are all below 50% of the median count of the reference window right before it. Not judged (no `incomplete`, no `last_complete_period`) when that median is below 10 transactions or with fewer than 3 reference periods; for such a small series the hint says that there are too few transactions to judge. Open question: T46 in [open-questions.md](../../open-questions.md).
- Size: 12 months (default) about 900 characters, 60 months about 9 100.

## Errors
| Situation | Message |
|---|---|
| `city` not a city slug (`polska`, `Kraków`, `warszawa/../x`) | `city: oczekiwano slug miasta bez polskich znaków, np. warszawa, krakow (nie polska: cała Polska nie jest obsługiwana); slug podaje search_locations (city_slug); podano 'polska'.` |
| The service has no data for the city | `Serwis nie ma cen transakcyjnych mieszkań dla miasta 'nieistniejace-miasto'. Sprawdź city_slug w search_locations (np. warszawa, krakow); statystyki są dla całych miast, nie dla dzielnic ani ulic.` |
| `granularity` outside the list | `Błędny argument narzędzia get_transaction_statistics: granularity musi być jedną z wartości month, quarter, podano "year". Popraw i ponów; nic nie zostało wysłane.` |
| `periods` outside 1-60 | `Błędny argument narzędzia get_transaction_statistics: periods musi być liczbą całkowitą z zakresu 1–60, podano 61. Popraw i ponów; nic nie zostało wysłane.` |
| Unknown argument | `Nieznany argument narzędzia get_transaction_statistics: '…'. Dozwolone argumenty: city, granularity, periods. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| STOP, service error | As in the [MCP overview](../README.md#errors); service errors with the prefix `Ceny transakcyjne dla '<city>': …` |

## Example
Call:

```json
{"name": "get_transaction_statistics", "arguments": {"city": "warszawa", "granularity": "quarter"}}
```

The result from `tests/golden/mcp/transactions_quarters.json` (first 3 quarters of the mocked series):

```json
{
  "city_slug": "warszawa", "granularity": "quarter",
  "total": 3, "returned": 3, "truncated": false, "available_from": "2017-Q1",
  "note": "Ostatnie kwartały są niepełne: transakcje trafiają do Rejestru Cen Nieruchomości z kilkumiesięcznym opóźnieniem, więc najnowsze okresy mają zaniżoną liczbę transakcji i mniej pewne ceny. Nie porównuj ich z okresami o zwykłej liczbie transakcji.",
  "stats_url": "https://deweloperuch.pl/statystyki/ceny-transakcyjne/mieszkania/warszawa",
  "periods": [
    {"period": "2017-Q1", "transactions": 2922, "average_price_per_m2": 7595},
    {"period": "2017-Q2", "transactions": 2854, "average_price_per_m2": 7695},
    {"period": "2017-Q3", "transactions": 2893, "average_price_per_m2": 7844}
  ]
}
```

A series with incomplete newest months, call `{"city": "warszawa"}` (`tests/golden/mcp/transactions_warszawa_20261015.json`, a sample of 2026-10-15; `stats_url` left out):

```json
{
  "city_slug": "warszawa", "granularity": "month",
  "total": 67, "returned": 12, "truncated": true, "available_from": "2021-01",
  "last_complete_period": "2026-04",
  "hint": "Pokazano ostatnie 12 z 67 okresów (dane od 2021-01); starsze pokaże większe periods (najwyżej 60). Okresy 2026-05, 2026-06 i 2026-07 mają mniej niż połowę zwykłej liczby transakcji (dane RCN jeszcze niepełne): nie wyciągaj wniosków z ich cen ani liczby transakcji. Ostatni okres ze zwykłą liczbą transakcji: 2026-04 (jego dane też mogą się jeszcze zmienić).",
  "note": "Ostatnie miesiące są niepełne: transakcje trafiają do Rejestru Cen Nieruchomości z kilkumiesięcznym opóźnieniem, więc najnowsze okresy mają zaniżoną liczbę transakcji i mniej pewne ceny. Nie porównuj ich z okresami o zwykłej liczbie transakcji.",
  "periods": [
    {"period": "2026-04", "transactions": 987, "median_price_per_m2": 16542, "average_price_per_m2": 16980, "median_area_m2": 48.6, "median_price": 770000},
    {"period": "2026-05", "transactions": 22, "incomplete": true, "median_price_per_m2": 15496, "average_price_per_m2": 16285, "median_area_m2": 52.2, "median_price": 754750},
    {"period": "2026-06", "transactions": 0, "incomplete": true},
    {"period": "2026-07", "transactions": 35, "incomplete": true, "median_price_per_m2": 33176, "average_price_per_m2": 31186, "median_area_m2": 53.4, "median_price": 1360209}
  ]
}
```

(The `periods` list is shortened to its last four of 12 items.)

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_transaction_statistics_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_transaction_statistics_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_transaction_statistics.py`, `tests/snapshots/mcp_tools.json`_
