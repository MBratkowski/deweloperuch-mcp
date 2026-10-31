# `get_market_statistics`
> Zwraca statystyki rynku ofert deweloperskich w jednym mieście: liczbę ofert, inwestycji i deweloperów, rozkład cen (PLN), cen za m² (PLN/m²) i metraży (m²) jako min, p25, median, p75 i max oraz największych deweloperów wg liczby ofert (developer_name, developer_slug, offers, investments, median_price_per_m2, developer_url). Opcjonalnie tylko oferty z zakresu ceny i metrażu. Użyj, gdy pytanie dotyczy rynku miasta (typowe ceny, kto ma najwięcej ofert), a nie konkretnych mieszkań (search_offers; inwestycje dewelopera daje get_developer).
>
> Ograniczenia: tylko aktywne oferty (bez archiwalnych) i tylko jedno miasto (city_slug z search_locations; polska nie działa). Liczby to stan na dzień z pola wyniku as_of i mogą się nieco różnić od total w search_offers. Pojedynczych ofert tu nie ma: list_url to lista tych ofert na deweloperuch.pl z tymi samymi filtrami, a developer_url profil dewelopera: podawaj je użytkownikowi jako linki.

Title: „Statystyki rynku miasta”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `city` | string | yes | — | „city_slug jednego miasta z search_locations, np. krakow (nie polska).” |
| `price_min` | integer 0-99 999 999 | no | none | „Najniższa cena oferty w PLN.” |
| `price_max` | integer 0-99 999 999 | no | none | „Najwyższa cena oferty w PLN.” |
| `area_min` | integer 0-9 999 | no | none | „Najmniejszy metraż w m².” |
| `area_max` | integer 0-9 999 | no | none | „Największy metraż w m².” |
| `top_developers` | integer 1-30 | no | `10` | „Ilu największych deweloperów pokazać, 1–30, domyślnie 10.” |

`price_min` greater than `price_max` (likewise for area) is rejected before any request. Argument rules: [MCP overview](../README.md#argument-rules).

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Description |
|---|---|
| `city_slug` | The city. |
| `as_of` | The day the service gave its offers for (`YYYY-MM-DD`, can be yesterday's): state it next to the numbers. |
| `offers`, `investments`, `developers` | Counts of the active offers matching the filters, and of their investments and developers. |
| `price`, `price_per_m2`, `area_m2` | The distribution as `min`, `p25`, `median`, `p75`, `max` (PLN, PLN/m², m²). Missing when nothing matches. |
| `top_developers` | The largest developers by number of offers: `developer_name`, `developer_slug`, `offers`, `investments`, `median_price_per_m2`, `developer_url`. `developer_slug` is for `get_developer` (with `city` = this `city_slug`). |
| `developers_returned`, `developers_omitted`, `truncated`, `hint` | How many developers were shown and omitted; `hint` also explains an empty result. |
| `list_url` | The offer list on deweloperuch.pl with the same filters: give it to the user as a link. |

## Data limitations
- The statistics are computed in the process from the service's bulk list of the city's active offers, `GET /api/map/offer-snapshot/{city}` ([decisions.md](../../decisions.md), D20; it replaces the retired `offers/city-sales`): the list itself never reaches the output. The route is an internal one and may change without notice. Only active offers; `polska` is refused before any request. The price and area filters are applied to the list in the process.
- `as_of` is the day of the list, so it is the date to show, not the date of the request: the CDN can serve an old copy (about ten hours old on 2026-10-31, `age` 37 703 s; the route sends `s-maxage=3600`, [endpoints.md](../../discovery/endpoints.md), `map/offer-snapshot`). The package itself keeps a reply in memory for at most 300 s ([configuration](../../configuration.md#package-client)), so a repeat after a few minutes is a new request.
- The counts agree with `total` of an unfiltered `search_offers` of the same city when both are from the same moment (Warszawa on 2026-10-31: 11 672 in both), but the two come from different routes and copies, so they can differ slightly.
- A developer's name comes with its investment in the list; `top_developers[].developer_name` is absent when the list gives none.
- Asking prices of the primary market, not transaction prices.
- Size: 5 developers about 1 600 characters (`tests/golden/mcp/market_warszawa_filters.json`).

## Errors
| Situation | Message |
|---|---|
| `city=polska` | `city: statystyki rynku są tylko dla jednego miasta; podaj city_slug miasta z search_locations (np. warszawa), a nie polska; podano 'polska'.` |
| `city` not a city slug (e.g. `Kraków`) | `city: oczekiwano slug jednego miasta z search_locations: małe litery, bez polskich znaków (np. warszawa, sopot; nie polska); podano 'Kraków'.` No request is sent. |
| Unknown city (the service answers a JSON 404) | `Serwis nie zna miasta 'nieistniejace-miasto' albo nie ma w nim ofert. Podaj city_slug z search_locations (miejscowości z offer_count=0 nie mają statystyk; statystyki rynku są tylko dla jednego miasta).` |
| `area_min` > `area_max` (likewise for price) | `area_min (60) jest większe niż area_max (40); zamień je miejscami.` |
| `top_developers` outside 1-30 | `Błędny argument narzędzia get_market_statistics: top_developers musi być liczbą całkowitą z zakresu 1–30, podano 31. Popraw i ponów; nic nie zostało wysłane.` |
| Nothing matches the filters | Not an error: `offers=0` and a `hint`: `Brak aktywnych ofert spełniających kryteria w 'sopot'. Sprawdź slug miasta (search_locations) i poluzuj filtry (cena, metraż).` |
| The route was moved or removed (a redirect, an HTML 404, a 410) | `Statystyki rynku w 'sopot': Narzędzie nie może pobrać tych danych, bo serwis przeniósł je w inne miejsce albo przestał je udostępniać. To nie musi znaczyć, że argumenty są błędne ani że szukanego obiektu nie ma. Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.` |
| The list does not match the contract | `Statystyki rynku w 'sopot': Dane z serwisu nie pasują do kontraktu klienta (inny format). Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.` |
| Unknown argument | `Nieznany argument narzędzia get_market_statistics: '…'. Dozwolone argumenty: city, price_min, price_max, area_min, area_max, top_developers. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| STOP, other service error | As in the [MCP overview](../README.md#errors) |

## Example
Call:

```json
{"name": "get_market_statistics", "arguments": {"city": "sopot"}}
```

The result from `tests/golden/mcp/market_sopot.json` (the real list of Sopot captured on 2026-10-31, `tests/fixtures/api/offer_snapshot_sopot_20261031.json`):

```json
{
  "city_slug": "sopot", "as_of": "2026-10-31", "offers": 8, "investments": 2, "developers": 1,
  "price": {"min": 1261250, "p25": 1534860, "median": 1616858, "p75": 1661530, "max": 3735107},
  "price_per_m2": {"min": 24289, "p25": 25224, "median": 25808, "p75": 26383, "max": 39115},
  "area_m2": {"min": 48.73, "p25": 58.11, "median": 64.69, "p75": 66.02, "max": 95.49},
  "top_developers": [{"developer_slug": "invest-komfort-spolka-akcyjna", "developer_name": "Invest Komfort Spółka Akcyjna Sp.K.", "offers": 8, "investments": 2, "median_price_per_m2": 25808, "developer_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna"}],
  "developers_returned": 1, "developers_omitted": 0, "truncated": false,
  "list_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/mieszkania?perPage=10"
}
```

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_market_statistics_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_market_statistics_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_market_statistics.py`, `src/deweloperuch_mcp/api/adapters/offer_snapshot_api.py`, `tests/snapshots/mcp_tools.json`_
