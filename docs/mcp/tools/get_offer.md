# `get_offer`
> Zwraca jedną ofertę z pełną historią ceny, inwestycją i deweloperem. Użyj, gdy chcesz zobaczyć, jak zmieniała się cena mieszkania. Wymaga offer_id i investment_slug (oba podaje search_offers albo get_investment): samo offer_id nie wystarcza.
>
> Zwraca cenę, metraż, cenę za m², status (active albo archived), zmianę od pierwszej ceny, daty i price_history (date, kind: offer, archived albo restored, price). investment_url i developer_url to strony inwestycji i dewelopera na deweloperuch.pl: podawaj je użytkownikowi jako linki. Do listy ofert jednej inwestycji użyj get_investment.

Summary: returns one offer with its full price history, investment and developer; use it to see how an apartment's price changed; it needs both `offer_id` and `investment_slug` (given by `search_offers` or `get_investment`), `offer_id` alone is not enough. Returns the price, area, price per m², status, change since the first price, dates and `price_history`; `investment_url` and `developer_url` are links to be given to the user; for the list of an investment's offers use `get_investment`.

Title: „Oferta z historią ceny”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `offer_id` | integer >= 1 | yes | — | The offer identifier from `search_offers` or `get_investment`; a number may also be a string of digits only. Schema text: „offer_id z search_offers albo get_investment. Liczba może być też tekstem z samych cyfr.” |
| `investment_slug` | string | yes | — | The slug of the offer's investment, e.g. smolna (from `search_offers`). Schema text: „investment_slug inwestycji tej oferty, np. smolna (z search_offers).” |

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

Fields: `offer_id`, `name`, `status` (`active` or `archived`), `investment_slug`, `investment_name`, `city`, `city_slug`, `developer` (`developer_slug`, `name`, optionally `website`, `description`), `price_history` (always); `investment_url` (the investment page on deweloperuch.pl: give it to the user as a link), `developer_url` (the developer profile on deweloperuch.pl: give it to the user as a link) (optional, a missing slug means no field); `price` (PLN, asking price), `currency`, `area_m2`, `price_per_m2`, `price_change_since_start` (PLN, negative = cheaper), `price_change_since_start_pct`, `creation_date`, `last_event_date`, `last_change_date` (optional).

A history event (`price_history[]`): `kind` (`offer` - a price in the offer, `archived` - withdrawal, `restored` - return), optionally `date` and `price`. One offer is a few hundred characters. The links lead to the investment and developer pages, not to a single offer (its page is not confirmed); rules: D12 in [decisions.md](../../decisions.md).

## Data limitations
- The service has no confirmed way from `offer_id` alone to the investment, which is why `investment_slug` is required (T1 in the service code).
- `kind: offer` is every asking-price entry in the history: the first price and each change [P 2026-10-10]; it is not only the first price. See [entities.md](../../discovery/entities.md) and [open-questions.md](../../open-questions.md).
- Asking prices, not transaction prices.

## Errors
| Situation | Message |
|---|---|
| The investment does not exist | `Nie znaleziono inwestycji '<slug>'. Slug inwestycji podaje search_offers (pole investment_slug).` |
| The investment has no such offer | `Inwestycja '<slug>' nie ma oferty <id>. Sprawdź offer_id i investment_slug (oba podaje search_offers); wszystkie oferty inwestycji zwraca get_investment.` |
| No price history | `Serwis nie ma historii ceny oferty <id> z inwestycji '<slug>'. Sprawdź offer_id i investment_slug (oba podaje search_offers); ofertę bez historii pokazuje get_investment.` |
| `offer_id` < 1, not a number | `offer_id musi być liczbą całkowitą z zakresu 1–… (identyfikator oferty z search_offers), podano …` or an SDK schema error |
| STOP, service error | As in the [MCP overview](../README.md#errors) |

## Example
Call:

```json
{"name": "get_offer", "arguments": {"offer_id": 2377, "investment_slug": "smolna"}}
```

The result from the test mock (samples `api.map_inv_visible`, `api.sale_events`):

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
  ]
}
```

_Source: `src/deweloperuch_mcp/interfaces/mcp/server.py`, `src/deweloperuch_mcp/interfaces/mcp/presenters.py`, `src/deweloperuch_mcp/application/`, `tests/snapshots/mcp_tools.json`_
