# `rank_locations`
> Porównanie wielu miejsc w jednym okresie; nie zwraca szeregu czasowego. Dwa tryby: (1) bez indicator: ranking miejscowości (level=city) albo powiatów (level=powiat) wg transakcji z RCN (liczba, cena za m²); (2) z indicator: ranking 66 miast na prawach powiatu wg wskaźnika GUS lub NBP. Trend jednego miasta w czasie: get_transaction_statistics (RCN) albo get_government_statistics (GUS, NBP). Bez indicator to ceny transakcyjne z RCN, nie ofertowe; nbp_price_per_m2 to oficjalna cena NBP, nie RCN.
>
> Zwraca total, returned, truncated, hint i items. Transakcje: min_transactions (zastosowany próg), items (name, city_slug albo powiat_id, transaction_count, price_per_m2, area_m2, price); dla city ranking_url (link dla użytkownika); dla powiat market i okres 12 miesięcy period_start–period_end. Wskaźnik: indicator, unit, period, items (name, city_slug, value, stats_url: link dla użytkownika).
>
> Ograniczenia: serwis nie mówi, czy ceny i metraż to średnie, czy mediany. Okresu miejscowości serwis nie podaje; nie porównuj liczb transakcji miejscowości i powiatów. Sortowanie po cenie domyślnie pomija miejsca poniżej 20 transakcji (cena bywa przypadkowa); min_transactions=0 pokazuje wszystkie.

Title: „Ranking miast i powiatów”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

Two modes. Without `indicator` the tool ranks places (`level=city`) or powiats (`level=powiat`) by RCN transactions. With `indicator` it ranks the 66 cities with powiat rights by a GUS or NBP indicator; that mode is cities only.

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `level` | `city` \| `powiat` | no | `city` | „city: miejscowości (miasta, także małe miasteczka i wsie), domyślnie; powiat: powiaty, tylko transakcje (market); powiaty nie mają city_slug ani ranking_url i nie ma ich w search_locations. Z indicator tylko city.” |
| `sort` | `transactions_desc` \| `price_per_m2_desc` \| `price_per_m2_asc` \| `value_desc` \| `value_asc` | no | `transactions_desc`; with `indicator` `value_desc` | „transactions_desc: najwięcej transakcji (domyślnie bez indicator); price_per_m2_desc, price_per_m2_asc: najwyższa, najniższa cena za m² (miejsca bez ceny na końcu); value_desc (domyślnie z indicator), value_asc: najwyższa, najniższa wartość wskaźnika, tylko z indicator.” |
| `limit` | integer 1-100 | no | `20` | „Ile pierwszych pozycji rankingu zwrócić, 1–100, domyślnie 20. Pozycja to ok. 120 znaków wyniku. Dla pełnych list zawężaj min_transactions, nie podnoś limitu bez potrzeby.” |
| `min_transactions` | integer 0-10 000 000 or null | no | null (the default threshold) | „Brak = próg domyślny: 20 przy sortowaniu po cenie, 0 przy transactions_desc. 0 = wszystkie miejsca. Pomija miejsca z mniejszą liczbą transakcji; np. 50 daje stabilniejsze ceny. Nie działa z indicator.” |
| `market` | `secondary` \| `primary` \| `all` or null | no | null (`secondary`) | „Tylko level=powiat. secondary: rynek wtórny (domyślnie); primary: pierwotny; all: oba rynki w zestawieniu serwisu (jego liczba transakcji nie zawsze równa się secondary + primary). Powiaty bez danych dla rynku są pominięte (hint).” |
| `indicator` | `unemployment_rate` \| `average_wage` \| `dwellings_completed` \| `dwellings_started` \| `average_dwelling_area` \| `natural_increase` \| `nbp_price_per_m2` or null | no | null (a transaction ranking) | „Ranking 66 miast na prawach powiatu według wskaźnika zamiast transakcji (bez level=powiat, min_transactions i market): unemployment_rate: stopa bezrobocia rejestrowanego (%) w miesiącu; average_wage: przeciętne miesięczne wynagrodzenie brutto (PLN), średnia za rok period (jak dataset=wages w get_government_statistics); dwellings_completed, dwellings_started: mieszkania oddane, rozpoczęte w 12 miesiącach do miesiąca period; average_dwelling_area: powierzchnia mieszkania (m²) podana przez serwis za okres period; nie porównuj jej z average_area z get_government_statistics (inna definicja); natural_increase: przyrost naturalny (osoby) w roku; nbp_price_per_m2: cena transakcyjna rynku wtórnego wg NBP (PLN/m²) w kwartale, tylko 17 miast. Miasta bez wartości są pominięte (hint).” |

