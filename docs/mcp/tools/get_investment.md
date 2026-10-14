# `get_investment`
> Zwraca inwestycję (projekt deweloperski): miasto, ulicę, współrzędne, dewelopera, średnie ceny aktywnych ofert, liczbę ofert i listę ofert (najpierw aktywne, potem archiwalne). Użyj, gdy chcesz zobaczyć mieszkania jednego projektu. investment_slug daje search_investments, search_offers albo get_developer. investment_url i developer_url to strony inwestycji i dewelopera na deweloperuch.pl: podawaj je użytkownikowi jako linki.
>
> Ograniczenia: zwraca najwyżej limit ofert (domyślnie 20); offers_returned mówi, ile ich jest na liście, truncated i offers_omitted, czy i ile pominięto. offers_total to liczba z serwisu, a pominięte oferty liczy offers_omitted. Przy dużej inwestycji nie zwiększaj limitu bez potrzeby; offers_omitted > 0 znaczy, że lista jest niepełna. include_history=true dodaje historię ceny każdej zwróconej oferty: wynik jest dłuższy i powstaje wolniej. Dla jednej oferty lepiej użyć get_offer.

Title: „Inwestycja z ofertami”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `investment_slug` | string | yes | — | „investment_slug z search_investments, search_offers albo get_developer, np. smolna.” |
| `include_history` | boolean | no | `false` | `true` attaches the price history of each returned offer (longer result). `null` = `false`. Schema text: „true: dołącz historię ceny każdej zwróconej oferty (dłuższy wynik).” |
| `limit` | integer 0-200 | no | `20` | The maximum number of offers in the result (active first), default 20, 0 = only the investment summary; each offer is about 300 characters of result, a few hundred more with the price history; the maximum 200 gives about 60k characters. `null` = 20. Schema text: „Najwięcej ofert w wyniku (najpierw aktywne), domyślnie 20, 0 = tylko podsumowanie inwestycji. Ile pominięto, mówi offers_omitted. Każda oferta to ok. 300 znaków wyniku, z historią ceny kilkaset więcej. Maksimum 200 daje ok. 60 tys. znaków; zwykle wystarcza domyślne 20.” |

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Type | Description |
|---|---|---|
| `investment_slug`, `name`, `status`, `city`, `city_slug`, `developer` | | Always (`developer`: `developer_slug`, `name`, optionally `website`, `description`). |
| `street`, `lat`, `lng`, `currency` | | Optional. |
| `investment_url`, `developer_url` | string | The investment page and the developer profile on deweloperuch.pl: give them to the user as links (optional; a missing slug means no field). The `offers` entries have no links. Rules: [Links to service pages](../README.md#links-to-service-pages). |
| `avg_price`, `avg_area_m2`, `avg_price_per_m2`, `offers_active` | | Optional; the averages concern active offers (price in PLN). |
| `offers_total` | integer | All offers of the investment according to the service, also archived; the `offers` list is cut by `limit`. |
| `offers` | array | Offers (active first): `offer_id`, `name`, `status`; optionally `price`, `currency`, `area_m2`, `price_per_m2`, `price_change_since_start`, `price_change_since_start_pct`, `creation_date`, `last_event_date`, `last_change_date` and, with `include_history=true`, `price_history` (`kind`: `offer` - a price in the offer, `archived`, `restored`). |
| `offers_returned` | integer | The number of offers in the `offers` list. |
| `offers_omitted` | integer | The number of offers omitted by `limit`. |
| `truncated` | boolean | `true`: the `offers` list is incomplete (`offers_omitted` > 0). |

Sizes (compact JSON, with links): 20 (default) about 6 400 characters, 200 about 58 100.

## Data limitations
- `limit` max 200 (MCP); the CLI `investments get` without `--limit` shows all offers.
- `include_history=true` is an extra request to the service (slower when it is not in the cache).
- `kind: offer` is every asking-price entry in the history (the first price and each change); see [entities.md](../../discovery/entities.md), [open-questions.md](../../open-questions.md).
- Asking prices, not transaction prices.

## Errors
| Situation | Message |
|---|---|
| The investment does not exist | `Nie znaleziono inwestycji '<slug>'. Slug inwestycji podaje search_investments, search_offers albo get_developer (pole investment_slug).` |
| No price history (with `include_history`) | `Serwis nie ma historii cen ofert inwestycji '<slug>'. Pobierz inwestycję bez include_history, a historię pojedynczej oferty przez get_offer.` |
| Bad `investment_slug` | `investment_slug: oczekiwano slug inwestycji, np. smolna; podaje go search_offers (investment_slug); podano '…'.` |
| `limit` outside 0-200, `include_history` not a boolean | `Błędny argument narzędzia get_investment: limit musi być liczbą całkowitą z zakresu 0–200, podano 201. Popraw i ponów; nic nie zostało wysłane.` |
| Unknown argument | `Nieznany argument narzędzia get_investment: '…'. Dozwolone argumenty: investment_slug, include_history, limit. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| STOP, service error | As in the [MCP overview](../README.md#errors); service errors with the prefix `Inwestycja '<slug>': …` |

## Example
Call:

```json
{"name": "get_investment", "arguments": {"investment_slug": "smolna", "limit": 1}}
```

The result for `limit` 1, cut from `tests/golden/mcp/investment.json` (sample `api.map_inv_visible`):

```json
{
  "investment_slug": "smolna",
  "name": "Smolna",
  "status": "active",
  "investment_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna",
  "city": "Sopot",
  "city_slug": "sopot",
  "street": "Świemirowo",
  "lat": 54.42735985,
  "lng": 18.55839032,
  "currency": "PLN",
  "developer": {"developer_slug": "invest-komfort-spolka-akcyjna", "name": "Invest Komfort Spółka Akcyjna Sp.K."},
  "developer_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna",
  "avg_price": 1566392.0,
  "avg_area_m2": 63.97,
  "avg_price_per_m2": 24487.63,
  "offers_active": 3,
  "offers_total": 16,
  "offers": [
    {"offer_id": 206087, "name": "C234", "status": "active", "price": 1679796.0, "currency": "PLN", "area_m2": 65.9, "price_per_m2": 25490.08, "price_change_since_start": 0.0, "price_change_since_start_pct": 0.0, "creation_date": "2026-10-03", "last_event_date": "2026-10-03", "last_change_date": "2026-10-03"}
  ],
  "offers_returned": 1,
  "offers_omitted": 2,
  "truncated": true
}
```

(The sample has 3 offers; `offers_total` 16 comes from the investment data in the sample.)

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_investment_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_investment_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_investment.py`, `tests/snapshots/mcp_tools.json`_
