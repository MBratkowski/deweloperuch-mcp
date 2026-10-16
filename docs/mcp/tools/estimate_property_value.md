# `estimate_property_value`
> Szacuje wartość mieszkania o danym metrażu w punkcie (lat, lng) w Polsce na podstawie cen transakcyjnych z Rejestru Cen Nieruchomości (RCN) z okolicy. Wynik jest przybliżony: to porównanie z transakcjami w pobliżu, a nie operat szacunkowy. Użyj, gdy użytkownik pyta, ile może być warte mieszkanie albo czy jego cena jest rynkowa.
>
> Zwraca estimated_value (PLN), price_per_m2, radius_m i period_months (skąd i z ilu miesięcy są transakcje), stats (liczba, mediana, średnia, min i max ceny za m²) oraz comparables: najbliższe transakcje porównawcze (adres, data, cena, metraż, cena za m², piętro, odległość, rynek), z comparables_total, comparables_omitted, truncated i hint. estimated_value=null znaczy, że serwis nie podał wyceny: przeczytaj hint.
>
> Wymaga współrzędnych: narzędzie nie zamienia adresu na lat i lng. Weź je od użytkownika, z search_locations (ulica lub dzielnica: to punkt przybliżony, nie konkretny budynek) albo z get_investment (współrzędne inwestycji oferty). Każde wywołanie to zapytanie do serwisu: nie wyceniaj seriami wielu punktów.

Title: „Wycena mieszkania”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `lat` | number 49.0-54.9 | yes | — | „Szerokość geograficzna punktu w Polsce w stopniach, np. 52.2297: pole lat z search_locations (ulica albo dzielnica, nie samo miasto) albo ze współrzędnych inwestycji w get_investment (dokładniejsze dla konkretnej oferty).” |
| `lng` | number 14.1-24.2 | yes | — | „Długość geograficzna punktu w Polsce w stopniach, np. 21.0122: pole lng z search_locations (ulica albo dzielnica, nie samo miasto) albo ze współrzędnych inwestycji w get_investment (dokładniejsze dla konkretnej oferty).” |
| `area_m2` | number 10-500 | yes | — | „Metraż mieszkania w m², 10–500, np. 48.5.” |
| `address` | string, 3-200 characters | no | none | „Opcjonalny opis adresu, np. Marszałkowska 100, Warszawa. Trafia do serwisu, ale nie wyznacza położenia: decydują lat i lng.” Blank text means "none". |
| `limit` | integer 0-50 | no | `10` | „Ile najbliższych transakcji porównawczych zwrócić, 0–50, domyślnie 10. Transakcja to ok. 210 znaków wyniku (50 to ok. 10,6 tys.); 0 = tylko wycena i statystyki.” |

