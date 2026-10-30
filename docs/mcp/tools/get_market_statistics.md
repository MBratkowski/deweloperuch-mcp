# `get_market_statistics`
> Zwraca statystyki rynku ofert deweloperskich w jednym mieście: liczbę ofert, inwestycji i deweloperów, rozkład cen (PLN), cen za m² (PLN/m²) i metraży (m²) jako min, p25, median, p75 i max oraz największych deweloperów wg liczby ofert (developer_slug, offers, investments, median_price_per_m2, developer_url; developer_slug to identyfikator, a nazwę dewelopera daje get_developer). Opcjonalnie tylko oferty z zakresu ceny i metrażu. Użyj, gdy pytanie dotyczy rynku miasta (typowe ceny, kto ma najwięcej ofert), a nie konkretnych mieszkań (search_offers).
>
> Ograniczenia: tylko aktywne oferty (bez archiwalnych) i tylko jedno miasto (city_slug z search_locations; polska nie działa). Liczby mogą się nieco różnić od total w search_offers. Pojedynczych ofert tu nie ma: list_url to lista tych ofert na deweloperuch.pl z tymi samymi filtrami, a developer_url profil dewelopera: podawaj je użytkownikowi jako linki.

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
| `offers`, `investments`, `developers` | Counts of the active offers matching the filters, and of their investments and developers. |
| `price`, `price_per_m2`, `area_m2` | The distribution as `min`, `p25`, `median`, `p75`, `max` (PLN, PLN/m², m²). Missing when nothing matches. |
| `top_developers` | The largest developers by number of offers: `developer_slug`, `offers`, `investments`, `median_price_per_m2`, `developer_url`. A name comes from `get_developer`. |
| `developers_returned`, `developers_omitted`, `truncated`, `hint` | How many developers were shown and omitted; `hint` also explains an empty result. |
| `list_url` | The offer list on deweloperuch.pl with the same filters: give it to the user as a link. |

## Data limitations
- The statistics are computed in the process from the service's compact list of the city's active offers ([decisions.md](../../decisions.md)): the list itself never reaches the output. Only active offers; `polska` is refused before any request.
- The counts can differ slightly from `total` in `search_offers` (Kraków: 7 325 vs 7 307 on 2026-10-13, verified; Wrocław: 5 836 in both on 2026-10-30). The channel and its limits: [endpoints.md](../../discovery/endpoints.md) (`map/offer-snapshot`; until the service's redesign of 2026-10-29 `offers/city-sales`).
- Asking prices of the primary market, not transaction prices.
- A repeat within 5 minutes comes from the cache; the service's cache headers for this channel are not checked yet ([configuration](../../configuration.md#package-client)).

## Errors
| Situation | Message |
|---|---|
| `city=polska` | `city: statystyki rynku są tylko dla jednego miasta; podaj city_slug miasta z search_locations (np. warszawa), a nie polska; podano 'polska'.` |
| Unknown city | `Serwis nie zna miasta 'nieznane'. Podaj city_slug z search_locations (statystyki rynku są tylko dla jednego miasta).` |
| The service no longer has the data source (HTML 404) | `Statystyki rynku w 'sopot': Źródło danych tego narzędzia nie jest już dostępne w serwisie (HTTP 404). Serwis mógł się zmienić po aktualizacji: ponawianie nie pomoże, zgłoś to użytkownikowi.` |
| `area_min` > `area_max` (likewise for price) | `area_min (60) jest większe niż area_max (40); zamień je miejscami.` |
| `top_developers` outside 1-30 | `Błędny argument narzędzia get_market_statistics: top_developers musi być liczbą całkowitą z zakresu 1–30, podano 31. Popraw i ponów; nic nie zostało wysłane.` |
| Nothing matches the filters | Not an error: `offers=0` and a `hint`: `Brak aktywnych ofert spełniających kryteria w 'sopot'. Sprawdź slug miasta (search_locations) i poluzuj filtry (cena, metraż).` |
| Unknown argument | `Nieznany argument narzędzia get_market_statistics: '…'. Dozwolone argumenty: city, price_min, price_max, area_min, area_max, top_developers. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| STOP, service error | As in the [MCP overview](../README.md#errors) |

## Example
Call:

```json
{"name": "get_market_statistics", "arguments": {"city": "sopot"}}
```

The result from `tests/golden/mcp/market_sopot.json`:

```json
{
  "city_slug": "sopot", "offers": 6, "investments": 2, "developers": 1,
  "price": {"min": 1399205, "p25": 1588164, "median": 1616463, "p75": 1646230, "max": 1679796},
  "price_per_m2": {"min": 22931, "p25": 23559, "median": 24533, "p75": 25309, "max": 27037},
  "area_m2": {"min": 56.5, "p25": 61.21, "median": 67.0, "p75": 68.7, "max": 69.5},
  "top_developers": [{"developer_slug": "invest-komfort-spolka-akcyjna", "offers": 6, "investments": 2, "median_price_per_m2": 24533, "developer_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna"}],
  "developers_returned": 1, "developers_omitted": 0, "truncated": false,
  "list_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/mieszkania?page=1&perPage=10"
}
```

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_market_statistics_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_market_statistics_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_market_statistics.py`, `tests/snapshots/mcp_tools.json`_
