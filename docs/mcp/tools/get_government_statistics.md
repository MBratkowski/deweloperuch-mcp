# `get_government_statistics`
> Zwraca oficjalne statystyki GUS, NBP i Eurostatu (demografia Polski) jako szeregi czasowe dla Polski, agregatu miast albo miasta na prawach powiatu: mieszkania oddane i rozpoczęte, średnią powierzchnię mieszkań deweloperskich, ceny m² wg NBP, bezrobocie, wynagrodzenia, demografię i ludność (parametr dataset). Ofert mieszkań tu nie ma (search_offers), ceny z rejestru RCN daje get_transaction_statistics, a porównanie wielu miast w jednym okresie rank_locations z indicator.
>
> Zwraca periods (od najstarszego) i series (series_id, label, unit, values wyrównane z periods; null = brak danych) oraz frequency, source, total, returned, truncated, available_from, note i stats_url (sekcja strony na deweloperuch.pl: podaj ją użytkownikowi jako link).
>
> Ograniczenia: domyślnie ostatnie 12 okresów; truncated=true: są starsze (zwiększ periods, najwyżej 120). nbp_prices: tylko 3 agregaty i część dużych miast (np. warszawa, krakow), nie polska. Nie każdy zestaw jest dostępny dla każdej lokalizacji (błąd wskaże, co podać); dane GUS i NBP są publikowane z opóźnieniem: ostatni okres bywa sprzed kilku tygodni lub miesięcy, dla demografii Polski nawet roku. Przeczytaj note: ostatni okres bywa niepełny.

