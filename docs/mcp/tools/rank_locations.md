# `rank_locations`
> Ranking miejscowości (level=city) albo powiatów (level=powiat) w Polsce według transakcji z Rejestru Cen Nieruchomości (RCN): liczba transakcji i cena transakcyjna za m². Dla porównania wielu miast: to narzędzie; dla trendu jednego miasta w czasie: get_transaction_statistics. To ceny transakcyjne, nie ofertowe; oferty deweloperów daje search_offers.
>
> Zwraca min_transactions (zastosowany próg), total (miejsca z co najmniej tyloma transakcjami), returned, truncated, hint i items (name, city_slug albo powiat_id, transaction_count, price_per_m2, area_m2, price); dla city także ranking_url (strona rankingu na deweloperuch.pl: podaj ją użytkownikowi jako link). powiat_id jest informacyjny: żadne narzędzie go nie przyjmuje.
>
> Ograniczenia: serwis nie podaje okresu ani tego, czy ceny i metraż to średnie, czy mediany: przedstawiaj je jako wartości podane przez serwis. Liczby transakcji powiatów obejmują wiele lat: służą tylko do uporządkowania, nie są bieżącym wolumenem; nie porównuj ich z liczbami miejscowości. Sortowanie po cenie domyślnie pomija miejsca poniżej 20 transakcji (cena bywa przypadkowa); min_transactions=0 pokazuje wszystkie, np. 50 daje stabilniejsze ceny.

Title: „Ranking miast i powiatów”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `level` | `city` \| `powiat` | no | `city` | „city: miejscowości (miasta, także małe miasteczka i wsie), domyślnie; powiat: powiaty (bez ranking_url i bez odpowiednika w search_locations).” |
| `sort` | `transactions_desc` \| `price_per_m2_desc` \| `price_per_m2_asc` | no | `transactions_desc` | „transactions_desc: najwięcej transakcji (domyślnie); price_per_m2_desc: najwyższa cena za m²; price_per_m2_asc: najniższa cena za m². Miejsca bez ceny są na końcu.” |
| `limit` | integer 1-100 | no | `20` | „Ile pierwszych pozycji rankingu zwrócić, 1–100, domyślnie 20. Pozycja to ok. 120 znaków wyniku. Dla pełnych list zawężaj min_transactions, nie podnoś limitu bez potrzeby.” |
| `min_transactions` | integer 0-10 000 000 or null | no | null (the default threshold) | „Brak = próg domyślny: 20 przy sortowaniu po cenie, 0 przy transactions_desc. 0 = wszystkie miejsca. Pomija miejsca z mniejszą liczbą transakcji; np. 50 daje stabilniejsze ceny.” |

All parameters are optional. When `min_transactions` is not given (or `null`), the threshold is 20 for both price sorts (`price_per_m2_desc`, `price_per_m2_asc`; both levels) and 0 for `transactions_desc`. An explicit value, including 0, always wins. **Behaviour change (BREAKING) in this version:** a price sort used to include every place by default. Blank text for `level` and `sort` means the default ([argument rules](../README.md#argument-rules)).

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Description |
|---|---|
| `level`, `sort` | The query as applied. |
| `min_transactions` | The threshold applied (the argument, or the default: 20 for a price sort, 0 for `transactions_desc`). |
| `total` | Places with at least `min_transactions` transactions. |
| `returned`, `truncated`, `hint` | Items returned; `true` when more exist (the hint says how to see them). The `hint` also has a sentence about the default threshold, but only when it actually left places out of a price sort. |
| `ranking_url` | The ranking page on deweloperuch.pl (`level=city` only): give it to the user as a link. |
| `items` | `name`, `city_slug` (cities) or `powiat_id` (powiats; informational, no tool accepts it), `transaction_count`, `price_per_m2`, `area_m2`, `price`. |

## Data limitations
- The service gives no period and does not say whether prices and areas are averages or medians: present them as values given by the service.
- Powiat transaction counts cover many years: they only order the list, are not the current volume and must not be compared with city counts.
- A price or area of 0 from the service means no value: the place sorts last on price and has no `price_per_m2` / `area_m2` / `price` fields (CLI text `?`, `--json` `null`). Example: Ignatki-osiedle, which the service lists with 0 and which used to rank as the cheapest [P 2026-10-15].
- Sorting by price with few transactions favours random prices; that is why the default threshold is 20 (`min_transactions=0` shows everything). Sources: [endpoints.md](../../discovery/endpoints.md) (`city-transaction-stats`), [open-questions.md](../../open-questions.md).
- Size: about 120 characters per item (20 items about 2 700).

## Errors
| Situation | Message |
|---|---|
| `level`, `sort` outside the list | `Błędny argument narzędzia rank_locations: level musi być jedną z wartości city, powiat, podano "gmina". Popraw i ponów; nic nie zostało wysłane.` |
| `limit` outside 1-100 | `Błędny argument narzędzia rank_locations: limit musi być liczbą całkowitą z zakresu 1–100, podano 101. Popraw i ponów; nic nie zostało wysłane.` |
| `min_transactions` outside 0-10 000 000 | `Błędny argument narzędzia rank_locations: min_transactions musi być liczbą całkowitą z zakresu 0–10000000 albo pusty, podano -1. Popraw i ponów; nic nie zostało wysłane.` |
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

The default threshold, call `{"sort": "price_per_m2_asc"}` (`tests/golden/mcp/rank_cities_price_asc_default_threshold.json`, abridged to the first two of 20 items):

```json
{
  "level": "city", "sort": "price_per_m2_asc", "min_transactions": 20,
  "total": 258, "returned": 20, "truncated": true,
  "hint": "Przy sortowaniu po cenie pominięto miejsca z mniej niż 20 transakcjami (domyślny próg); wszystkie miejsca pokaże min_transactions=0. Pokazano pierwsze 20 z 258 miejscowości; kolejne pokaże większy limit (najwyżej 100).",
  "ranking_url": "https://deweloperuch.pl/ceny-transakcyjne/polska/miasta",
  "items": [
    {"name": "Kamienna Góra", "city_slug": "kamienna-gora", "transaction_count": 37, "price_per_m2": 3394.0, "area_m2": 46.6, "price": 150000.0},
    {"name": "Boguszów-gorce", "city_slug": "boguszow-gorce", "transaction_count": 32, "price_per_m2": 3524.0, "area_m2": 43.1, "price": 132500.0}
  ]
}
```

With `"min_transactions": 0` the output echoes `"min_transactions": 0` and the cheapest places are one-transaction ones (Miejsce Piastowe, 260.0 PLN/m², `tests/golden/mcp/rank_cities_price_asc_min_transactions_0.json`).

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/rank_locations_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/rank_locations_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/rank_locations.py`, `tests/snapshots/mcp_tools.json`_
