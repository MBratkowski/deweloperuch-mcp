# `get_building`
> Zwraca budynek z rejestru cen transakcyjnych (RCN): adres, współrzędne, średnie ceny podane przez serwis i lokale z transakcjami: datą, ceną, ceną za m², rynkiem, rodzajem i stronami. To ceny, za które lokale sprzedano, nie ceny ofertowe deweloperów. building_slug to ostatni człon adresu strony budynku z cenami transakcyjnymi na deweloperuch.pl, np. 23-marca-79c-sopot; gdy go nie znasz, poproś użytkownika o link do tej strony. building_url to ta strona: podaj ją jako link. Kolejność: lokale od tego z najnowszą transakcją, transakcje każdego lokalu od najstarszej. Transakcji o classification innym niż regular (udział, egzekucja, bonifikata…) nie uśredniaj ze zwykłymi: to nie zwykła sprzedaż po cenie rynkowej; liczy je non_regular_transactions.
>
> Ograniczenia: tylko budynki z mieszkaniami, nie domy. Zwraca najwyżej limit lokali (domyślnie 10); truncated i units_omitted mówią, czy i ile pominięto; units_total i transactions_total liczą cały budynek. Najnowsze miesiące bywają niepełne (rejestr spływa z opóźnieniem). include_trend=true dodaje średnią cenę za m² transakcji w okolicy budynku (promień radius_km) w ostatnich 12 kwartałach; to jedno zapytanie do serwisu więcej.

