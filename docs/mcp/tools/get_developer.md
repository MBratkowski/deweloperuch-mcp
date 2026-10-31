# `get_developer`
> Zwraca profil dewelopera: nazwę, stronę www, podsumowanie jego aktywnych ofert (summary: active_offers, cities, avg_price, avg_area_m2, avg_price_per_m2), inwestycje z aktywnymi ofertami (najpierw te z największą liczbą aktywnych ofert: investment_slug, name, city, active_offers, total_offers razem z archiwalnymi, średnie aktywnych ofert, investment_url) i jego miasta (cities: inwestycje, aktywne oferty, średnia cena i cena za m²). Użyj, gdy pytanie dotyczy dewelopera: gdzie i ile buduje, w jakich cenach. developer_slug weź z search_developers (po nazwie) albo z pól developer_slug w search_offers, get_investment, get_offer. developer_url i investment_url to strony na deweloperuch.pl: podawaj je użytkownikowi jako linki.
>
> city zawęża summary i investments do jednego miasta (city_slug z search_locations); domyślnie polska (cała Polska). cities zawsze obejmuje całą Polskę.
>
> Ograniczenia: najwyżej limit inwestycji (domyślnie 20); investments_omitted i truncated mówią, ile pominięto. Pojedynczych ofert tu nie ma: oferty inwestycji daje get_investment.

Title: „Profil dewelopera”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `developer_slug` | string | yes | — | „developer_slug z search_developers (po nazwie) albo z pól developer_slug w search_offers, get_investment, get_offer, np. atal.” |
| `city` | string | no | `polska` | „city_slug miasta z search_locations (np. krakow) albo polska (domyślnie: cała Polska).” |
| `limit` | integer 1-100 | no | `20` | „Najwięcej inwestycji w wyniku (najpierw te z największą liczbą aktywnych ofert), 1–100, domyślnie 20. Inwestycja to ok. 350 znaków wyniku; zwykle wystarcza domyślne 20.” |

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Description |
|---|---|
| `developer` | `developer_slug`, `name`, optionally `website`, `description`. |
| `developer_url` | The developer profile on deweloperuch.pl for the chosen `city`: give it to the user as a link. |
| `city_slug` | The city the profile is narrowed to (`polska` = the whole country). |
| `summary` | `active_offers`, `cities`, `avg_price`, `avg_area_m2`, `avg_price_per_m2` (active offers, for the chosen `city`). |
| `investments_total`, `investments_returned`, `investments_omitted`, `truncated`, `hint` | How many investments with active offers the developer has, how many were returned and omitted by `limit`. |
| `investments` | `investment_slug`, `name`, `city`, `city_slug`, `status`, `active_offers`, `total_offers` (with archived), averages of active offers, `investment_url`. Most active offers first. |
| `cities` | The developer's cities across the whole country (investments, active offers, average price and price per m²), regardless of `city`. |

## Data limitations
- Source is the developer profile page of the service (RSC): [pages-rsc.md](../../discovery/pages-rsc.md). Its consistency between the `polska` and city variants was verified on 2026-10-13 (fixtures `developer_atal_*.rsc`).
- Since the service's redesign of 2026-10-29 the page lists only the investments with active offers and has no totals: `summary` is computed from those investments (sums, averages weighted by active offers, which gives the page's own averages per city), and `developer` has no `website` or `description`. A city's `avg_price` is known only when the profile lists that city's investments, so on a city profile the other cities have none.
- Single offers are not here; use `get_investment` with an `investment_slug`.
- Asking prices of the primary market, not transaction prices.

## Errors
| Situation | Message |
|---|---|
| The developer is unknown (the service answers 200 with „Deweloper nie znaleziony”) | `Nie znaleziono dewelopera 'nieistniejacy-deweloper' w 'warszawa'. Slug dewelopera podaje search_developers (po nazwie) albo pole developer_slug w search_offers, get_investment i get_offer; city to city_slug z search_locations albo polska (cała Polska).` |
| `developer_slug` not a slug (e.g. `ATAL`) | `developer_slug: oczekiwano slug dewelopera, np. atal; podają go search_developers, search_offers i search_investments (developer_slug); podano 'ATAL'.` |
| `city` not a slug (e.g. `Kraków`) | `city: oczekiwano slug miasta (np. warszawa) albo polska; slug podaje search_locations; podano 'Kraków'.` |
| `limit` outside 1-100 | `Błędny argument narzędzia get_developer: limit musi być liczbą całkowitą z zakresu 1–100, podano 0. Popraw i ponów; nic nie zostało wysłane.` |
| Unknown argument | `Nieznany argument narzędzia get_developer: 'slug'. Dozwolone argumenty: developer_slug, city, limit. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| Page without the data | `Deweloper 'atal' w 'warszawa': Na stronie serwisu brakuje oczekiwanych danych. Serwis mógł się zmienić po aktualizacji: ponawianie nie pomoże, zgłoś to użytkownikowi.` |
| STOP, service error | As in the [MCP overview](../README.md#errors) |

## Example
Call:

```json
{"name": "get_developer", "arguments": {"developer_slug": "atal", "city": "warszawa"}}
```

The result from `tests/golden/mcp/developer_warszawa.json` (the real RSC fixture; the first 2 of 4 investments):

```json
{
  "developer": {"developer_slug": "atal", "name": "ATAL S.A."},
  "developer_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal",
  "city_slug": "warszawa",
  "summary": {"active_offers": 69, "cities": 1, "avg_price": 1001962.0, "avg_area_m2": 62.7, "avg_price_per_m2": 16111.0},
  "investments_total": 4, "investments_returned": 4, "investments_omitted": 0, "truncated": false,
  "investments": [
    {"investment_slug": "warszawska-58a", "name": "Warszawska 58A", "city": "Warszawa", "city_slug": "warszawa", "status": "active", "active_offers": 36, "total_offers": 73, "avg_price": 958592.58, "avg_area_m2": 59.67, "avg_price_per_m2": 16064.0, "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/warszawska-58a"},
    {"investment_slug": "nowy-targowek-vi", "name": "Nowy Targówek VI", "city": "Warszawa", "city_slug": "warszawa", "status": "active", "active_offers": 24, "total_offers": 75, "avg_price": 1098682.92, "avg_area_m2": 62.31, "avg_price_per_m2": 17631.0, "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi"}
  ],
  "cities": [{"city": "Poznań", "city_slug": "poznan", "investments": 4, "active_offers": 736, "avg_price": 709389.0, "avg_price_per_m2": 11823.0}, "… (the other cities of the whole country, omitted here)"]
}
```

The whole-country call (`{"developer_slug": "atal"}`) is about 8 800 characters at the default `limit` 20.

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_developer_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_developer_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_developer.py`, `tests/snapshots/mcp_tools.json`_