All parameters are optional. When `min_transactions` is not given (or `null`), the threshold is 20 for both price sorts (`price_per_m2_desc`, `price_per_m2_asc`; both levels) and 0 for `transactions_desc`. An explicit value, including 0, always wins. `market` not given is `secondary`. Blank text for `level`, `sort`, `market` and `indicator` means the default ([argument rules](../README.md#argument-rules)).

Combinations the tool refuses before any request: `indicator` with `level=powiat`, `min_transactions`, `market` or a sort other than `value_desc` / `value_asc`; `value_desc` / `value_asc` without `indicator`; `market` without `level=powiat` (see Errors).

The indicators, all for the 66 cities with powiat rights (`unit` and `period` are in the result):

| `indicator` | `unit` | Value |
|---|---|---|
| `unemployment_rate` | `%` | Registered unemployment rate in the month `period` (`RRRR-MM`). |
| `average_wage` | `PLN/mies.` | Average monthly gross wage, the average for the year `period` (`RRRR`); the same as `dataset=wages` of [`get_government_statistics`](get_government_statistics.md). |
| `dwellings_completed`, `dwellings_started` | `mieszkania (suma 12 miesięcy)` | Dwellings completed / started: the sum of the 12 months up to the month `period`. |
| `average_dwelling_area` | `m²` | Dwelling area as the service gives it for `period`; do not compare it with `average_area` of `get_government_statistics` (another definition). |
| `natural_increase` | `osoby` | Natural increase in the year `period`. |
| `nbp_price_per_m2` | `PLN/m²` | NBP transaction price of the secondary market in the quarter `period` (`RRRR-Qn`); 17 cities only. |

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Description |
|---|---|
| `level`, `sort` | The query as applied (with `indicator`, `level` is `city`). Required. |
| `min_transactions` | Transaction rankings: the threshold applied (the argument, or the default: 20 for a price sort, 0 for `transactions_desc`). Absent with `indicator`. |
| `market` | `level=powiat`: `secondary`, `primary` or `all` as applied. |
| `period_start`, `period_end` | `level=powiat`: the 12-month window of the powiat figures, `RRRR-MM-01` and the last month included, `RRRR-MM` (e.g. `2025-11-01` and `2026-10`). |
| `indicator`, `unit`, `period` | Indicator rankings: the indicator, its unit and its period (a month `RRRR-MM`, a quarter `RRRR-Qn` or a year `RRRR`; for `dwellings_completed` and `dwellings_started` the last month of the 12-month window). |
| `total` | Places that meet the criteria: with at least `min_transactions` transactions, with figures for `market`, or with a value of the indicator. |
| `returned`, `truncated`, `hint` | Items returned; `true` when more exist (the hint says how to see them). The `hint` also says what was left out: places under the default threshold of a price sort (only when it actually left places out), powiats without figures for the market, cities without the indicator. |
| `ranking_url` | The ranking page on deweloperuch.pl (`level=city` without `indicator` only): give it to the user as a link. |
| `items` | Transactions: `name`, `city_slug` (cities) or `powiat_id` (powiats; informational, no tool accepts it), `transaction_count`, `price_per_m2`, `area_m2`, `price`. Indicator: `name`, `city_slug`, `value`, `stats_url` (the city's page of government statistics on deweloperuch.pl, with the section of the indicator: give it to the user as a link). |

**BREAKING (0.2.0):** the output schema requires only `level`, `sort`, `total`, `returned`, `truncated` and `items` (and `name` in an item). `min_transactions` and `items[].transaction_count` are no longer required, because an indicator ranking has neither; a transaction ranking still always emits both. A consumer that validated the strict schema and relied on them must accept their absence.

Names of cities and powiats come from a table packaged in the wheel (D19), not from a request; a powiat missing from it is shown by its id, a city by its slug ([configuration](../../configuration.md#files)).

## Data limitations
- The service gives no period and does not say whether prices and areas are averages or medians: present them as values given by the service.
- Powiat figures cover the 12 months `period_start`–`period_end` (`statystyki/powiat-map-stats`); the service does not give the period of the city ranking, so powiat and city transaction counts must not be compared. Whether the prices of either are means or medians is open (T10, T85). `market=all` is the service's own figure for both markets, not the sum of the other two (equal in 80 of 303 powiats, T86). Powiats without figures for the chosen market are left out and counted in the `hint`.
- A price or area of 0 from the service means no value: the place sorts last on price and has no `price_per_m2` / `area_m2` / `price` fields (CLI text `?`, `--json` `null`). Example: Ignatki-osiedle, which the service lists with 0 and which used to rank as the cheapest [P 2026-10-15].
- Sorting by price with few transactions favours random prices; that is why the default threshold is 20 (`min_transactions=0` shows everything). Sources: [endpoints.md](../../discovery/endpoints.md) (`city-transaction-stats`), [open-questions.md](../../open-questions.md).
- Indicator rankings: every value equals the series of the same city in [`get_government_statistics`](get_government_statistics.md) for its period (unemployment of the month, wages and natural increase of the year, the NBP price of the quarter) or the sum of its 12 months (dwellings); the dwelling area matches no series of that tool, so present it as given by the service. Only the 66 cities with powiat rights are ranked; cities without a value are left out (`nbp_price_per_m2` has 17 of them, the `hint` says how many were left out). Source: [endpoints.md](../../discovery/endpoints.md) (`statystyki/gov-map-stats`).
- The routes behind the powiat level and the indicators (`statystyki/powiat-map-stats`, `statystyki/gov-map-stats`) are cached in the process for up to 24 h (D19, [configuration](../../configuration.md#package-client)), so a repeated ranking in the same process costs no request.
- Size: about 120 characters per item (20 items about 2 900 with the hint, `tests/golden/mcp/rank_cities_price_asc_default_threshold.json`).

## Errors
| Situation | Message |
|---|---|
| `level`, `sort`, `market`, `indicator` outside the list | `Błędny argument narzędzia rank_locations: level musi być jedną z wartości city, powiat, podano "gmina". Popraw i ponów; nic nie zostało wysłane.` |
| `limit` outside 1-100 | `Błędny argument narzędzia rank_locations: limit musi być liczbą całkowitą z zakresu 1–100, podano 101. Popraw i ponów; nic nie zostało wysłane.` |
| `min_transactions` outside 0-10 000 000 | `Błędny argument narzędzia rank_locations: min_transactions musi być liczbą całkowitą z zakresu 0–10000000 albo pusty, podano -1. Popraw i ponów; nic nie zostało wysłane.` |
| Unknown argument | `Nieznany argument narzędzia rank_locations: '…'. Dozwolone argumenty: level, sort, limit, min_transactions, market, indicator. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| `indicator` with `level=powiat` | `indicator działa tylko z level=city: wskaźniki GUS/NBP są tylko dla 66 miast na prawach powiatu, a dla powiatów są tylko transakcje (market). Pomiń level, aby dostać ranking miast według wskaźnika, albo pomiń indicator, aby dostać ranking powiatów według transakcji.` |
| `indicator` with `min_transactions` | `min_transactions nie działa z indicator: ranking wskaźnika nie liczy transakcji; pomiń min_transactions.` |
| `indicator` with `market` | `market nie działa z indicator: rynek dotyczy transakcji powiatów; pomiń market.` |
| `indicator` with a transaction sort | `Z indicator sort przyjmuje value_desc (najwyższa wartość, domyślnie) albo value_asc (najniższa); pomiń sort albo podaj jedną z nich.` |
| `value_desc` / `value_asc` without `indicator` | `sort value_desc i value_asc działa tylko z indicator; podaj indicator albo sort transactions_desc, price_per_m2_desc lub price_per_m2_asc.` |
| `market` without `level=powiat` | `market działa tylko z level=powiat: ranking miejscowości nie dzieli transakcji na rynki; pomiń market albo podaj level=powiat.` |
| STOP, other service error | As in the [MCP overview](../README.md#errors); a service error: `Ranking miejscowości: Serwis odpowiedział błędem HTTP 500. Nic nie ponawiam; spróbuj później.` |

## Example
Call:

```json
{"name": "rank_locations", "arguments": {"level": "powiat"}}
```

The result from `tests/golden/mcp/rank_powiats.json` (three real rows of the capture `tests/fixtures/api/powiat_map_stats_20261102.json`; `market` not given is `secondary`; the window is 12 months):

```json
{
  "level": "powiat", "sort": "transactions_desc", "min_transactions": 0,
  "market": "secondary", "period_start": "2025-11-01", "period_end": "2026-10",
  "total": 3, "returned": 3, "truncated": false,
  "items": [
    {"name": "powiat piaseczyński", "powiat_id": 3, "transaction_count": 1067, "price_per_m2": 12164.0, "area_m2": 56.6, "price": 675000.0},
    {"name": "powiat ropczycko-sędziszowski", "powiat_id": 1, "transaction_count": 21, "price_per_m2": 6829.0, "area_m2": 55.9, "price": 390000.0},
    {"name": "powiat łosicki", "powiat_id": 2, "transaction_count": 5, "price_per_m2": 7246.0, "area_m2": 57.2, "price": 400000.0}
  ]
}
```

`{"level": "powiat", "market": "primary"}` ranks the primary market; powiats without figures for it are left out and the hint says how many (`tests/golden/mcp/rank_powiats_primary_captured.json`: 70 left out, 310 ranked).

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

An indicator ranking, call `{"indicator": "average_wage"}` (`tests/golden/mcp/rank_indicator_average_wage.json`, three cities of the capture `tests/fixtures/api/gov_map_stats_20261102.json`):

```json
{
  "level": "city", "sort": "value_desc", "indicator": "average_wage", "unit": "PLN/mies.", "period": "2025",
  "total": 3, "returned": 3, "truncated": false,
  "items": [
    {"name": "Warszawa", "city_slug": "warszawa", "value": 11677.57, "stats_url": "https://deweloperuch.pl/statystyki/warszawa/dane-rzadowe#gus-wynagrodzenia"},
    {"name": "Bydgoszcz", "city_slug": "bydgoszcz", "value": 9207.5, "stats_url": "https://deweloperuch.pl/statystyki/bydgoszcz/dane-rzadowe#gus-wynagrodzenia"},
    {"name": "Białystok", "city_slug": "bialystok", "value": 9084.99, "stats_url": "https://deweloperuch.pl/statystyki/bialystok/dane-rzadowe#gus-wynagrodzenia"}
  ]
}
```

With `{"indicator": "nbp_price_per_m2", "limit": 5}` the hint says: „Pominięto miasta, dla których serwis nie podaje tego wskaźnika: 49 z 66. Pokazano pierwsze 5 z 17 miast; kolejne pokaże większy limit (najwyżej 100).” (`tests/golden/mcp/rank_indicator_nbp_captured.json`).

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/rank_locations_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/rank_locations_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/rank_locations.py`, `tests/snapshots/mcp_tools.json`_
