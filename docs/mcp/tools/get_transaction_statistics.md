# `get_transaction_statistics`
> Zwraca ceny transakcyjne mieszkań w mieście z Rejestru Cen Nieruchomości (RCN) w kolejnych miesiącach albo kwartałach: liczbę transakcji i ceny za m². To ceny faktycznych sprzedaży, a nie ceny ofertowe deweloperów (search_offers, get_market_statistics) ani oficjalne ceny NBP (get_government_statistics).
>
> granularity=month (domyślnie): mediana i średnia ceny za m², mediana metrażu i mediana ceny mieszkania. granularity=quarter: tylko średnia cena za m² i liczba transakcji, za to dłuższa historia. Miesiące i kwartały to różne statystyki: nie łącz ich w jeden wykres ani szereg.
>
> Zwraca periods (od najstarszego; okres bez transakcji nie ma cen) oraz total, returned, truncated, available_from, hint, note i stats_url (link dla użytkownika).
>
> Ograniczenia: tylko mieszkania i całe miasta (city_slug z search_locations; bez dzielnic, ulic i całej Polski). Domyślnie ostatnie 12 okresów; truncated=true znaczy, że są starsze (zwiększ periods, najwyżej 60). Najnowsze miesiące są niepełne, bo transakcje trafiają do RCN z kilkumiesięcznym opóźnieniem: mają zaniżoną liczbę transakcji i niepewne ceny, więc ich spadku nie traktuj jako trendu (przeczytaj note).

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
| `periods` | Oldest first. Month: `period` (`2021-01`), `transactions`, `median_price_per_m2`, `average_price_per_m2`, `median_area_m2`, `median_price`. Quarter: `period` (`2017-Q1`), `transactions`, `average_price_per_m2`. A period without transactions has no prices. |
| `total`, `returned`, `truncated`, `available_from`, `hint` | How many periods exist, how many were returned, whether older ones were cut, the first available period. |
| `note` | A warning that the newest periods are incomplete (RCN data lag). Read it before describing a trend. |
| `stats_url` | The statistics page of the city on deweloperuch.pl: give it to the user as a link. |

## Data limitations
- Transaction prices from the RCN, not asking prices; apartments only; whole cities only (no districts, streets or `polska`).
- RCN data reaches the register with a lag of several months: the newest periods have too few transactions and uncertain prices, so a drop there is not a trend. Months and quarters are different statistics; do not mix them in one series. Sources: [endpoints.md](../../discovery/endpoints.md), [open-questions.md](../../open-questions.md).
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
  "note": "Ostatnie kwartały są niepełne: transakcje trafiają do Rejestru Cen Nieruchomości z kilkumiesięcznym opóźnieniem, więc najnowsze okresy mają zaniżoną liczbę transakcji i mniej pewne ceny. Nie porównuj ich z pełnymi okresami.",
  "stats_url": "https://deweloperuch.pl/statystyki/ceny-transakcyjne/mieszkania/warszawa",
  "periods": [
    {"period": "2017-Q1", "transactions": 2922, "average_price_per_m2": 7595},
    {"period": "2017-Q2", "transactions": 2854, "average_price_per_m2": 7695},
    {"period": "2017-Q3", "transactions": 2893, "average_price_per_m2": 7844}
  ]
}
```

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_transaction_statistics_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_transaction_statistics_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_transaction_statistics.py`, `tests/snapshots/mcp_tools.json`_
