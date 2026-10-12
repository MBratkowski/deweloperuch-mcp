# `search_offers`
> Wyszukuje oferty mieszkań od deweloperów (tylko rynek pierwotny, ceny ofertowe, nie transakcyjne) w jednym mieście albo w całej Polsce (city=polska), z filtrami ceny i metrażu i sortowaniem po cenie. Użyj, gdy szukasz mieszkań w budżecie albo o danym metrażu. Nie filtruje po dzielnicy, liczbie pokoi ani deweloperze.
>
> Zwraca jedną stronę: total (wszystkie pasujące), returned, page, per_page, pages_available, truncated, hint, list_url i items (offer_id, investment_slug, investment_url (strona inwestycji, nie pojedynczej oferty), name, cena w PLN, metraż w m², cena za m², status, inwestycja, deweloper, ostatnia zmiana ceny i zmiana od pierwszej ceny w procentach; miasto tylko przy city=polska). Pozycje są skrócone; szczegóły oferty i historię ceny daje get_offer. list_url to link „zobacz wszystkie na deweloperuch.pl” z tymi samymi filtrami: przydatny, gdy truncated=true albo użytkownik chce więcej ofert. Linki podawaj użytkownikowi, np. w tabeli ofert.
>
> Ograniczenia: można przejrzeć najwyżej 20 stron po per_page ofert. Gdy truncated=true, zawęź filtry zamiast przeglądać kolejne strony. Wszystkie oferty jednej inwestycji daje get_investment.

Summary: searches developers' apartment offers (primary market only, asking prices, not transaction prices) in one city or the whole of Poland (`city=polska`), with price and area filters and price sorting; use it to find apartments within a budget or of a given area; it does not filter by district, number of rooms or developer. Returns one page: `total`, `returned`, `page`, `per_page`, `pages_available`, `truncated`, `hint`, `list_url` and `items` (shortened; details and price history come from `get_offer`); `list_url` is a "see all on deweloperuch.pl" link with the same filters. Limits: at most 20 pages of `per_page` offers can be browsed; when `truncated=true`, narrow the filters instead of paging; all offers of one investment come from `get_investment`.

