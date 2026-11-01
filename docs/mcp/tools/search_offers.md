# `search_offers`
> Wyszukuje oferty mieszkań od deweloperów (tylko rynek pierwotny, ceny ofertowe, nie transakcyjne) w jednym mieście albo w jego dzielnicy; city=polska nie działa. city_slug i nazwę dzielnicy daje search_locations. Filtry: cena, metraż, cena za m², dzielnica, status (aktywne, archiwalne) i obniżka od pierwszej ceny; sortowanie po cenie, cenie za m², metrażu albo największej obniżce; lista ofert nie filtruje po pokojach ani piętrze, ani po deweloperze (jego inwestycje daje get_developer).
>
> Zwraca jedną stronę: total (wszystkie pasujące), returned, page, per_page, pages_available, truncated, hint, list_url i items (offer_id, investment_slug, investment_url, name, cena w PLN, metraż w m², cena za m², status, inwestycja z dzielnicą, deweloper z developer_slug, zmiany ceny w procentach). Pozycje są skrócone; szczegóły oferty i historię ceny daje get_offer. Linki podawaj użytkownikowi.
>
> Ograniczenia: można przejrzeć najwyżej 20 stron po per_page ofert. Gdy truncated=true, zawęź filtry (np. dzielnica, cena) zamiast przeglądać kolejne strony. Wszystkie oferty jednej inwestycji daje get_investment, ceny całego miasta get_market_statistics.

Title: „Szukaj ofert mieszkań”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules (argument rules, errors, sizes): [MCP overview](../README.md).

Searches one city or one district of a city. **Not the whole of Poland:** `city=polska` is refused before any request, because the service has no list of offers of the whole country (its page for Poland is a list of cities).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `city` | string | yes | — | „city_slug jednego miasta z search_locations, np. warszawa, krakow (nie polska: serwis nie ma listy ofert całego kraju).” |
| `price_min` | integer 0-99 999 999 | no | none | „Najniższa cena oferty w PLN.” |
| `price_max` | integer 0-99 999 999 | no | none | „Najwyższa cena oferty w PLN.” |
| `area_min` | integer 0-9 999 | no | none | „Najmniejszy metraż w m².” |
| `area_max` | integer 0-9 999 | no | none | „Największy metraż w m².” |
| `price_per_m2_min` | integer 0-999 999 | no | none | „Najniższa cena za m² w PLN.” |
| `price_per_m2_max` | integer 0-999 999 | no | none | „Najwyższa cena za m² w PLN.” |
| `district` | string, 2-100 characters | no | none | „Nazwa dzielnicy dokładnie tak, jak podaje ją search_locations (kind=district, pole name), np. Mokotów, Praga-Południe; razem z city_slug miasta tej dzielnicy.” |
| `price_dropped` | boolean | no | `false` | „true: tylko oferty, których obecna cena jest niższa od pierwszej ceny (liczy się zmiana od pierwszej ceny, nie ostatnia zmiana).” |
| `status` | `active` \| `archived` \| `all` | no | `active` | „active (domyślnie): oferty obecnie w cennikach; archived: tylko wycofane; all: aktywne i wycofane (total przy all może być większy niż suma active i archived: serwis liczy je niejasno).” |
| `sort` | `price_asc` \| `price_desc` \| `price_per_m2_asc` \| `price_per_m2_desc` \| `area_asc` \| `area_desc` \| `biggest_drop` | no | none | „price_asc: od najtańszych, price_desc: od najdroższych, price_per_m2_asc i price_per_m2_desc: po cenie za m², area_asc i area_desc: po metrażu, biggest_drop: najpierw największa obniżka od pierwszej ceny (w %); brak: domyślna kolejność serwisu (nie jest gwarantowana; zwykle najstarsze oferty, grupami po inwestycji; to nie ranking), więc do przeglądu miasta podaj sort.” |
| `page` | integer 1-20 | no | `1` | „Numer strony wyników, 1–20 (dalej serwis nie udostępnia: zawęź filtry).” |
| `per_page` | `10` \| `50` | no | `10` | „10 albo 50. Pozycja to ok. 500 znaków wyniku (z linkiem), więc 50 daje ok. 25 tys.; zwykle wystarcza 10.” |

