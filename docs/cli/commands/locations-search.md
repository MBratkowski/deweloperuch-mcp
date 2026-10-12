# `deweloperuch locations search`
Finds cities, districts and streets by a name fragment and returns the city slug for `offers search`. Equivalent to the MCP tool [`search_locations`](../../mcp/tools/search_locations.md).

## Usage
```
deweloperuch locations search [OPTIONS] QUERY
```

`--help` description: „Znajdź miasta, dzielnice i ulice; podaje slug miasta do `offers search`.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `QUERY` (argument, required) | text | — | A fragment of a city, district or street name (2-100 characters), e.g. krak. Help text: „Fragment nazwy miasta, dzielnicy lub ulicy (2–100 znaków), np. krak.” |
| `--json` | flag | off | Print the result as JSON (the domain model). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0 success, 2 bad `QUERY`, 3 STOP, 4 service error. No results is code 0 (with a `Wskazówka:` line).

## Examples
```
deweloperuch locations search krak
deweloperuch locations search "Mokotów" --json
```

Text output (from the test mock on samples; the mock does not filter by `QUERY`, so the Mokotów entries are not a match for "krak"; `[ ]` is the city slug):

```
Lokalizacje: 5.
miasto     Kraków [krakow] · ofert: 8 082
miasto     Krakowiany [krakowiany] · ofert: 0
miasto     Krakulice [krakulice] · ofert: 0
dzielnica  Mokotów, Warszawa [warszawa] · ofert: ok. 1 562
ulica      Mokotów, Warszawa [warszawa] · ofert: ok. 191
W nawiasach [] slug miasta dla: deweloperuch offers search CITY_SLUG
```

When there are more results than shown, the header reads `Lokalizacje: pokazano N, może być więcej.` (shown N, there may be more).

_Source: `src/deweloperuch_mcp/interfaces/cli/`, `uv run deweloperuch locations search --help`_