Title: „Budynek z transakcjami”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `building_slug` | string | yes | — | „Slug budynku, np. 23-marca-79c-sopot, ze strony budynku albo z comparables w estimate_property_value.” Lowercase letters without Polish characters, digits and hyphens. |
| `limit` | integer 0-50 | no | `10` | „Najwięcej lokali w wyniku (tych z najnowszymi transakcjami), domyślnie 10, najwyżej 50; 0 = tylko podsumowanie budynku. Ile pominięto, mówi units_omitted. Wynik ma ok. 200 znaków na transakcję; lokal może mieć kilka transakcji, więc zwykle wystarcza domyślny limit.” |
| `include_trend` | boolean | no | `false` | „true: dołącz średnią cenę za m² transakcji w okolicy budynku w ostatnich 12 kwartałach (jedno zapytanie więcej).” |

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Description |
|---|---|
| `building_slug`, `name`, `building_url`, `city`, `city_slug`, `street`, `lat`, `lng` | The building and its page on deweloperuch.pl (give `building_url` to the user as a link). `name` is the address from the price register and is **optional**: absent when the register gives none (the place is then in `city`). **BREAKING** for consumers of the strict output schema: `name` used to be required. `street` only when it differs from `name`. |
| `avg_price`, `avg_area_m2`, `avg_price_per_m2` | Averages as given by the service; a value of 0 or less is no value and is omitted. |
| `first_transaction_date`, `last_transaction_date` | The range of transactions of the whole building. |
| `units_total`, `transactions_total` | The whole building. |
| `non_regular_transactions` | Counts of the whole building's transactions by `classification` other than `regular`, e.g. `{"share": 1}`; omitted when there are none. Do not average them with regular sales. The service's `avg_*` probably do not include them (checked in one building, T48). |
| `units` | Units, the one with the newest transaction first: `floor`, `rooms` (both absent when the register's text is blank; used to be 0), `area_m2` and `transactions` (oldest first): `date`, `price`, `price_per_m2`, `currency` (absent = PLN), `market` (`primary` or `secondary`), `classification` (`regular`, `share`, `bulk`, `government`, `enforcement`, `discount`, `anomaly_low`, `anomaly_high`), `buyer`, `seller` (`natural_person`, `legal_person`), `share` (only when a share was sold). |
| `hint` | What to do next or what is missing, e.g. an empty neighbourhood trend. |
| `units_returned`, `units_omitted`, `truncated` | How many units were returned and cut by `limit`. |
| `neighbourhood_trend` | Only with `include_trend=true`: `radius_km`, `total`, `returned`, `truncated` and `quarters` (`period`, `avg_price_per_m2`, `transactions`). A quarter's price and a radius of 0 or less are no value and are omitted. |

## Data limitations
- Transaction prices from the RCN, not asking prices; buildings with apartments only (no houses). The newest months are incomplete (register lag). Sources: [endpoints.md](../../discovery/endpoints.md), [open-questions.md](../../open-questions.md).
- The service gives no way to find a building by address: the slug comes from the building's page, from `comparables` of `estimate_property_value`, or from the user.
- `include_trend=true` is one more request to the service.
- `non_regular_transactions` and the `avg_*`: the service's averages probably do not include shares, enforcement and similar sales (checked in one building, T48 in [open-questions.md](../../open-questions.md)); this is not confirmed for other buildings.
- Buyers and sellers appear only as a type (`natural_person`, `legal_person`), without names. The MCP units carry no register identifier (the CLI text shows one per unit).

## Errors
| Situation | Message |
|---|---|
| The building does not exist | `Nie znaleziono budynku '23-marca-79c-sopot'. Slug budynku to ostatni człon adresu jego strony z cenami transakcyjnymi na deweloperuch.pl, np. 23-marca-79c-sopot albo aleja-krakowska-279-warszawa.` |
| `building_slug` not a slug | `building_slug: oczekiwano slug budynku: małe litery bez polskich znaków, cyfry i myślniki, np. 23-marca-79c-sopot; podano '23-Marca-79C-Sopot'.` |
| `limit` outside 0-50 | `Błędny argument narzędzia get_building: limit musi być liczbą całkowitą z zakresu 0–50, podano 51. Popraw i ponów; nic nie zostało wysłane.` |
| The trend request fails | `Trend cen w okolicy budynku '23-marca-79c-sopot': Serwis odpowiedział błędem HTTP 500. Nic nie ponawiam; spróbuj później.` |
| Unknown argument | `Nieznany argument narzędzia get_building: '…'. Dozwolone argumenty: building_slug, limit, include_trend. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| STOP, service error | As in the [MCP overview](../README.md#errors); service errors with the prefix `Budynek '<slug>': …` |

## Example
Call:

```json
{"name": "get_building", "arguments": {"building_slug": "23-marca-79c-sopot"}}
```

The result from `tests/golden/mcp/building.json` (the real fixture; the first of 3 units shown):

```json
{
  "building_slug": "23-marca-79c-sopot", "name": "23 Marca 79C",
  "building_url": "https://deweloperuch.pl/ceny-transakcyjne/sopot/adresy/23-marca-79c-sopot",
  "city": "Sopot", "city_slug": "sopot", "lat": 54.44705851, "lng": 18.54342128,
  "avg_price": 1324114.66, "avg_area_m2": 61.6, "avg_price_per_m2": 21494.72,
  "first_transaction_date": "2025-09-12", "last_transaction_date": "2025-11-17",
  "units_total": 3, "transactions_total": 3,
  "units": [
    {"floor": 1, "rooms": 5, "area_m2": 122.01, "transactions": [{"date": "2025-11-17", "price": 1900000.47, "price_per_m2": 15572.5, "market": "primary", "classification": "regular", "buyer": "natural_person", "seller": "legal_person"}]}
  ],
  "units_returned": 3, "units_omitted": 0, "truncated": false
}
```

With `include_trend=true` the result adds `"neighbourhood_trend": {"radius_km": 1.0, "total": 3, "returned": 3, "truncated": false, "quarters": [{"period": "2006-Q2", "avg_price_per_m2": 5706.0, "transactions": 25}, …]}` (`tests/golden/mcp/building_trend.json`).

A building without a name, with non-regular transactions and an empty trend, call `{"building_slug": "cisna", "include_trend": true}` (`tests/golden/mcp/building_cisna_trend.json`, a mocked answer based on the Cisna sample; two of 6 units left out): no `name`, `floor` absent for units the register gives none for.

```json
{
  "building_slug": "cisna",
  "building_url": "https://deweloperuch.pl/ceny-transakcyjne/cisna/adresy/cisna",
  "city": "Cisna", "city_slug": "cisna", "lat": 49.21459191, "lng": 22.3219767,
  "avg_price": 274600.0, "avg_area_m2": 72.08, "avg_price_per_m2": 3809.76,
  "first_transaction_date": "2022-02-01", "last_transaction_date": "2026-03-19",
  "units_total": 6, "transactions_total": 7,
  "non_regular_transactions": {"enforcement": 1, "share": 1},
  "units": [
    {"rooms": 7, "area_m2": 62.31, "transactions": [{"date": "2026-03-19", "price": 360000.0, "price_per_m2": 5777.56, "market": "secondary", "classification": "regular", "buyer": "natural_person", "seller": "natural_person"}]},
    {"floor": 2, "rooms": 4, "area_m2": 62.68, "transactions": [{"date": "2023-05-08", "price": 95000.0, "price_per_m2": 1276.2, "market": "secondary", "classification": "share", "buyer": "natural_person", "seller": "natural_person", "share": "1/2"}, {"date": "2024-06-12", "price": 280000.0, "price_per_m2": 4467.13, "market": "secondary", "classification": "regular", "buyer": "natural_person", "seller": "natural_person"}]}
  ],
  "units_returned": 6, "units_omitted": 0, "truncated": false,
  "hint": "Serwis nie ma kwartałów trendu cen w okolicy tego budynku; to nie błąd i ponowienie nic nie zmieni. Szersze tło może dać get_transaction_statistics dla city_slug budynku (małe miejscowości mogą nie mieć tych statystyk).",
  "neighbourhood_trend": {"total": 0, "returned": 0, "truncated": false, "quarters": []}
}
```

(Abridged: the golden lists all 6 units, as `units_returned` says.)

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_building_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_building_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_building.py`, `tests/snapshots/mcp_tools.json`_
