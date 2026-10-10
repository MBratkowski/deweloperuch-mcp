# `deweloperuch investments get`
Pokazuje inwestycję (projekt deweloperski) z deweloperem, średnimi cenami aktywnych ofert i listą ofert (najpierw aktywne). Odpowiednik narzędzia MCP [`get_investment`](../../mcp/tools/get_investment.md).

## Użycie
```
deweloperuch investments get [OPTIONS] SLUG
```

## Opcje
| Flaga | Typ | Domyślna | Opis |
|---|---|---|---|
| `SLUG` (argument, wymagany) | tekst | — | Slug inwestycji (investment_slug z `offers search`). |
| `--history` | flaga | wyłączona | Dołącz historię ceny każdej oferty (wolniej: dodatkowe zapytanie). |
| `--limit` | int | brak (wszystkie oferty) | Najwięcej pokazanych ofert (najpierw aktywne). W MCP `limit` ma domyślnie 20 i maks. 200; CLI bez `--limit` pokazuje wszystkie. |
| `--json` | flaga | wyłączona | Wypisz wynik jako JSON (model domenowy). |
| `--help` | flaga | | Pokaż pomoc. |

## Kody wyjścia
Zob. [tabela kodów](../README.md#kody-wyjścia). Najczęstsze: 0, 2 (zły slug lub `--limit`), 3 STOP, 7 brak inwestycji.

## Przykłady
```
deweloperuch investments get smolna
deweloperuch investments get smolna --limit 2
deweloperuch investments get smolna --history --json
```

Wynik tekstowy z `--limit 2` (mock testów, próbka `api.map_inv_visible`):

```
Smolna [smolna] · aktywna
Miejsce: Sopot [sopot], Świemirowo · 54.42736, 18.55839
Deweloper: Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]
Średnio (aktywne oferty): 1 566 392 PLN · 63,97 m² · 24 487,63 PLN/m²
Oferty: aktywne 3 z 16 · pokazano 2 · pominięto 1 (zwiększ --limit).
[206087] C234 · 1 679 796 PLN · 65,9 m² · 25 490,08 PLN/m² · aktywna
[2377] C224 · 1 620 175 PLN · 69,5 m² · 23 311,87 PLN/m² · aktywna · od pierwszej ceny +175 PLN (+0,01%)
```

_Źródło: `src/deweloperuch_mcp/cli.py`, `uv run deweloperuch investments get --help`_