Numbers may also be text with a decimal point (`"52.2297"`); a decimal comma (`"52,2297"`) and booleans are rejected ([argument rules](../README.md#argument-rules)).

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted, except `estimated_value`.

| Field | Description |
|---|---|
| `lat`, `lng`, `area_m2` | The query; `area_m2` is the requested area, rounded to 0.01 m². The service does not confirm the area it actually used. |
| `estimated_value` (PLN), `price_per_m2` | The estimate as returned by the service, without recomputing the total locally; `estimated_value=null` means the service gave none (read `hint`). |
| `radius_m`, `period_months` | The radius and the number of months the comparable transactions come from (e.g. 200 m, 24 months). |
| `stats` | `count`, `median_price_per_m2`, `average_price_per_m2`, `min_price_per_m2`, `max_price_per_m2` as given by the service. |
| `comparables_total`, `comparables_returned`, `comparables_omitted`, `truncated` | How many comparable transactions exist and were returned. |
| `hint` | Valuation cautions and guidance about omitted comparables or a missing estimate. |
| `comparables` | The nearest transactions: `address`, `date`, `price`, `area_m2`, `price_per_m2`, `floor`, `distance_m`, `market` (`primary` or `secondary`), `building_slug` (for `get_building`). |

## Data limitations
- An approximation from nearby RCN transactions, not an appraisal. The service rounds distances (to the nearest 50 m, verified 2026-10-13); the newest transactions are incomplete (register lag).
- Fractional requested areas carry the caution „Serwis może nie uwzględnić części ułamkowej powierzchni w wycenie.” in `hint`, including when `limit` omits comparables. A check on 2026-10-16 returned the same total for 41.37 m² and 41 m² at one point; the general rounding or truncation rule remains unknown ([T41](../../open-questions.md#technical)). Do not assume `estimated_value` equals `price_per_m2 × area_m2`.
- The full pool of transactions in the radius (`radiusPool`) is a bulk dump and is deliberately never returned ([decisions.md](../../decisions.md)); only `comparables` limited by `limit` do.
- The tool does not geocode an address: coordinates come from the user, `search_locations` (street or district: an approximate point) or `get_investment`.
- Every call is a request to the service; do not value many points in a series. Sources: [endpoints.md](../../discovery/endpoints.md), [open-questions.md](../../open-questions.md).

## Errors
| Situation | Message |
|---|---|
| The service gives no estimate (HTTP 404) | `Serwis nie podał wyceny dla tego miejsca; w promieniu może nie być transakcji.` |
| `lat`/`lng` outside Poland, a comma, a boolean | `Błędny argument narzędzia estimate_property_value: lat musi być liczbą z zakresu 49–54.9 (z kropką dziesiętną), podano 60. Popraw i ponów; nic nie zostało wysłane.` |
| `area_m2` outside 10-500 | `Błędny argument narzędzia estimate_property_value: area_m2 musi być liczbą z zakresu 10–500 (z kropką dziesiętną), podano 5. Popraw i ponów; nic nie zostało wysłane.` |
| `address` shorter than 3 characters | `address: podaj od 3 do 200 znaków adresu albo pomiń ten parametr, podano 'ab'.` |
| A required argument is missing | `Błędny argument narzędzia estimate_property_value: lat: brak wymaganego argumentu. Popraw i ponów; nic nie zostało wysłane.` |
| `limit` outside 0-50 | `Błędny argument narzędzia estimate_property_value: limit musi być liczbą całkowitą z zakresu 0–50, podano 51. Popraw i ponów; nic nie zostało wysłane.` |
| Unknown argument | `Nieznany argument narzędzia estimate_property_value: '…'. Dozwolone argumenty: lat, lng, area_m2, address, limit. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| STOP, service error | As in the [MCP overview](../README.md#errors); a service error: `Wycena mieszkania: Serwis odpowiedział błędem HTTP 500. Nic nie ponawiam; spróbuj później.` |

A response without an estimate that is not a 404 is a result with `estimated_value=null` and a `hint` (`tests/golden/mcp/valuation_without_an_estimate.json`).

## Example
Call:

```json
{"name": "estimate_property_value", "arguments": {"lat": 52.2297, "lng": 21.0122, "area_m2": 50}}
```

The result from `tests/golden/mcp/valuation.json` (a mocked service answer):

```json
{
  "lat": 52.2297, "lng": 21.0122, "area_m2": 50.0,
  "estimated_value": 1063300.0, "price_per_m2": 21266.0, "radius_m": 200, "period_months": 24,
  "stats": {"count": 9, "median_price_per_m2": 23830.0, "average_price_per_m2": 22195.0, "min_price_per_m2": 13187.0, "max_price_per_m2": 31492.0},
  "comparables_total": 3, "comparables_returned": 3, "comparables_omitted": 0, "truncated": false,
  "comparables": [
    {"address": "Ulica Nowogrodzka 38", "date": "2025-04-17", "price": 765002.0, "area_m2": 43.57, "price_per_m2": 17558.0, "floor": 6, "distance_m": 150.0, "market": "secondary", "building_slug": "ulica-nowogrodzka-38-warszawa"},
    {"address": "Ulica Widok 24", "date": "2025-05-27", "price": 977507.0, "area_m2": 41.02, "price_per_m2": 23830.0, "floor": 6, "distance_m": 150.0, "market": "secondary", "building_slug": "ulica-widok-24-warszawa"}
  ]
}
```

(The third comparable is omitted here.)

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/estimate_property_value_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/estimate_property_value_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/estimate_property_value.py`, `tests/snapshots/mcp_tools.json`_
