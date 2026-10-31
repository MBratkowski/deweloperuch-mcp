# `get_developer`
> Zwraca profil dewelopera: nazwę, podsumowanie jego aktywnych ofert (summary), inwestycje z aktywnymi ofertami (najpierw te z największą liczbą aktywnych ofert) i jego miasta (cities, od miasta z największą liczbą aktywnych ofert). Nie podaje strony www dewelopera. Użyj, gdy pytanie dotyczy dewelopera: gdzie i ile buduje, w jakich cenach. developer_slug weź z search_developers (po nazwie) albo z pól developer_slug w search_offers, get_investment, get_offer i get_market_statistics (top_developers). developer_url i investment_url to strony na deweloperuch.pl: podawaj je użytkownikowi jako linki.
>
> city zawęża summary i investments do jednego miasta (city_slug z search_locations albo z cities); domyślnie polska (cała Polska). cities obejmuje całą Polskę (gdy serwis nie podaje listy miast, tylko miasta inwestycji: wtedy hint). summary liczy narzędzie z inwestycji w zakresie city; summary.cities to liczba miast. Średnia cena oferty w jednym mieście: city=<city_slug>, pole summary.avg_price.
>
> Ograniczenia: najwyżej limit inwestycji (domyślnie 20); o pominięciu mówią investments_omitted (ile), truncated i hint. Pojedynczych ofert tu nie ma: oferty inwestycji daje get_investment.

Title: „Profil dewelopera”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `developer_slug` | string | yes | — | „developer_slug z search_developers (po nazwie) albo z pól developer_slug w search_offers, get_investment, get_offer, get_market_statistics (top_developers), np. atal.” |
| `city` | string | no | `polska` | „city_slug miasta z search_locations albo z cities wyniku get_developer (np. krakow), albo polska (domyślnie: cała Polska).” |
| `limit` | integer 1-100 | no | `20` | „Najwięcej inwestycji w wyniku (najpierw te z największą liczbą aktywnych ofert), 1–100, domyślnie 20. Inwestycja to 350–400 znaków wyniku; zwykle wystarcza domyślne 20.” |

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Description |
|---|---|
| `developer` | `developer_slug` and `name`. There is no `website` or `description`: the service does not give them (the description says „Nie podaje strony www dewelopera”). |
| `developer_url` | The developer profile on deweloperuch.pl for the chosen `city`: give it to the user as a link. |
| `city_slug` | The scope of `summary` and `investments`: the chosen city, or `polska` (the whole country). |
| `summary` | `active_offers`, `cities` (the number of cities), `avg_price`, `avg_area_m2`, `avg_price_per_m2` of the active offers in the scope. The tool computes it from the investments in the scope (see Data limitations). |
| `investments_total`, `investments_returned`, `investments_omitted`, `truncated`, `hint` | How many investments with active offers the developer has, how many were returned and omitted by `limit`. |
| `investments` | `investment_slug`, `name`, `city`, `city_slug`, `status`, `active_offers`, `total_offers` (with archived), averages of active offers, `investment_url`. Most active offers first. |
| `cities` | The developer's cities across the whole country, regardless of `city`: `city`, `city_slug`, `investments`, `active_offers`, `avg_price_per_m2`. Ordered by active offers, highest first, then by price per m², highest first. A city row has no average price (the average price of one city is `summary.avg_price` of a call with that `city`). |

The `hint` appears in three cases: the developer has no investment with active offers in the scope („Deweloper nie ma inwestycji z aktywnymi ofertami.”, or, for a city, „Deweloper nie ma inwestycji z aktywnymi ofertami w 'bialystok'. Spróbuj city=polska (cała Polska).”); a city call whose `cities` come from the investments only (see below): „Serwis nie podał listy miast dewelopera: cities to tylko miasta inwestycji w city (wszystkie: city=polska).”; and a truncated result: „Pokazano 20 z 42 inwestycji (najwięcej aktywnych ofert); pozostałe pokaże większy limit (najwyżej 100).” (appended to the first two).

## Data limitations
- Source is the developer profile page of the service (RSC): [pages-rsc.md](../../discovery/pages-rsc.md). It is an internal page of the service's UI, not an API (D21), and the redesign of 2026-10-29 changed it. The tool reads the redesigned page only.
- The page lists only the investments with active offers and has no totals and no developer website or description. So `summary` is computed by the tool from the investments in the scope: `avg_price` and `avg_area_m2` are the investments' means weighted by their active offers (the mean over every active offer), `avg_price_per_m2` weights the investments' price per m² by their active offers, as the service does. All are rounded (PLN, 0.01 m²), so `avg_price_per_m2` of one city can differ by 1 zł from that city's row in `cities`, and it is not `avg_price / avg_area_m2`. An unknown count of offers makes the averages absent.
- `cities` are the rows of the page's chart of the developer's cities. The page of a developer with investments in a single city has no such chart (seen on one developer, Ceres Development, [W] in general), so `cities` is then derived from the investments, and a call with a `city` says so in `hint`. The CLI header of that list is „Miasta dewelopera (tylko z inwestycji w [miasto]):”. For the whole list of the developer's cities call with `city=polska`.
- A price or area of 0 from the service means no value (a developer without active offers in a city): such a field is absent.
- Size: an investment is 350-400 characters; the whole-country call at the default `limit` 20 is 8 528 characters (`tests/golden/mcp/developer_whole_country.json`).
- Single offers are not here; use `get_investment` with an `investment_slug`.
- Asking prices of the primary market, not transaction prices.
- **Known limitation (not fixed in 0.2.0):** a developer the service knows, asked for in a city the service does not know, is answered with the "service changed" message instead of „Nie znaleziono dewelopera …”: the service's page for that pair has no developer data and no 404 marker (T39 in [open-questions.md](../../open-questions.md), [P 2026-10-31, live e2e], recorded as an expected failure). The message is then misleading: `city=polska` shows whether the developer exists. A repair is planned.

