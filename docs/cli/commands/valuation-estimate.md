# `deweloperuch valuation estimate`
Estimates the value of an apartment of a given area at a point in Poland from nearby RCN transactions (an approximation, not an appraisal). Equivalent to the MCP tool [`estimate_property_value`](../../mcp/tools/estimate_property_value.md).

## Usage
```
deweloperuch valuation estimate [OPTIONS]
```

`--help` description: „Oszacuj wartość mieszkania z transakcji w okolicy punktu (przybliżenie, nie operat).”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `--lat` | float | — (required) | Latitude of a point in Poland, 49–54.9, e.g. 52.2297. Help text: „Szerokość geograficzna punktu w Polsce, np. 52.2297.” |
| `--lng` | float | — (required) | Longitude of a point in Poland, 14.1–24.2, e.g. 21.0122. Help text: „Długość geograficzna punktu w Polsce, np. 21.0122.” |
| `--area` | float | — (required) | The apartment area in m², 10–500, e.g. 48.5. Help text: „Metraż mieszkania w m², 10–500, np. 48.5.” |
| `--address` | text | none | An address description, 3–200 characters; the position comes from `--lat` and `--lng`. Help text: „Opcjonalny opis adresu; położenie wyznaczają --lat i --lng.” |
| `--limit` | int | all comparables | The maximum number of comparable transactions shown (the nearest), 0–100000. In MCP `limit` defaults to 10 with a maximum of 50. Help text: „Najwięcej pokazanych transakcji porównawczych (najbliższe); domyślnie wszystkie.” |
| `--json` | flag | off | Print the result as JSON (the domain model). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (a missing required option, a coordinate or area outside the range, a decimal comma, `--address` shorter than 3 characters, `--limit` outside the range), 3 STOP, 4 service error, 7 the service gave no estimate for the place (`Błąd: Serwis nie podał wyceny dla tego miejsca; w promieniu może nie być transakcji.`).

## Examples
```
deweloperuch valuation estimate --lat 52.2297 --lng 21.0122 --area 50
deweloperuch valuation estimate --lat 52.2297 --lng 21.0122 --area 48.5 --address "Marszałkowska 100, Warszawa" --limit 5
deweloperuch valuation estimate --lat 52.2297 --lng 21.0122 --area 50 --json
```

Output of the first call (`tests/golden/cli/valuation_estimate.json`):

```
Wycena mieszkania 50 m² · 52.22970, 21.01220
Szacowana wartość: 1 063 300 PLN · 21 266 PLN/m²
Na podstawie transakcji z Rejestru Cen Nieruchomości (RCN) w promieniu 200 m z ostatnich 24 miesięcy; to przybliżenie, nie operat szacunkowy.
Statystyki cen za m² podane przez serwis (liczba: 9): mediana 23 830 · średnia 22 195 · min 13 187 · max 31 492 PLN/m²
Transakcje porównawcze: 3 · pokazano 3.
  2025-04-17   ok. 150 m  Ulica Nowogrodzka 38 · 43,57 m² · 765 002 PLN · 17 558 PLN/m² · piętro 6 · rynek wtórny [ulica-nowogrodzka-38-warszawa]
  2025-05-27   ok. 150 m  Ulica Widok 24 · 41,02 m² · 977 507 PLN · 23 830 PLN/m² · piętro 6 · rynek wtórny [ulica-widok-24-warszawa]
  2025-01-13   ok. 150 m  Ulica Widok 22 · 66,76 m² · 2 100 003 PLN · 31 456 PLN/m² · piętro 3 · rynek wtórny [ulica-widok-22-warszawa]
```

The slug in brackets is a building slug for `buildings get`.

## Caveat of low confidence
When the estimate rests on fewer than 5 comparable transactions, the output has an `Uwaga: …` line with the caveat; the valuation cautions (no estimate, fractional area) are on a separate `Wskazówka: …` line. Digits are grouped (`1 000 m`) and the period reads „z ostatniego miesiąca” or „z ostatnich 24 miesięcy”. Output of `valuation estimate --lat 49.2167 --lng 22.3333 --area 50` (`tests/golden/cli/valuation_estimate_low_confidence.json`):

```
Wycena mieszkania 50 m² · 49.21670, 22.33330
Szacowana wartość: 202 000 PLN · 4 040 PLN/m²
Na podstawie transakcji z Rejestru Cen Nieruchomości (RCN) w promieniu 1 000 m z ostatnich 24 miesięcy; to przybliżenie, nie operat szacunkowy.
Uwaga: Wycena oparta tylko na 2 transakcjach z promienia 1 000 m (największego, jaki serwis bierze pod uwagę) z ostatnich 24 miesięcy: to orientacyjna wartość o niskiej wiarygodności. Podaj ją z tym zastrzeżeniem i z rozpiętością cen za m² tych transakcji (2 302–5 778 PLN/m²); porównaj też z cenami transakcyjnymi miasta (get_transaction_statistics).
Statystyki cen za m² podane przez serwis (liczba: 2): mediana 4 040 · średnia 4 040 · min 2 302 · max 5 778 PLN/m²
Transakcje porównawcze: 2 · pokazano 2.
  2025-06-02   ok. 850 m  ? · 65,15 m² · 149 975 PLN · 2 302 PLN/m² · rynek wtórny [cisna]
  2026-03-19   ok. 850 m  ? · 62,31 m² · 360 027 PLN · 5 778 PLN/m² · rynek wtórny [cisna]
```

With `--json` the result has `low_confidence` (`true` / `false` when there is an estimate; `null` without one) and the caveat is in `hint` (`tests/golden/cli/valuation_estimate_low_confidence_json.json`). The estimate and the price per m² come as a pair; a value of 0 or less is no value.

## Fractional areas
The client sends fractional areas to the service (rounded to 0.01 m²). The output area is the requested area; the service does not confirm the area it actually used. `estimated_value` and `price_per_m2` are retained as returned by the service, without recomputing the total locally.

For a fractional requested area, the text output and the JSON `hint` include: „Serwis może nie uwzględnić części ułamkowej powierzchni w wycenie.” This caution remains visible with `--limit`, alongside guidance about omitted comparables or a missing estimate.

A check on 2026-10-16 returned the same total for 41.37 m² and 41 m² at one point. This observation does not establish a general rounding or truncation rule; see [T41](../../open-questions.md#technical).

_Source: `src/deweloperuch_mcp/consumers/cli/commands/valuation_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/estimate_property_value_cli_presenter.py`, `uv run deweloperuch valuation estimate --help`_
