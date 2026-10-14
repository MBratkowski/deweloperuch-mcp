# `rank_locations`
> Ranking miejscowości (level=city) albo powiatów (level=powiat) w Polsce według transakcji z Rejestru Cen Nieruchomości (RCN): liczba transakcji i cena transakcyjna za m². Dla porównania wielu miast (gdzie najwięcej transakcji, gdzie najdrożej, gdzie najtaniej): to narzędzie; dla trendu jednego miasta w czasie: get_transaction_statistics. To ceny transakcyjne, nie ofertowe; oferty deweloperów daje search_offers.
>
> Zwraca total (miejsca z co najmniej min_transactions transakcji), returned, truncated, hint i items (name, city_slug albo powiat_id, transaction_count, price_per_m2, area_m2, price); dla city także ranking_url (strona rankingu na deweloperuch.pl: podaj ją użytkownikowi jako link). powiat_id jest informacyjny: żadne narzędzie go nie przyjmuje.
>
> Ograniczenia: serwis nie podaje okresu ani tego, czy ceny i metraż to średnie, czy mediany: przedstawiaj je jako wartości podane przez serwis. Liczby transakcji powiatów obejmują wiele lat: służą tylko do uporządkowania, nie są bieżącym wolumenem; nie porównuj ich z liczbami miejscowości. Przy sortowaniu miejscowości po cenie podaj min_transactions (np. 50): przy kilku transakcjach cena bywa przypadkowa.

Title: „Ranking miast i powiatów”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `level` | `city` \| `powiat` | no | `city` | „city: miejscowości (miasta, także małe miasteczka i wsie), domyślnie; powiat: powiaty (bez ranking_url i bez odpowiednika w search_locations).” |
| `sort` | `transactions_desc` \| `price_per_m2_desc` \| `price_per_m2_asc` | no | `transactions_desc` | „transactions_desc: najwięcej transakcji (domyślnie); price_per_m2_desc: najwyższa cena za m²; price_per_m2_asc: najniższa cena za m². Miejsca bez ceny są na końcu.” |
| `limit` | integer 1-100 | no | `20` | „Ile pierwszych pozycji rankingu zwrócić, 1–100, domyślnie 20. Pozycja to ok. 120 znaków wyniku. Dla pełnych list zawężaj min_transactions, nie podnoś limitu bez potrzeby.” |
| `min_transactions` | integer 0-10 000 000 | no | `0` | „Pomiń miejsca z mniejszą liczbą transakcji; domyślnie 0 (wszystkie). Przy sortowaniu miejscowości (level=city) po cenie podaj np. 50.” |

All parameters are optional; blank text for `level` and `sort` means the default ([argument rules](../README.md#argument-rules)).

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Description |
|---|---|
| `level`, `sort`, `min_transactions` | The query as applied. |
| `total` | Places with at least `min_transactions` transactions. |
| `returned`, `truncated`, `hint` | Items returned; `true` when more exist (the hint says how to see them). |
| `ranking_url` | The ranking page on deweloperuch.pl (`level=city` only): give it to the user as a link. |
| `items` | `name`, `city_slug` (cities) or `powiat_id` (powiats; informational, no tool accepts it), `transaction_count`, `price_per_m2`, `area_m2`, `price`. |

## Data limitations
- The service gives no period and does not say whether prices and areas are averages or medians: present them as values given by the service.
- Powiat transaction counts cover many years: they only order the list, are not the current volume and must not be compared with city counts.
- Sorting cities by price without `min_transactions` favours places with few, random transactions. Sources: [endpoints.md](../../discovery/endpoints.md) (`city-transaction-stats`), [open-questions.md](../../open-questions.md).
- Size: about 120 characters per item (20 items about 2 700).

## Errors
| Situation | Message |
|---|---|
| `level`, `sort` outside the list | `Błędny argument narzędzia rank_locations: level musi być jedną z wartości city, powiat, podano "gmina". Popraw i ponów; nic nie zostało wysłane.` |
| `limit` outside 1-100 | `Błędny argument narzędzia rank_locations: limit musi być liczbą całkowitą z zakresu 1–100, podano 101. Popraw i ponów; nic nie zostało wysłane.` |
| `min_transactions` outside 0-10 000 000 | `Błędny argument narzędzia rank_locations: min_transactions musi być liczbą całkowitą z zakresu 0–10000000, podano -1. Popraw i ponów; nic nie zostało wysłane.` |
| Unknown argument | `Nieznany argument narzędzia rank_locations: '…'. Dozwolone argumenty: level, sort, limit, min_transactions. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| STOP, service error | As in the [MCP overview](../README.md#errors); a service error: `Ranking miejscowości: Serwis odpowiedział błędem HTTP 500. Nic nie ponawiam; spróbuj później.` |

## Example
Call:

```json
{"name": "rank_locations", "arguments": {"level": "powiat"}}
```

The result from `tests/golden/mcp/rank_powiats.json`:

```json
{
  "level": "powiat", "sort": "transactions_desc", "min_transactions": 0,
  "total": 3, "returned": 3, "truncated": false,
  "items": [
    {"name": "powiat Warszawa", "powiat_id": 302, "transaction_count": 351314, "price_per_m2": 16367.0, "area_m2": 48.6, "price": 780000.0},
    {"name": "powiat Kraków", "powiat_id": 14, "transaction_count": 225694, "price_per_m2": 14899.0, "area_m2": 47.7, "price": 695000.0},
    {"name": "powiat Wrocław", "powiat_id": 33, "transaction_count": 166308, "price_per_m2": 12547.0, "area_m2": 50.1, "price": 607000.0}
  ]
}
```

A `level=city` call adds `ranking_url` (`https://deweloperuch.pl/ceny-transakcyjne/polska/miasta`) and items with `city_slug`, e.g. `{"name": "Warszawa", "city_slug": "warszawa", "transaction_count": 3606, "price_per_m2": 16413.0, "area_m2": 48.8, "price": 780000.0}` (`tests/golden/mcp/rank_cities.json`).

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/rank_locations_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/rank_locations_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/rank_locations.py`, `tests/snapshots/mcp_tools.json`_
