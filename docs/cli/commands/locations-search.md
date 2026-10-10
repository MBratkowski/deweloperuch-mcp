# `deweloperuch locations search`
Znajduje miasta, dzielnice i ulice po fragmencie nazwy i podaje slug miasta do `offers search`. Odpowiednik narzędzia MCP [`search_locations`](../../mcp/tools/search_locations.md).

## Użycie
```
deweloperuch locations search [OPTIONS] QUERY
```

## Opcje
| Flaga | Typ | Domyślna | Opis |
|---|---|---|---|
| `QUERY` (argument, wymagany) | tekst | — | Fragment nazwy miasta, dzielnicy lub ulicy (2–100 znaków), np. krak. |
| `--json` | flaga | wyłączona | Wypisz wynik jako JSON (model domenowy). |
| `--help` | flaga | | Pokaż pomoc. |

## Kody wyjścia
Zob. [tabela kodów](../README.md#kody-wyjścia). Najczęstsze: 0 sukces, 2 zły `QUERY`, 3 STOP, 4 błąd serwisu. Brak wyników to kod 0 (z linią `Wskazówka:`).

## Przykłady
```
deweloperuch locations search krak
deweloperuch locations search "Mokotów" --json
```

Wynik tekstowy (z mocka testów na próbkach; mock nie filtruje po `QUERY`, więc pozycje z Mokotowem nie są dopasowaniem do „krak”; `[ ]` to slug miasta):

```
Lokalizacje: 5.
miasto     Kraków [krakow] · ofert: 8 082
miasto     Krakowiany [krakowiany] · ofert: 0
miasto     Krakulice [krakulice] · ofert: 0
dzielnica  Mokotów, Warszawa [warszawa] · ofert: ok. 1 562
ulica      Mokotów, Warszawa [warszawa] · ofert: ok. 191
W nawiasach [] slug miasta dla: deweloperuch offers search CITY_SLUG
```

Gdy wyników jest więcej niż pokazano, nagłówek brzmi `Lokalizacje: pokazano N, może być więcej.`

_Źródło: `src/deweloperuch_mcp/cli.py`, `uv run deweloperuch locations search --help`_
