# `deweloperuch stats government`
Shows GUS and NBP statistics of a location (`polska`, an aggregate or a city with county rights) as a table of periods and values; the monthly demography of `polska` comes from Eurostat (the `Źródło:` line says which). The same data as the MCP tool [`get_government_statistics`](../../mcp/tools/get_government_statistics.md).

## Usage
```
Usage: deweloperuch stats government [OPTIONS] {LOCATION} {DATASET}

 Pokaż statystyki GUS i NBP lokalizacji jako tabelę okresów i wartości.

Arguments:
 *    LOCATION  <str>  polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy)
                        albo miasto na prawach powiatu bez polskich znaków, np.
                        warszawa, bielsko-biala.  [required]
 *    DATASET   <dwellings_quarterly|dwellings_monthly|average_area|demography|
                 population|unemployment|wages|nbp_prices>  Zestaw danych. [required]

Options:
 --periods  <int>  Ile ostatnich okresów pokazać (lat, kwartałów, miesięcy).
                   [default: 12]
 --json            Wypisz wynik jako JSON (model domenowy).
 --help            Show this message and exit.
```
(Layout condensed from the boxed `--help` output; texts verbatim.) The command belongs to the `stats` group: „Statystyki: rynek ofert miasta, ceny transakcyjne (RCN) miasta, ranking miast i powiatów oraz statystyki rządowe GUS i NBP.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `LOCATION` | argument | | See above; capitals are accepted. The accepted locations are `polska`, the aggregates and the 66 cities with county rights of the service's own list (Jastrzębie-Zdrój is `jastrzebie-zdroj`). |
| `DATASET` | argument, enum | | `dwellings_quarterly`, `dwellings_monthly`, `average_area`, `demography`, `population`, `unemployment`, `wages`, `nbp_prices`. |
| `--periods` | int | 12 | 1–1000 (MCP: 1–120). |
| `--json` | flag | off | The domain dataclasses as JSON. |

## Exit codes
| Code | Meaning |
|---|---|
| 0 | Success. |
| 2 | Bad argument: `periods` outside 1–1000 (`Błąd: periods musi być liczbą całkowitą z zakresu 1–1000 (liczba ostatnich okresów), podano 0.`), unknown `DATASET`, missing argument. |
| 3 | STOP (401, 403, 429, challenge or an earlier STOP record). |
| 4 | Service error (5xx, network). |
| 5 | The limiter requires a longer pause than allowed. |
| 6 | The page has no expected data (the service may have changed), or the service moved or removed it: a redirect, a removed route, a 410, or a 404 for a location the service lists itself (`polska`, an aggregate, one of the 66 cities; `Błąd: Statystyki rządowe dla 'polska': Narzędzie nie może pobrać tych danych, …`). |
| 7 | Unknown location (a slug the service does not list: `Błąd: Serwis nie ma statystyk rządowych dla lokalizacji '…'. Podaj polska, agregat …`), `nbp_prices` for `polska` / a location without NBP prices, or a dataset the location lacks (`7-miast` has no `wages` or `unemployment`: `Błąd: Serwis nie publikuje zestawu 'wages' (…) dla lokalizacji '7-miast'. Podaj polska albo miasto na prawach powiatu, np. warszawa.`). |

Details: [exit codes](../README.md#exit-codes).

## Examples
```
uv run deweloperuch stats government polska unemployment
uv run deweloperuch stats government warszawa nbp_prices --periods 8
uv run deweloperuch stats government krakow wages --json
```
First example output (`tests/golden/cli/stats_polska_unemployment.json`, shortened):
```
Stopa bezrobocia rejestrowanego · Polska [polska]
Źródło: GUS · miesięcznie · okresy: pokazano 12 z 188 (dane od 2011-01).
Wskazówka: Pokazano ostatnie 12 z 188 okresów (dane od 2011-01); starsze pokaże większa wartość periods.
Strona na deweloperuch.pl: https://deweloperuch.pl/statystyki/polska/dane-rzadowe#gus-bezrobocie
Kolumny:
  [1] Stopa bezrobocia (%)
Okres    [1]
2025-09  5,6
...
2026-08  5,8
```
The demography of `polska` is from Eurostat (`tests/golden/cli/stats_polska_demography.json`, `stats government polska demography`, shortened): the head is `Urodzenia żywe, zgony i przyrost naturalny · Polska [polska]`, then `Źródło: Eurostat · miesięcznie · okresy: pokazano 12 z 357 (dane od 1996-01).` and `Strona na deweloperuch.pl: https://deweloperuch.pl/statystyki/polska/dane-rzadowe#eurostat-demografia`.

The last year of `average_area` is partial, which a `Uwaga:` line says (`tests/golden/cli/stats_polska_average_area.json`): `Uwaga: Ostatni rok (2026) bywa niepełny: GUS dopisuje go kwartałami, więc porównuj go ostrożnie z pełnymi latami.`

_Source: `src/deweloperuch_mcp/consumers/cli/commands/stats_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/get_government_statistics_cli_presenter.py`, `uv run deweloperuch stats government --help`, `tests/golden/cli/stats_*.json`_
