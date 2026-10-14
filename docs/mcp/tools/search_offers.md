# `search_offers`
> Wyszukuje oferty mieszkań od deweloperów (tylko rynek pierwotny, ceny ofertowe, nie transakcyjne) w jednym mieście albo w całej Polsce (city=polska). Filtry: cena, metraż, cena za m², dzielnica, status (aktywne, archiwalne) i obniżka od pierwszej ceny; sortowanie po cenie, cenie za m², metrażu albo największej obniżce. Nie filtruje po liczbie pokoi ani piętrze (serwis nie ma takich danych) ani po deweloperze (jego inwestycje daje get_developer).
>
> Zwraca jedną stronę: total (wszystkie pasujące), returned, page, per_page, pages_available, truncated, hint, list_url i items (offer_id, investment_slug, investment_url (strona inwestycji), name, cena w PLN, metraż w m², cena za m², status, inwestycja, deweloper z developer_slug, zmiany ceny w procentach; miasto tylko przy city=polska). Pozycje są skrócone; szczegóły oferty i historię ceny daje get_offer. list_url to ta lista na deweloperuch.pl z tymi samymi filtrami. Linki podawaj użytkownikowi.
>
> Ograniczenia: można przejrzeć najwyżej 20 stron po per_page ofert. Gdy truncated=true, zawęź filtry zamiast przeglądać kolejne strony. Wszystkie oferty jednej inwestycji daje get_investment, ceny całego miasta get_market_statistics.