Title: „Szukaj ofert mieszkań”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules (argument rules, errors, sizes): [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `city` | string | yes | — | The `city_slug` of a city from `search_locations` (e.g. warszawa, krakow) or polska for the whole country. Schema text: „city_slug miasta z search_locations (np. warszawa, krakow) albo polska dla całego kraju.” |
| `price_min` | integer 0-99 999 999 | no | none | The lowest offer price in PLN. Schema text: „Najniższa cena oferty w PLN.” |
| `price_max` | integer 0-99 999 999 | no | none | The highest offer price in PLN. Schema text: „Najwyższa cena oferty w PLN.” |
| `area_min` | integer 0-9 999 | no | none | The smallest area in m². Schema text: „Najmniejszy metraż w m².” |
| `area_max` | integer 0-9 999 | no | none | The largest area in m². Schema text: „Największy metraż w m².” |
| `sort` | `price_asc` \| `price_desc` | no | none | `price_asc`: cheapest first, `price_desc`: most expensive first; none: the service's default order (not guaranteed). Schema text: „price_asc: od najtańszych, price_desc: od najdroższych; brak: domyślna kolejność serwisu (nie jest gwarantowana).” |
| `page` | integer 1-20 | no | `1` | The results page number, 1-20. Schema text: „Numer strony wyników, 1–20.” |
| `per_page` | `10` \| `50` | no | `10` | 10 or 50. An item is about 450 characters of result (with a link), so 50 gives about 22k; 10 is usually enough. Schema text: „10 albo 50. Pozycja to ok. 450 znaków wyniku (z linkiem), więc 50 daje ok. 22 tys.; zwykle wystarcza 10.” |

Argument rules (numbers as a string of digits only, `""`/`null`, trimming of `sort`): [MCP overview](../README.md#argument-rules). `price_min` greater than `price_max` (likewise for area) is a service validation error.

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

An item: `offer_id`, `investment_slug`, `name`, `status` (`active` or `archived`), `investment_name`, `developer_name` (always); `investment_url` (the investment page on deweloperuch.pl, not a single offer: give it to the user as a link; a missing slug means no field), `price` (PLN, asking price), `area_m2`, `price_per_m2`, `last_price_change_kind` (`increase`, `decrease`, `no_change`), `last_price_change_pct`, `price_change_since_start_pct` (negative = cheaper) (optional); `city`, `city_slug` only with `city=polska`.

Sizes (full pages from samples, with links): 10 items about 4 500 characters, 50 about 21 200, 50 with `polska` about 23 300.

Links (`*_url`): only three page patterns confirmed [P], without `_rsc` and `/api/`, no link to a single offer (its page is not confirmed). Rules: D12 in [decisions.md](../../decisions.md).

## Data limitations
- At most 20 pages (`page` 1-20) of `per_page` offers can be browsed; the rest is unreachable and the filters must be narrowed. See [pages-rsc.md](../../discovery/pages-rsc.md), [Common list rules](../../discovery/pages-rsc.md#common-list-rules-p).
- `per_page` in MCP is 10 and 50 ([P] in pages-rsc.md); the CLI also accepts 100.
- The maxima of `price_*` (99 999 999 PLN) and `area_*` (9 999 m²) are range sentinels [P z kodu] of the service's client, not market data.
- Sorting by price (`amount`, ascending and descending) is confirmed [P 2026-10-10]; without `sort` the service sorts ascending by offer identifier, and an unknown sort value gives no error (T3 in [open-questions.md](../../open-questions.md)).
- Primary-market asking prices, not transaction prices.

## Errors
| Situation | Message |
|---|---|
| `price_min` > `price_max` | `price_min (7) jest większe niż price_max (5); zamień je miejscami.` (likewise for `area_`) |
| A number out of range | `<pole> musi być liczbą całkowitą z zakresu <od>–<do> …, podano <wartość>.` (or an SDK schema error) |
| Unknown city (a valid slug the service does not know) | `Serwis nie zna miasta '<city>'. Podaj city_slug z search_locations albo polska (cały kraj).` |
| Bad `city`: a name instead of a slug (e.g. `Warszawa`, `Kraków`), capital letters, an empty string | `city: oczekiwano slug miasta (np. warszawa) albo polska; slug podaje search_locations; podano '…'.` No request to the service; surrounding spaces are trimmed, a slug is lowercase ASCII letters, digits and hyphens. |
| `sort`/`per_page` outside the list | A schema validation error from the SDK (English, prefix „Error executing tool …”) |
| STOP, service error | As in the [MCP overview](../README.md#errors); service errors with the prefix `Wyszukiwanie ofert w '<city>': …` |

## Example
Call (default `per_page` 10, no filters):

```json
{"name": "search_offers", "arguments": {"city": "warszawa"}}
```

The result from the test mock (`tests/service_mocks.offers_page(count=10)`): the items are copies of offers from the `page.offers_list` sample with synthetic `offer_id` values (900000+), and `total` comes from the sample. The first 2 of 10 items are shown, the remaining 8 omitted:

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
    {"offer_id": 900000, "investment_slug": "nowy-targowek-vi", "name": "D1.1.1.4", "price": 994012.0, "area_m2": 55.25, "price_per_m2": 17991.17, "status": "active", "investment_name": "Nowy Targówek VI", "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi", "developer_name": "ATAL S.A.", "last_price_change_kind": "increase", "last_price_change_pct": 5.89, "price_change_since_start_pct": -0.6},
    {"offer_id": 900001, "investment_slug": "nowy-targowek-vi", "name": "D1.2.0.1", "price": 659315.0, "area_m2": 36.49, "price_per_m2": 18068.37, "status": "active", "investment_name": "Nowy Targówek VI", "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi", "developer_name": "ATAL S.A.", "last_price_change_kind": "decrease", "last_price_change_pct": -3.21, "price_change_since_start_pct": -4.45}
  ]
}
```

_Source: `src/deweloperuch_mcp/mcp_server.py`, `src/deweloperuch_mcp/mcp_results.py`, `src/deweloperuch_mcp/services.py`, `tests/snapshots/mcp_tools.json`_