Title: „Statystyki GUS, NBP i Eurostatu”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Official GUS, NBP and Eurostat statistics as time series: market context, not offers. To compare many cities in one period (unemployment, wages, dwellings, NBP prices), use [`rank_locations`](rank_locations.md) with `indicator`: its values equal the series of this tool for the same period. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `location` | string | yes | | „polska (cała Polska), agregat 7-miast, 10-miast albo 6-miast-bez-warszawy, albo jedno z 66 miast na prawach powiatu: nazwa małymi literami bez polskich znaków, z myślnikami zamiast spacji, np. warszawa, krakow, lodz, bielsko-biala, zielona-gora, jastrzebie-zdroj. Dane są tylko dla 66 miast na prawach powiatu, a nie dla dzielnic i mniejszych miejscowości.” Capitals are accepted. Jastrzębie-Zdrój is `jastrzebie-zdroj`. |
| `dataset` | enum | yes | | `dwellings_quarterly`, `dwellings_monthly`, `average_area`, `demography`, `population`, `unemployment`, `wages`, `nbp_prices`. Schema text: „dwellings_quarterly: mieszkania oddane do użytkowania i rozpoczęte (razem, wg form budownictwa, na wynajem), kwartalnie; dwellings_monthly: to samo miesięcznie; average_area: średnia powierzchnia mieszkania oddanego przez deweloperów (m², rocznie); demography: urodzenia żywe, zgony, przyrost naturalny (dla Polski miesięcznie wg Eurostatu, dla miast rocznie wg GUS); population: ludność, kobiety i mężczyźni (rocznie); unemployment: stopa bezrobocia rejestrowanego (%, miesięcznie); wages: przeciętne miesięczne wynagrodzenie brutto w PLN (dla Polski miesięcznie, dla miast rocznie, czasem z relacją do średniej krajowej); nbp_prices: średnie ceny m² wg NBP, rynek pierwotny i wtórny, ofertowe i transakcyjne (PLN/m², kwartalnie). Częstotliwość zwraca pole frequency. Agregat 7-miast nie ma wages ani unemployment (są dla miast i polska).” |
| `periods` | integer 1-120 | no | 12 | How many latest periods (years, quarters or months), 1–120. `null` means 12. A digit string is accepted ([argument rules](../README.md#argument-rules)). Schema text: „Ile ostatnich okresów zwrócić (lat, kwartałów albo miesięcy), 1–120, domyślnie 12. Najszerszy zestaw (mieszkania, 15 szeregów) przy 120 miesiącach to ok. 10 tys. znaków. Dla trendów bierz dane roczne/kwartalne; miesięczne 120 okresów tylko, gdy użytkownik o to prosi.” |

Datasets: `dwellings_quarterly` / `dwellings_monthly` (dwellings completed and started: total, by form, for rent), `average_area` (m², yearly), `demography` (births, deaths, natural increase; monthly for `polska` from Eurostat, yearly for cities from GUS), `population` (yearly), `unemployment` (registered, %, monthly), `wages` (gross monthly, PLN; monthly for `polska`, yearly for cities; a city's yearly wages also carry the series `relative_to_poland`, the ratio to the national average, which the tool reads from the notes of the page's chart), `nbp_prices` (PLN/m², primary and secondary market, asking and transaction prices, quarterly).

## Result
`structuredContent` (also compact JSON in the content): `location_slug`, `location_name`, `dataset`, `title`, `source` (`GUS`, `NBP` or `Eurostat`: Poland's demography), `frequency` (`month`, `quarter`, `year`), `total` (periods available), `returned`, `truncated`, `available_from`, `hint`, `stats_url` (the section of the service's statistics page, to show to the user), optional `note`, `periods` (oldest first) and `series` (`series_id`, `label`, `unit`, `values` aligned with `periods`; `null` = no data). `truncated=true` means older periods exist; raise `periods` (max 120).

`stats_url` is `https://deweloperuch.pl/statystyki/{location}/dane-rzadowe#{section}`. The section is an id taken from that location's own list of sections (`govSections`), because the ids differ per location: Poland's demography is `eurostat-demografia`, a city's `gus-demografia`; the NBP prices are `nbp`.

`note` is set when the last period may be incomplete: the last quarter of `dwellings_quarterly` when the monthly data does not cover all three months, and, for `average_area`, the last year („Ostatni rok (2026) bywa niepełny: GUS dopisuje go kwartałami, więc porównuj go ostrożnie z pełnymi latami.”).

Size: the default 12 periods is at most about 3 000 characters; 120 periods of the widest dataset (`dwellings_monthly` of `polska`, 15 series) about 10 600.

## Data limitations
- `nbp_prices` exists only for the 3 aggregates and part of the large cities (for example `warszawa`, `krakow`), not for `polska`. The error names aggregates and some large cities as examples, not as the full list.
- Not every dataset exists for every location; the error says what to give. The aggregate `7-miast` has no `wages` or `unemployment` (the schema says so; the error names the dataset and the location and what to give instead).
- GUS, NBP and Eurostat publish with a delay: the latest period can be weeks or months old, and the monthly demography of `polska` (Eurostat) about a year (the capture of 2026-10-31 ends with 2025-09). The last quarter of dwellings can hold only 2 of 3 months and the last year of `average_area` is partial; `note` states both.
- Source: the statistics page of the service as RSC, `/statystyki/{location}/dane-rzadowe` ([pages-rsc](../../discovery/pages-rsc.md), [open-questions](../../open-questions.md)). The page is an internal page of the service's UI (D21) and the redesign of 2026-10-29 changed it: 4 of the 8 datasets (`average_area`, `demography`, `unemployment`, `wages`) are now read from the page's chart props, with the same values as before; the other 4 from its data props. Whether `search_locations` slugs always equal the statistics slugs is not confirmed; the accepted locations are the page's own list: `polska`, 3 aggregates and 66 cities.
- Not found or changed: the page of an unknown slug answers 404 with its own flight stream, which is "not found". The same answer for `polska`, an aggregate or one of the 66 cities (a known location) cannot mean an unknown place, so it is read as a changed service.

## Errors
| Situation | Message |
|---|---|
| Unknown location | `Serwis nie ma statystyk rządowych dla lokalizacji 'nieistniejaca-lokalizacja'. Podaj polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo slug miasta na prawach powiatu: nazwa małymi literami bez polskich znaków, z myślnikami zamiast spacji, np. warszawa, krakow, jastrzebie-zdroj. Jeśli nie znasz sluga miasta, spróbuj city_slug z search_locations (zwykle jest taki sam). Statystyki są tylko dla miast na prawach powiatu.` |
| A known location (`polska`, an aggregate, one of the 66 cities) answers 404 | `Statystyki rządowe dla 'polska': Narzędzie nie może pobrać tych danych, bo serwis przeniósł je w inne miejsce albo przestał je udostępniać. To nie musi znaczyć, że argumenty są błędne ani że szukanego obiektu nie ma. Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.` |
| `location` not a slug | `location: oczekiwano polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo slug miasta bez polskich znaków, np. warszawa, krakow, jastrzebie-zdroj (Jastrzębie-Zdrój); podano 'a/b'.` No request is sent. |
| `nbp_prices` for `polska` | `NBP nie podaje jednej ceny dla całej Polski, tylko dla miast i agregatów. Podaj agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo duże miasto, np. warszawa, krakow, gdansk, wroclaw, gdynia, poznan.` |
| `nbp_prices` for a location without NBP prices | The same, starting `NBP nie publikuje cen mieszkań dla lokalizacji 'sopot'.` |
| A dataset the location lacks (`7-miast` with `wages` or `unemployment`) | `Serwis nie publikuje zestawu 'wages' (Przeciętne miesięczne wynagrodzenie brutto w sektorze przedsiębiorstw) dla lokalizacji '7-miast'. Podaj polska albo miasto na prawach powiatu, np. warszawa.` |
| Unknown `dataset` or `periods` outside 1–120 | `Błędny argument narzędzia get_government_statistics: periods musi być liczbą całkowitą z zakresu 1–120, podano 121. Popraw i ponów; nic nie zostało wysłane.` (for `dataset`: `… dataset musi być jedną z wartości dwellings_quarterly, …, podano "prices" …`) |
| Unknown argument | `Nieznany argument narzędzia get_government_statistics: '…'. Dozwolone argumenty: location, dataset, periods. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| Page without the data | `Statystyki rządowe dla 'warszawa': Na stronie serwisu brakuje oczekiwanych danych. Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.` |
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

The demography of `polska` comes from Eurostat (`tests/golden/mcp/stats_polska_demography.json`, shortened to 2 of 12 periods and 1 of 3 series): `"source": "Eurostat"`, `"frequency": "month"`, `"stats_url": "https://deweloperuch.pl/statystyki/polska/dane-rzadowe#eurostat-demografia"`, `"periods": ["2024-10", "2024-11", "..."]`, `"series": [{"series_id": "births", "label": "Urodzenia żywe", "unit": "osoby", "values": [20923, 18893, "..."]}, "..."]`.

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/get_government_statistics_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/get_government_statistics_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/get_government_statistics.py`, `src/deweloperuch_mcp/api/adapters/government_statistics_api.py`, `tests/snapshots/mcp_tools.json`, `tests/golden/mcp/stats_*.json`_
