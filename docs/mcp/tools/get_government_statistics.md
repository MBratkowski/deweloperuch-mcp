# `get_government_statistics`
> Zwraca oficjalne statystyki GUS i NBP jako szeregi czasowe dla Polski, agregatu miast albo miasta na prawach powiatu: mieszkania oddane do użytkowania i rozpoczęte (razem, wg form budownictwa, na wynajem), średnią powierzchnię mieszkań oddanych przez deweloperów, średnie ceny m² wg NBP (rynek pierwotny i wtórny, ceny ofertowe i transakcyjne), stopę bezrobocia, wynagrodzenia, demografię i ludność. Użyj jako kontekstu rynku; ofert i cen konkretnych mieszkań tu nie ma (search_offers).
>
> Zwraca periods (od najstarszego) i series (series_id, label, unit, values wyrównane z periods; null = brak danych) oraz frequency, source, total, returned, truncated, available_from, note i stats_url (sekcja strony na deweloperuch.pl: podaj ją użytkownikowi jako link).
>
> Ograniczenia: domyślnie ostatnie 12 okresów; truncated=true znaczy, że są starsze (zwiększ periods, najwyżej 120). nbp_prices: tylko 17 dużych miast i 3 agregaty, nie polska. Nie każdy zestaw jest dostępny dla każdej lokalizacji (błąd wskaże, co podać); dane GUS i NBP są publikowane z opóźnieniem, ostatni okres bywa sprzed kilku tygodni lub miesięcy. Przeczytaj note: ostatni okres bywa niepełny.

Title: „Statystyki GUS i NBP”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Official GUS and NBP statistics as time series: market context, not offers. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `location` | string | yes | | `polska`, an aggregate (`7-miast`, `10-miast`, `6-miast-bez-warszawy`) or one of 66 cities with county rights: lowercase, no Polish letters, hyphens for spaces (`warszawa`, `bielsko-biala`; Jastrzębie-Zdrój is `jastrzebie`). Capitals are accepted. Not for districts or smaller towns. |
| `dataset` | enum | yes | | `dwellings_quarterly`, `dwellings_monthly`, `average_area`, `demography`, `population`, `unemployment`, `wages`, `nbp_prices`. The frequency is returned in `frequency`. |
| `periods` | integer 1-120 | no | 12 | How many latest periods (years, quarters or months), 1–120. `null` means 12. A digit string is accepted ([argument rules](../README.md#argument-rules)). |

Datasets: `dwellings_quarterly` / `dwellings_monthly` (dwellings completed and started: total, by form, for rent), `average_area` (m², yearly), `demography` (births, deaths, natural increase; monthly for `polska`, yearly for cities), `population` (yearly), `unemployment` (registered, %, monthly), `wages` (gross monthly, PLN; monthly for `polska`, yearly for cities; the ratio to the national average only from pages of the build before the redesign of 2026-10-29), `nbp_prices` (PLN/m², primary and secondary market, asking and transaction prices, quarterly).

## Result
`structuredContent` (also compact JSON in the content): `location_slug`, `location_name`, `dataset`, `title`, `source` (`GUS` or `NBP`), `frequency` (`month`, `quarter`, `year`), `total` (periods available), `returned`, `truncated`, `available_from`, `hint`, `stats_url` (the section of the service's statistics page, to show to the user), optional `note`, `periods` (oldest first) and `series` (`series_id`, `label`, `unit`, `values` aligned with `periods`; `null` = no data). `truncated=true` means older periods exist; raise `periods` (max 120).

Size: the default 12 periods is at most about 3 000 characters; 120 periods of the widest dataset (`dwellings_monthly` of `polska`, 15 series) about 10 500.

## Data limitations
- `nbp_prices` exists only for 17 cities and the 3 aggregates, not for `polska`.
- Not every dataset exists for every location; the error says what to give.
- GUS and NBP publish with a delay: the latest period can be weeks or months old (2026-10-11 samples: months up to 2026-08, NBP up to 2026-Q2). The last quarter of dwellings can hold only 2 of 3 months, which `note` states.
- Source: the statistics page of the service as RSC ([pages-rsc](../../discovery/pages-rsc.md), [open-questions](../../open-questions.md)). Whether `search_locations` slugs always equal the statistics slugs is not confirmed.

## Errors
| Situation | Message |
|---|---|
| Unknown location | `Serwis nie ma statystyk rządowych dla lokalizacji 'nieistniejaca-lokalizacja'. Podaj polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo slug miasta na prawach powiatu bez polskich znaków, np. warszawa, krakow. Jeśli nie znasz sluga miasta, spróbuj city_slug z search_locations (zwykle jest taki sam, ale nie zawsze, np. dla Jastrzębia-Zdroju użyj jastrzebie). Statystyki są tylko dla miast na prawach powiatu.` |
| `nbp_prices` for `polska` | `NBP nie podaje jednej ceny dla całej Polski, tylko dla miast i agregatów. Podaj jedną z lokalizacji: warszawa, 10-miast, 7-miast, …` (the locations of the page's NBP grid) |
| Unknown `dataset` or `periods` outside 1–120 | `Błędny argument narzędzia get_government_statistics: periods musi być liczbą całkowitą z zakresu 1–120, podano 121. Popraw i ponów; nic nie zostało wysłane.` (for `dataset`: `… dataset musi być jedną z wartości dwellings_quarterly, …, podano "prices" …`) |
| Unknown argument | `Nieznany argument narzędzia get_government_statistics: '…'. Dozwolone argumenty: location, dataset, periods. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| Page without the data | `Statystyki rządowe dla 'warszawa': Na stronie serwisu brakuje oczekiwanych danych. Serwis mógł się zmienić po aktualizacji: ponawianie nie pomoże, zgłoś to użytkownikowi.` |
| 5xx, network | `Statystyki rządowe dla '<location>': Serwis odpowiedział błędem HTTP 503. Nic nie ponawiam; spróbuj później.` |
| 401, 403, 429, challenge | `STOP: …` ([errors](../README.md#errors)) |

## Example
Call:
```json
{"location": "polska", "dataset": "unemployment"}
```
Result (`tests/golden/mcp/stats_polska_unemployment.json`, shortened to 3 of 12 periods):
```json
{
  "location_slug": "polska", "location_name": "Polska",
  "dataset": "unemployment", "title": "Stopa bezrobocia rejestrowanego",
  "source": "GUS", "frequency": "month",
  "total": 188, "returned": 12, "truncated": true, "available_from": "2011-01",
  "hint": "Pokazano ostatnie 12 z 188 okresów (dane od 2011-01); starsze pokaże większe periods (najwyżej 120).",
  "stats_url": "https://deweloperuch.pl/statystyki/polska/dane-rzadowe#gus-bezrobocie",
  "periods": ["2025-09", "2025-10", "...", "2026-08"],
  "series": [{"series_id": "rate", "label": "Stopa bezrobocia", "unit": "%",
              "values": [5.6, 5.6, "...", 5.8]}]
}
```

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_government_statistics_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_government_statistics_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_government_statistics.py`, `tests/snapshots/mcp_tools.json`, `tests/golden/mcp/stats_*.json`_