Argument rules (numbers as a string of digits only, `""`/`null`, trimming of `sort`): [MCP overview](../README.md#argument-rules). A reversed range (`price_min` > `price_max`, likewise for area and `price_per_m2_*`) is rejected before any request. A blank `district` means "none".

How `district` works: the tool reads the district's own list, `/ceny-ofertowe/{city}/{district slug}/mieszkania`, and makes the slug itself from the name (`Praga-Południe` becomes `praga-poludnie`: Polish letters to ASCII, lower case, runs of other characters to one hyphen). The name must be the one `search_locations` gives (`kind=district`, field `name`) and the city must be the district's own. A name with no Latin letter or digit has no slug, so it is refused as unknown without a request.

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Type | Description |
|---|---|---|
| `total` | integer | All matching offers. |
| `returned` | integer | The number of items on this page. |
| `truncated` | boolean | `true`: there are more matching offers than can be browsed (20 pages at most); narrow the filters. |
| `page`, `per_page`, `pages_available` | integer | The page, its size and the number of pages that can be browsed. |
| `hint` | string | When truncated: how many offers match, how many pages of what size can be browsed, and advice to narrow the filters: „Zawęź filtry (dzielnica, cena, metraż).”, and „(cena, metraż)” when the search is already in a district. With no match: „Brak ofert spełniających kryteria. Sprawdź slug miasta (search_locations) i poluzuj filtry.” For an empty page: „Strona N jest pusta; dostępne strony: 1–M.” (optional). |
| `list_url` | string | This offer list on deweloperuch.pl, the city's or the district's (the same filters, sorting and page; `page=1` is never part of it): give it to the user as a link (optional). |
| `items` | array | Shortened items. |

An item: `offer_id`, `investment_slug`, `name` (the developer's label of the flat, e.g. `A2`; the investment's name is `investment_name`), `status` (`active` or `archived`), `investment_name`, `developer_name` (always); `district` (the investment's district, spelled as `search_locations` names it, so it can be passed back as `district`; absent when the service gives none, e.g. Sopot), `developer_slug` (for `get_developer` and `search_investments`), `investment_url` (the investment page on deweloperuch.pl, not a single offer: give it to the user as a link; a missing slug means no field), `price` (PLN, asking price), `area_m2`, `price_per_m2`, `last_price_change_kind` (`increase`, `decrease`, `no_change`, `new_offer`: an offer without a price change since it was added), `last_price_change_pct`, `price_change_since_start_pct` (negative = cheaper) (optional). An item has no `city` or `city_slug` (it is the city asked for).

Sizes (a mocked full page of real offers, with links): 10 items about 5 100 characters, 50 about 23 900.

Links (`*_url`): only the confirmed page patterns, without `_rsc` and `/api/`, no link to a single offer (its page is not confirmed). Rules: [Links to service pages](../README.md#links-to-service-pages).

## Data limitations
- At most 20 pages (`page` 1-20) of `per_page` offers can be browsed; the rest is unreachable and the filters must be narrowed. See [pages-rsc.md](../../discovery/pages-rsc.md), [Common list rules](../../discovery/pages-rsc.md#common-list-rules-p).
- Only one city or one district at a time. A search of several cities is one call per city.
- On the redesigned service (2026-10-29) a page past the last one is answered like an unknown city (Next.js's 404 marker, [P 2026-10-31] live), so a `page` above 1 that is not found gets its own message naming both readings (see Errors). `pages_available` of page 1 says how many pages there are.
- Without `sort` the service's order is not a ranking: it follows the offer identifier, which usually means the oldest offers, grouped by investment. Give `sort` to browse a city. An unknown sort value gives no error ([open-questions.md](../../open-questions.md)).
- `status=all` can report a `total` larger than the active and the archived offers together; the service counts them unclearly (T72 in [open-questions.md](../../open-questions.md)).
- `per_page` in MCP is 10 and 50; the CLI also accepts 100.
- The maxima of `price_*` (99 999 999 PLN), `area_*` (9 999 m²) and `price_per_m2_*` (999 999 PLN) are range limits taken from the service client, not market data.
- The ranges, the price-drop filter, `status=archived` and the orders were checked on the city list of the redesigned service. On a district's list the live e2e suite confirmed the three ranges, the price-drop filter, `status=archived`, `sort` and `per_page` 10 and 50 ([P 2026-10-31]; T73 in [open-questions.md](../../open-questions.md)); `status=all` and the CLI's `--per-page 100` were not tried there. The slug of a district is made from its name [W], not taken from the service; it equals the service's own slug for all 72 districts of Warszawa, Kraków and Wrocław that were compared (see [pages-rsc.md](../../discovery/pages-rsc.md), the district list).
- No filter by number of rooms, floor or developer (the list has no such data); for a developer's investments use `get_developer` or `search_investments` with `developer_slug`.
- Primary-market asking prices, not transaction prices.

## Errors
| Situation | Message |
|---|---|
| A range reversed | `price_min (700000) jest większe niż price_max (500000); zamień je miejscami.` (likewise for `area_` and `price_per_m2_`) |
| A number or choice out of range | `Błędny argument narzędzia search_offers: price_per_m2_max musi być liczbą całkowitą z zakresu 0–999999 albo pusty, podano 1000000. Popraw i ponów; nic nie zostało wysłane.` (likewise `status`: `…musi być jedną z wartości active, archived, all albo pusty, podano "sold"…`, `sort`, `page`, `per_page`) |
| Unknown argument | `Nieznany argument narzędzia search_offers: 'max_price'. Dozwolone argumenty: city, price_min, price_max, area_min, area_max, price_per_m2_min, price_per_m2_max, district, price_dropped, status, sort, page, per_page. Popraw nazwy i ponów; nic nie zostało wysłane.` (several: `Nieznane argumenty narzędzia search_offers: 'developer', 'floor', 'rooms'. …`) |
| `city=polska` (also with `district`) | `city=polska nie działa przy wyszukiwaniu ofert: serwis nie ma jednej listy ofert całej Polski. Podaj city_slug jednego miasta z search_locations (np. warszawa); oferty kilku miast wyszukaj osobno dla każdego.` No request is sent. |
| Bad `city`: a name instead of a slug (e.g. `Kraków`), capital letters, an empty string | `city: oczekiwano city_slug jednego miasta (małe litery bez polskich znaków, np. warszawa, krakow), nie polska; slug podaje search_locations; podano 'Kraków'.` No request to the service; surrounding spaces are trimmed, a slug is lowercase ASCII letters, digits and hyphens. |
| `district` shorter than 2 or longer than 100 characters | `district: podaj nazwę dzielnicy (od 2 do 100 znaków) tak, jak zwraca ją search_locations (kind=district), np. Mokotów; podano 'W'.` (a blank `district` is "none", no error) |
| Unknown city (a valid slug the service does not know) | `Serwis nie zna miasta 'nieistniejace-miasto'. Podaj city_slug miasta z search_locations.` |
| Unknown district (also a name with no Latin letter or digit, then without a request) | `Serwis nie zna dzielnicy 'Nieistniejąca Dzielnica' w mieście 'warszawa'. Podaj nazwę dzielnicy tak, jak zwraca ją search_locations (kind=district, pole name), razem z city_slug jej miasta.` |
| `page` above 1 that the service does not find (a page past the last one, or an unknown city) | `Serwis nie ma strony 2 tej listy albo nie zna miasta 'sopot': lista może mieć mniej stron (pages_available podaje page=1); jeśli page=1 też zawiedzie, podaj city_slug miasta z search_locations.` (in a district search it names the district instead of the city) |
| The service moved or removed the list, or its data does not match | `Wyszukiwanie ofert w 'warszawa': Na stronie serwisu brakuje oczekiwanych danych. Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.` (in a district search the prefix is `Wyszukiwanie ofert w 'warszawa' (dzielnica 'Mokotów'): …`); a redirect or a removed route gives the "service changed" message of the [MCP overview](../README.md#errors) |
| STOP, other service error | As in the [MCP overview](../README.md#errors); service errors with the prefix `Wyszukiwanie ofert w '<city>': …` |

## Example
Call (default `per_page` 10, no filters):

```json
{"name": "search_offers", "arguments": {"city": "warszawa"}}
```

The result from `tests/golden/mcp/offers.json`: the items are the first 10 real offers of the list of Warszawa captured on 2026-10-31 (`tests/fixtures/rsc/offers_warszawa_20261031.rsc`), and `total` comes from that capture. The first 2 of 10 items are shown, the remaining 8 omitted:

```json
{
  "total": 11672,
  "returned": 10,
  "truncated": true,
  "page": 1,
  "per_page": 10,
  "pages_available": 20,
  "hint": "Pasujących ofert jest 11672, a można przejrzeć najwyżej 20 stron po 10 (200). Zawęź filtry (dzielnica, cena, metraż).",
  "list_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/mieszkania?perPage=10",
  "items": [
    {"offer_id": 4487, "investment_slug": "apartamenty-beethovena", "name": "A2", "price": 810660.0, "area_m2": 35.4, "price_per_m2": 22900.0, "status": "active", "investment_name": "Apartamenty Beethovena", "district": "Mokotów", "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/dom-development/apartamenty-beethovena", "developer_name": "Dom Development S.A.", "developer_slug": "dom-development", "last_price_change_kind": "increase", "last_price_change_pct": 6.51, "price_change_since_start_pct": 0.08},
    {"offer_id": 4527, "investment_slug": "apartamenty-beethovena", "name": "B36", "price": 1324896.0, "area_m2": 59.68, "price_per_m2": 22200.0, "status": "active", "investment_name": "Apartamenty Beethovena", "district": "Mokotów", "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/dom-development/apartamenty-beethovena", "developer_name": "Dom Development S.A.", "developer_slug": "dom-development", "last_price_change_kind": "increase", "last_price_change_pct": 6.73, "price_change_since_start_pct": 1.14}
  ]
}
```

A district: `{"city": "warszawa", "district": "Mokotów"}` (`tests/golden/mcp/offers_district.json`) sends one request, for `/ceny-ofertowe/warszawa/mokotow/mieszkania`, and gives `total` 959, the hint „Pasujących ofert jest 959, a można przejrzeć najwyżej 20 stron po 10 (200). Zawęź filtry (cena, metraż).” and `list_url` `https://deweloperuch.pl/ceny-ofertowe/warszawa/mokotow/mieszkania?perPage=10`.

With the new filters (`tests/golden/mcp/offers_new_filters.json`): `{"city": "warszawa", "price_per_m2_min": 12000, "price_per_m2_max": "20000", "district": "Mokotów", "price_dropped": true, "status": "archived", "sort": "biggest_drop"}` gives a `list_url` `https://deweloperuch.pl/ceny-ofertowe/warszawa/mokotow/mieszkania?filterPricePerM2=12000-20000&filterPriceChange=decrease&filterStatus=archived&sortBy=start_amount_difference_percent&sortOrder=asc&perPage=10`.

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/search_offers_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/search_offers_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/search_offers.py`, `src/deweloperuch_mcp/api/queries/offers_query.py`, `tests/snapshots/mcp_tools.json`_
