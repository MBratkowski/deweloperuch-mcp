# `get_offer`
> Zwraca jedną ofertę z pełną historią ceny, inwestycją i deweloperem. Użyj, gdy chcesz zobaczyć, jak zmieniała się cena mieszkania. Wymaga offer_id i investment_slug (oba podaje search_offers albo get_investment): samo offer_id nie wystarcza.
>
> Zwraca cenę, metraż, cenę za m², status (active albo archived), zmianę od pierwszej ceny, daty, price_history (date, kind: offer, archived albo restored, price) i price_flags. investment_url i developer_url to strony inwestycji i dewelopera na deweloperuch.pl: podawaj je użytkownikowi jako linki. Do listy ofert jednej inwestycji użyj get_investment.
>
> price_flags (na dziś; ceny z offer i restored, wycofanie przerywa cenę; oferta archiwalna do dnia wycofania): lowest_price_30d i lowest_price_90d to najniższa cena obowiązująca w ostatnich 30 i 90 dniach, także ta sprzed okna; price_changes to liczba zmian ceny; largest_drop_pct i largest_rise_pct to największa pojedyncza obniżka i podwyżka w % poprzedniej ceny; suspicious_reduction=true, gdy ostatnia obniżka przyszła do 30 dni po podwyżce, a nowa cena nie jest niższa od najniższej z 30 dni przed nią („promocja” po podwyżce).

Title: „Oferta z historią ceny”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `offer_id` | integer >= 1 | yes | — | „offer_id z search_offers albo get_investment.” A number may also be a string of digits only. |
| `investment_slug` | string | yes | — | „investment_slug inwestycji tej oferty, np. smolna (z search_investments, search_offers albo get_developer).” |

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

Fields: `offer_id`, `name`, `status` (`active` or `archived`), `investment_slug`, `investment_name`, `city`, `city_slug`, `developer` (`developer_slug`, `name`, optionally `website`, `description`), `price_history` (always); `investment_url` (the investment page on deweloperuch.pl: give it to the user as a link), `developer_url` (the developer profile on deweloperuch.pl: give it to the user as a link) (optional, a missing slug means no field); `price` (PLN, asking price), `currency`, `area_m2`, `price_per_m2`, `price_change_since_start` (PLN, negative = cheaper), `price_change_since_start_pct`, `creation_date`, `last_event_date`, `last_change_date`, `price_flags` (optional).

`price_flags` (computed as of today from the history; prices come from `offer` and `restored` events, an `archived` event ends the price in effect, and an archived offer is counted up to its withdrawal day): `lowest_price_30d`, `lowest_price_90d` (the lowest price in effect in the last 30 and 90 days, also one set before the window), `price_changes` (the number of price changes), `largest_drop_pct`, `largest_rise_pct` (the largest single drop and rise as a percentage of the previous price), `suspicious_reduction` (`true` when the latest drop came within 30 days after a rise and the new price is not lower than the lowest of the 30 days before it: a "promotion" after a rise). A flag with no basis (e.g. no drop yet) is omitted.

A history event (`price_history[]`): `kind` (`offer` - a price in the offer, `archived` - withdrawal, `restored` - return), optionally `date` and `price`. One offer is a few hundred characters. The links lead to the investment and developer pages, not to a single offer (its page is not confirmed); rules: D12 in [decisions.md](../../decisions.md).

## Data limitations
- The service has no confirmed way from `offer_id` alone to the investment, which is why `investment_slug` is required.
- `kind: offer` is every asking-price entry in the history: the first price and each change; it is not only the first price. See [entities.md](../../discovery/entities.md) and [open-questions.md](../../open-questions.md).
- Asking prices, not transaction prices.

## Errors
| Situation | Message |
|---|---|
| The investment does not exist | `Nie znaleziono inwestycji '<slug>'. Slug inwestycji podaje search_investments, search_offers albo get_developer (pole investment_slug).` |
| The investment has no such offer | `Inwestycja '<slug>' nie ma oferty <id>. Sprawdź offer_id i investment_slug (oba podaje search_offers); wszystkie oferty inwestycji zwraca get_investment.` |
| No price history | `Serwis nie ma historii ceny oferty <id> z inwestycji '<slug>'. Sprawdź offer_id i investment_slug (oba podaje search_offers); ofertę bez historii pokazuje get_investment.` |
| `offer_id` < 1, not a number | `Błędny argument narzędzia get_offer: offer_id musi być liczbą całkowitą nie mniejszą niż 1, podano 0. Popraw i ponów; nic nie zostało wysłane.` |
| Unknown argument | `Nieznany argument narzędzia get_offer: '…'. Dozwolone argumenty: offer_id, investment_slug. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| STOP, service error | As in the [MCP overview](../README.md#errors) |

## Example
Call:

```json
{"name": "get_offer", "arguments": {"offer_id": 2377, "investment_slug": "smolna"}}
```

The result from `tests/golden/mcp/offer.json` (samples `api.map_inv_visible`, `api.sale_events`):

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
  "investment_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna",
  "city": "Sopot",
  "city_slug": "sopot",
  "developer": {"developer_slug": "invest-komfort-spolka-akcyjna", "name": "Invest Komfort Spółka Akcyjna Sp.K."},
  "developer_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna",
  "price_history": [
    {"date": "2025-02-25", "kind": "offer", "price": 1620000.0},
    {"date": "2025-02-25", "kind": "archived", "price": 1620000.0},
    {"date": "2026-10-03", "kind": "restored", "price": 1620175.0}
  ],
  "price_flags": {"lowest_price_30d": 1620175.0, "lowest_price_90d": 1620175.0, "price_changes": 1, "largest_rise_pct": 0.01, "suspicious_reduction": false}
}
```

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_offer_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_offer_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_offer.py`, `src/deweloperuch_mcp/models/price_history.py`, `tests/snapshots/mcp_tools.json`_
