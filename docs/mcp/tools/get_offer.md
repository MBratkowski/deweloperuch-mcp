# `get_offer`
> Zwraca jedną ofertę z pełną historią ceny, inwestycją i deweloperem. Użyj, gdy chcesz zobaczyć, jak zmieniała się cena mieszkania. Wymaga offer_id i investment_slug (oba podaje search_offers albo get_investment): samo offer_id nie wystarcza.
>
> Zwraca cenę, metraż, cenę za m², status (active albo archived), zmianę od pierwszej ceny, daty i price_history (date, kind: offer, archived albo restored, price). Do listy ofert jednej inwestycji użyj get_investment.

Tytuł: „Oferta z historią ceny”. Adnotacje: `readOnlyHint=true`, `openWorldHint=true`. Zasady wspólne: [przegląd MCP](../README.md).

## Parametry
| Nazwa | Typ | Wymagany | Domyślna | Opis |
|---|---|---|---|---|
| `offer_id` | integer ≥ 1 | tak | — | offer_id z search_offers albo get_investment. Liczba może być też tekstem z samych cyfr. |
| `investment_slug` | string | tak | — | investment_slug inwestycji tej oferty, np. smolna (z search_offers). |

## Wynik
Wynik strukturalny i ten sam kompaktowy JSON w treści; pola `null` są pomijane.

Pola: `offer_id`, `name`, `status` (`active` albo `archived`), `investment_slug`, `investment_name`, `city`, `city_slug`, `developer` (`developer_slug`, `name`, opcjonalnie `website`, `description`), `price_history` (zawsze); `price` (PLN, cena ofertowa), `currency`, `area_m2`, `price_per_m2`, `price_change_since_start` (PLN, ujemna = tańsza), `price_change_since_start_pct`, `creation_date`, `last_event_date`, `last_change_date` (opcjonalne).

Zdarzenie historii (`price_history[]`): `kind` (`offer` – cena w ofercie, `archived` – wycofanie, `restored` – powrót), opcjonalnie `date` i `price`. Jedna oferta to rząd kilkuset znaków.

## Ograniczenia danych
- Serwis nie ma potwierdzonej drogi od samego `offer_id` do inwestycji, dlatego `investment_slug` jest wymagany (T1 w kodzie usługi).
- `kind: offer` to każdy wpis ceny ofertowej w historii: pierwsza cena i każda jej zmiana [P 2026-10-10]; nie jest to tylko pierwsza cena. Zob. [entities.md](../../discovery/entities.md) i [open-questions.md](../../open-questions.md).
- Ceny ofertowe, nie transakcyjne.

## Błędy
| Sytuacja | Komunikat |
|---|---|
| Inwestycja nie istnieje | `Nie znaleziono inwestycji '<slug>'. Slug inwestycji podaje search_offers (pole investment_slug).` |
| Inwestycja nie ma takiej oferty | `Inwestycja '<slug>' nie ma oferty <id>. Sprawdź offer_id i investment_slug (oba podaje search_offers); wszystkie oferty inwestycji zwraca get_investment.` |
| Brak historii ceny | `Serwis nie ma historii ceny oferty <id> z inwestycji '<slug>'. Sprawdź offer_id i investment_slug (oba podaje search_offers); ofertę bez historii pokazuje get_investment.` |
| `offer_id` < 1, nie liczba | `offer_id musi być liczbą całkowitą z zakresu 1–… (identyfikator oferty z search_offers), podano …` albo błąd schematu z SDK |
| STOP, błąd serwisu | Jak w [przeglądzie MCP](../README.md#błędy) |

## Przykład
Wywołanie:

```json
{"name": "get_offer", "arguments": {"offer_id": 2377, "investment_slug": "smolna"}}
```

Wynik z mocka testów (próbki `api.map_inv_visible`, `api.sale_events`):

```json
{
  "offer_id": 2377,
  "name": "C224",
  "status": "active",
  "price": 1620175.0,
  "currency": "PLN",
  "area_m2": 69.5,
  "price_per_m2": 23311.87,
  "price_change_since_start": 175.0,
  "price_change_since_start_pct": 0.01,
  "creation_date": "2025-02-25",
  "last_event_date": "2026-10-03",
  "last_change_date": "2026-10-03",
  "investment_slug": "smolna",
  "investment_name": "Smolna",
  "city": "Sopot",
  "city_slug": "sopot",
  "developer": {"developer_slug": "invest-komfort-spolka-akcyjna", "name": "Invest Komfort Spółka Akcyjna Sp.K."},
  "price_history": [
    {"date": "2025-02-25", "kind": "offer", "price": 1620000.0},
    {"date": "2025-02-25", "kind": "archived", "price": 1620000.0},
    {"date": "2026-10-03", "kind": "restored", "price": 1620175.0}
  ]
}
```

_Źródło: `src/deweloperuch_mcp/mcp_server.py`, `src/deweloperuch_mcp/mcp_results.py`, `src/deweloperuch_mcp/services.py`, `tests/snapshots/mcp_tools.json`_