## Errors
| Situation | Message |
|---|---|
| The developer is unknown for `city=polska` (the service answers 200 with Next.js's 404 marker) | `Nie znaleziono dewelopera 'nieistniejacy-deweloper'. Slug dewelopera podaje search_developers (po nazwie) albo pole developer_slug w search_offers, get_investment i get_offer; city to city_slug z search_locations albo polska (cała Polska).` |
| The developer is unknown in a city | The same, with `w 'warszawa'` after the slug and the end `Albo deweloper nie ma w tym mieście aktywnych ofert: spróbuj city=polska.` |
| `developer_slug` not a slug (e.g. `ATAL`) | `developer_slug: oczekiwano slug dewelopera, np. atal; podają go search_developers, search_offers i search_investments (developer_slug); podano 'ATAL'.` |
| `city` not a slug (e.g. `Kraków`) | `city: oczekiwano slug miasta (np. warszawa) albo polska; slug podaje search_locations; podano 'Kraków'.` |
| `limit` outside 1-100 | `Błędny argument narzędzia get_developer: limit musi być liczbą całkowitą z zakresu 1–100, podano 0. Popraw i ponów; nic nie zostało wysłane.` |
| Unknown argument | `Nieznany argument narzędzia get_developer: 'slug'. Dozwolone argumenty: developer_slug, city, limit. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| Page without the data | `Deweloper 'atal' w 'warszawa': Na stronie serwisu brakuje oczekiwanych danych. Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.` |
| A redirect, a removed route or a 410 | `Deweloper 'atal': Narzędzie nie może pobrać tych danych, bo serwis przeniósł je w inne miejsce albo przestał je udostępniać. To nie musi znaczyć, że argumenty są błędne ani że szukanego obiektu nie ma. Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.` (the prefix has ` w '<city>'` for a city); see the [MCP overview](../README.md#errors) |
| STOP, other service error | As in the [MCP overview](../README.md#errors) |

## Example
Call:

```json
{"name": "get_developer", "arguments": {"developer_slug": "atal", "city": "warszawa"}}
```

The result from `tests/golden/mcp/developer_warszawa.json` (the real RSC page captured on 2026-10-31, `tests/fixtures/rsc/developer_atal_warszawa_20261031.rsc`; the first 2 of 4 investments):

```json
{
  "developer": {"developer_slug": "atal", "name": "ATAL S.A."},
  "developer_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal",
  "city_slug": "warszawa",
  "summary": {"active_offers": 60, "cities": 1, "avg_price": 993384.0, "avg_area_m2": 62.3, "avg_price_per_m2": 16110.0},
  "investments_total": 4, "investments_returned": 4, "investments_omitted": 0, "truncated": false,
  "investments": [
    {"investment_slug": "warszawska-58a", "name": "Warszawska 58A", "city": "Warszawa", "city_slug": "warszawa", "status": "active", "active_offers": 32, "total_offers": 73, "avg_price": 966208.84, "avg_area_m2": 59.93, "avg_price_per_m2": 16123.0, "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/warszawska-58a"},
    {"investment_slug": "nowy-targowek-vi", "name": "Nowy Targówek VI", "city": "Warszawa", "city_slug": "warszawa", "status": "active", "active_offers": 21, "total_offers": 75, "avg_price": 1073611.14, "avg_area_m2": 60.84, "avg_price_per_m2": 17646.0, "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi"}
  ],
  "cities": [{"city": "Kraków", "city_slug": "krakow", "investments": 7, "active_offers": 705, "avg_price_per_m2": 13757.0}, {"city": "Poznań", "city_slug": "poznan", "investments": 4, "active_offers": 704, "avg_price_per_m2": 11864.0}, "… (the other 12 cities of the whole country, omitted here)"]
}
```

A developer in one city whose page has no chart of cities (`{"developer_slug": "ceres-development", "city": "warszawa"}`, `tests/golden/mcp/developer_single_city.json`) gets `cities` with that one city, derived from its investment, and the `hint` „Serwis nie podał listy miast dewelopera: cities to tylko miasta inwestycji w city (wszystkie: city=polska).”

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_developer_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_developer_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_developer.py`, `src/deweloperuch_mcp/models/developer_profile.py`, `tests/snapshots/mcp_tools.json`_