Title: „Szukaj ofert mieszkań”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules (argument rules, errors, sizes): [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `city` | string | yes | — | „city_slug miasta z search_locations (np. warszawa, krakow) albo polska dla całego kraju.” |
| `price_min` | integer 0-99 999 999 | no | none | „Najniższa cena oferty w PLN.” |
| `price_max` | integer 0-99 999 999 | no | none | „Najwyższa cena oferty w PLN.” |
| `area_min` | integer 0-9 999 | no | none | „Najmniejszy metraż w m².” |
| `area_max` | integer 0-9 999 | no | none | „Największy metraż w m².” |
| `price_per_m2_min` | integer 0-999 999 | no | none | „Najniższa cena za m² w PLN.” |
| `price_per_m2_max` | integer 0-999 999 | no | none | „Najwyższa cena za m² w PLN.” |
| `district` | string | no | none | „Nazwa dzielnicy dokładnie tak, jak podaje ją search_locations (kind=district, pole name), np. Mokotów; tylko z miastem tej dzielnicy, nie z polska.” |
| `price_dropped` | boolean | no | `false` | „true: tylko oferty, których obecna cena jest niższa od pierwszej ceny (liczy się zmiana od pierwszej ceny, nie ostatnia zmiana).” |
| `status` | `active` \| `archived` \| `all` | no | `active` | „active (domyślnie): oferty obecnie w cennikach; archived: tylko wycofane; all: aktywne i wycofane.” |
| `sort` | `price_asc` \| `price_desc` \| `price_per_m2_asc` \| `price_per_m2_desc` \| `area_asc` \| `area_desc` \| `biggest_drop` | no | none | „price_asc: od najtańszych, price_desc: od najdroższych, price_per_m2_asc i price_per_m2_desc: po cenie za m², area_asc i area_desc: po metrażu, biggest_drop: najpierw największa obniżka od pierwszej ceny (w %); brak: domyślna kolejność serwisu (nie jest gwarantowana).” |
| `page` | integer 1-20 | no | `1` | „Numer strony wyników, 1–20.” |
| `per_page` | `10` \| `50` | no | `10` | „10 albo 50. Pozycja to ok. 500 znaków wyniku (z linkiem), więc 50 daje ok. 25 tys.; zwykle wystarcza 10.” |

Argument rules (numbers as a string of digits only, `""`/`null`, trimming of `sort`): [MCP overview](../README.md#argument-rules). A reversed range (`price_min` > `price_max`, likewise for area and `price_per_m2_*`) is rejected before any request. A blank `district` means "none".

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Type | Description |
|---|---|---|
| `total` | integer | All matching offers. |
| `returned` | integer | The number of items on this page. |
| `truncated` | boolean | `true`: there are more matching offers than can be browsed (20 pages at most); narrow the filters. |
| `page`, `per_page`, `pages_available` | integer | The page, its size and the number of pages that can be browsed. |
| `hint` | string | When truncated: how many offers match, how many pages of what size can be browsed, and advice to narrow the filters (optional). |
| `list_url` | string | This offer list on deweloperuch.pl (the same filters, sorting and page): give it to the user as a link (optional). |
| `items` | array | Shortened items. |

An item: `offer_id`, `investment_slug`, `name`, `status` (`active` or `archived`), `investment_name`, `developer_name` (always); `developer_slug` (for `get_developer` and `search_investments`), `investment_url` (the investment page on deweloperuch.pl, not a single offer: give it to the user as a link; a missing slug means no field), `price` (PLN, asking price), `area_m2`, `price_per_m2`, `last_price_change_kind` (`increase`, `decrease`, `no_change`), `last_price_change_pct`, `price_change_since_start_pct` (negative = cheaper) (optional); `city`, `city_slug` only with `city=polska`.

Sizes (mocked full pages, with links): 10 items about 4 700 characters, 50 about 22 400.

Links (`*_url`): only the confirmed page patterns, without `_rsc` and `/api/`, no link to a single offer (its page is not confirmed). Rules: [Links to service pages](../README.md#links-to-service-pages).

## Data limitations
- At most 20 pages (`page` 1-20) of `per_page` offers can be browsed; the rest is unreachable and the filters must be narrowed. See [pages-rsc.md](../../discovery/pages-rsc.md), [Common list rules](../../discovery/pages-rsc.md#common-list-rules-p).
- `per_page` in MCP is 10 and 50; the CLI also accepts 100.
- The maxima of `price_*` (99 999 999 PLN), `area_*` (9 999 m²) and `price_per_m2_*` (999 999 PLN) are range limits taken from the service client, not market data.
- Sorting by price is verified; without `sort` the service sorts ascending by offer identifier, and an unknown sort value gives no error ([open-questions.md](../../open-questions.md)). The other sorts and filters (`price_per_m2_*`, `district`, `price_dropped`, `status`) are listed in [pages-rsc.md](../../discovery/pages-rsc.md) with their confirmation level; the `price_per_m2_*` range (`filterPricePerM2`) is not yet marked as verified there (see [open-questions.md](../../open-questions.md)).
- No filter by number of rooms, floor or developer (the service has no such data in the list); for a developer's investments use `get_developer` or `search_investments` with `developer_slug`.
- Primary-market asking prices, not transaction prices.

## Errors
| Situation | Message |
|---|---|
| A range reversed | `price_min (700000) jest większe niż price_max (500000); zamień je miejscami.` (likewise for `area_` and `price_per_m2_`) |
| A number or choice out of range | `Błędny argument narzędzia search_offers: price_per_m2_max musi być liczbą całkowitą z zakresu 0–999999 albo pusty, podano 1000000. Popraw i ponów; nic nie zostało wysłane.` (likewise `status`: `…musi być jedną z wartości active, archived, all albo pusty, podano "sold"…`, `sort`, `page`, `per_page`) |
| Unknown argument | `Nieznany argument narzędzia search_offers: 'max_price'. Dozwolone argumenty: city, price_min, price_max, area_min, area_max, price_per_m2_min, price_per_m2_max, district, price_dropped, status, sort, page, per_page. Popraw nazwy i ponów; nic nie zostało wysłane.` (several: `Nieznane argumenty narzędzia search_offers: 'developer', 'floor', 'rooms'. …`) |
| `district` with `city=polska` | `district działa tylko z jednym miastem: podaj jako city slug miasta tej dzielnicy (search_locations zwraca go przy dzielnicy), a nie polska; podano 'Wola'.` |
| Unknown city (a valid slug the service does not know) | `Serwis nie zna miasta 'nieistniejace-miasto'. Podaj city_slug z search_locations albo polska (cały kraj).` |
| Bad `city`: a name instead of a slug (e.g. `Kraków`), capital letters, an empty string | `city: oczekiwano slug miasta (np. warszawa) albo polska; slug podaje search_locations; podano 'Kraków'.` No request to the service; surrounding spaces are trimmed, a slug is lowercase ASCII letters, digits and hyphens. |
| STOP, service error | As in the [MCP overview](../README.md#errors); service errors with the prefix `Wyszukiwanie ofert w '<city>': …` |

## Example
Call (default `per_page` 10, no filters):

```json
{"name": "search_offers", "arguments": {"city": "warszawa"}}
```

The result from `tests/golden/mcp/offers.json`: the items are copies of offers from the `page.offers_list` sample, and `total` comes from the sample. The first 2 of 10 items are shown, the remaining 8 omitted:

```json
{
  "total": 13324,
  "returned": 10,
  "truncated": true,
  "page": 1,
  "per_page": 10,
  "pages_available": 20,
  "hint": "Pasujących ofert jest 13324, a można przejrzeć najwyżej 20 stron po 10 (200). Zawęź filtry (cena, metraż).",
  "list_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/mieszkania?page=1&perPage=10",
  "items": [
    {"offer_id": 4397, "investment_slug": "nowy-targowek-vi", "name": "D1.1.1.4", "price": 994012.0, "area_m2": 55.25, "price_per_m2": 17991.17, "status": "active", "investment_name": "Nowy Targówek VI", "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi", "developer_name": "ATAL S.A.", "developer_slug": "atal", "last_price_change_kind": "increase", "last_price_change_pct": 5.89, "price_change_since_start_pct": -0.6},
    {"offer_id": 4406, "investment_slug": "nowy-targowek-vi", "name": "D1.2.0.1", "price": 659315.0, "area_m2": 36.49, "price_per_m2": 18068.37, "status": "active", "investment_name": "Nowy Targówek VI", "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi", "developer_name": "ATAL S.A.", "developer_slug": "atal", "last_price_change_kind": "decrease", "last_price_change_pct": -3.21, "price_change_since_start_pct": -4.45}
  ]
}
```

With the new filters (`tests/golden/mcp/offers_new_filters.json`): `{"city": "warszawa", "price_per_m2_min": 12000, "price_per_m2_max": "20000", "district": "Mokotów", "price_dropped": true, "status": "archived", "sort": "biggest_drop"}` gives a `list_url` with `filterPricePerM2=12000-20000&filterDistrict=Mokot%C3%B3w&filterPriceChange=decrease&filterStatus=archived&sortBy=start_amount_difference_percent&sortOrder=asc`.

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/search_offers_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/search_offers_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/search_offers.py`, `src/deweloperuch_mcp/api/queries/offers_query.py`, `tests/snapshots/mcp_tools.json`_
