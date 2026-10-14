# `search_investments`
> Wyszukuje inwestycje (projekty deweloperskie, rynek pierwotny). Dwa tryby: city (pełne dane) albo samo name (cała Polska; tylko investment_slug, name i offers_active, w kolejności serwisu). Użyj, gdy pytanie dotyczy projektów, a nie pojedynczych mieszkań: np. najtańsze za m² w mieście, inwestycje jednego dewelopera, slug inwestycji po nazwie.
>
> Z city zwraca inwestycje, które serwis pokazuje na mapie miasta (z aktywnymi ofertami; bez nich mogą nie być na liście): investment_slug, name, city_slug, ulica, status, offers_active, offers_total, średnie (avg_price, avg_area_m2, avg_price_per_m2; tylko aktywne oferty, wg serwisu), developer_slug, developer_name, investment_url i developer_url. name i developer_slug zawężają listę, sort ją porządkuje (domyślnie najwięcej aktywnych ofert); pozycje bez średniej są na końcu. Oferty i szczegóły inwestycji daje get_investment (investment_slug). Linki podawaj użytkownikowi.
>
> Ograniczenia: najwyżej limit pozycji; total, returned, truncated i hint mówią, ile pominięto i co zawęzić. Nie filtruje po cenie ani metrażu (do tego search_offers); city=polska nie działa.

Title: „Szukaj inwestycji”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules (argument rules, errors, sizes): [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `city` | string | no* | none | „city_slug miasta z search_locations, np. warszawa, sopot (nie polska).” |
| `name` | string | no* | none | „Fragment nazwy inwestycji, 2–100 znaków, np. Kolibki. Z city wielkość liter i polskie znaki nie mają znaczenia; bez city szuka serwis w całej Polsce.” |
| `developer_slug` | string | no | none | „developer_slug z search_developers (po nazwie) albo z pól developer_slug w search_offers, get_investment, get_offer, np. atal. Tylko z city.” |
| `sort` | `active_offers` \| `price_per_m2_asc` \| `price_per_m2_desc` \| `price_asc` \| `price_desc` \| `name` | no | `active_offers` | „Tylko z city. active_offers: najwięcej aktywnych ofert (domyślnie); price_per_m2_asc, price_per_m2_desc: średnia cena za m²; price_asc, price_desc: średnia cena; name: alfabetycznie. Bez średniej na końcu.” |
| `limit` | integer 1-30 | no | `10` | „Najwięcej inwestycji w wyniku, 1–30, domyślnie 10. Pozycja z city to ok. 550–750 znaków wyniku (z linkami), więc 30 daje najwyżej ok. 23 tys.; zwykle wystarcza 10.” |

\* At least one of `city` and `name` is required (both are allowed). Blank text for `name`, `developer_slug` and `sort` means "none". Argument rules: [MCP overview](../README.md#argument-rules).

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

- `total`, `returned`, `truncated`, `hint` (when truncated or nothing matched) and `items`.
- With `city`, an item has `investment_slug`, `name`, `city_slug`, `status`, `offers_active`, `offers_total` and, when the service gives them, `street`, `avg_price`, `avg_area_m2`, `avg_price_per_m2` (active offers only), `developer_slug`, `developer_name`, `investment_url`, `developer_url`.
- With `name` only, an item has `investment_slug`, `name` and `offers_active`, in the service's order.

## Data limitations
- The list with `city` is what the service shows on the city map: investments without active offers may be missing. The averages are the service's, for active offers.
- `city=polska` does not work; searching the whole country is possible only by `name`. Filtering by price or area is not offered here (use `search_offers`).
- `sort`, `developer_slug` and the averages exist only in the `city` mode; the `name`-only mode keeps the service's order.
- Channels and open questions: [endpoints.md](../../discovery/endpoints.md), [open-questions.md](../../open-questions.md). Links: [Links to service pages](../README.md#links-to-service-pages).

## Errors
| Situation | Message |
|---|---|
| Neither `city` nor `name` | `Podaj city (slug miasta z search_locations, np. sopot) albo name (fragment nazwy inwestycji, np. Kolibki); można oba.` |
| `city=polska` | `city=polska nie działa przy wyszukiwaniu inwestycji: podaj slug jednego miasta (search_locations) albo szukaj w całym kraju po nazwie (name, bez city).` |
| `city` not a slug (e.g. `Sopot`) | `city: oczekiwano slug jednego miasta (np. warszawa, sopot; nie polska); slug podaje search_locations; podano 'Sopot'.` |
| `developer_slug` or `sort` without `city` | `developer_slug działa tylko razem z city: podaj slug miasta (search_locations), w którym szukać inwestycji dewelopera.` / `sort działa tylko razem z city; wyniki wyszukiwania po samej nazwie są w kolejności serwisu: pomiń sort albo podaj city.` |
| Unknown city | `Serwis nie zna miasta 'sopot'. Podaj city_slug z search_locations.` |
| `limit` outside 1-30, `sort` outside the list | `Błędny argument narzędzia search_investments: limit musi być liczbą całkowitą z zakresu 1–30, podano 31. Popraw i ponów; nic nie zostało wysłane.` |
| Unknown argument | `Nieznany argument narzędzia search_investments: '…'. Dozwolone argumenty: city, name, developer_slug, sort, limit. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| STOP, service error | As in the [MCP overview](../README.md#errors); service errors with the prefix `Wyszukiwanie inwestycji w '<city>': …` |

## Example
Call:

```json
{"name": "search_investments", "arguments": {"city": "sopot"}}
```

The result from `tests/golden/mcp/investments_search.json` (a mocked service answer):

```json
{
  "total": 2, "returned": 2, "truncated": false,
  "items": [
    {"investment_slug": "nowe-kolibki-etap-4", "name": "Nowe Kolibki etap 4", "city_slug": "sopot", "status": "active", "offers_active": 3, "offers_total": 27, "avg_price": 1615878.0, "avg_area_m2": 65.55, "avg_price_per_m2": 24756.49, "developer_slug": "invest-komfort-spolka-akcyjna", "developer_name": "Invest Komfort Spółka Akcyjna Sp.K.", "investment_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna/nowe-kolibki-etap-4", "developer_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna"},
    {"investment_slug": "smolna", "name": "Smolna", "city_slug": "sopot", "street": "Świemirowo", "status": "active", "offers_active": 3, "offers_total": 16, "avg_price": 1566392.0, "avg_area_m2": 63.97, "avg_price_per_m2": 24522.21, "developer_slug": "invest-komfort-spolka-akcyjna", "developer_name": "Invest Komfort Spółka Akcyjna Sp.K.", "investment_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna", "developer_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna"}
  ]
}
```

Name only (`{"name": "nowy targ"}`, `tests/golden/mcp/investments_search_by_name.json`): `{"total": 2, "returned": 2, "truncated": false, "items": [{"investment_slug": "nowy-targowek-vi", "name": "Nowy Targówek VI", "offers_active": 27}, {"investment_slug": "apartamenty-nowy-targ", "name": "Apartamenty Nowy Targ", "offers_active": 0}]}`.

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/search_investments_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/search_investments_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/search_investments.py`, `tests/snapshots/mcp_tools.json`_
