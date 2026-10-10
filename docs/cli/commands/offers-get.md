# `deweloperuch offers get`
Pokazuje jedną ofertę z pełną historią ceny, inwestycją i deweloperem. Odpowiednik narzędzia MCP [`get_offer`](../../mcp/tools/get_offer.md).

## Użycie
```
deweloperuch offers get [OPTIONS] OFFER_ID --investment SLUG
```

## Opcje
| Flaga | Typ | Domyślna | Opis |
|---|---|---|---|
| `OFFER_ID` (argument, wymagany) | int | — | Identyfikator oferty z `offers search`. |
| `--investment` | SLUG | — (wymagana) | Slug inwestycji oferty (investment_slug z `offers search`). |
| `--json` | flaga | wyłączona | Wypisz wynik jako JSON (model domenowy). |
| `--help` | flaga | | Pokaż pomoc. |

## Kody wyjścia
Zob. [tabela kodów](../README.md#kody-wyjścia). Najczęstsze: 0, 2 (brak `--investment`, zły `OFFER_ID`), 3 STOP, 7 brak inwestycji lub oferty w tej inwestycji.

## Przykłady
```
deweloperuch offers get 2377 --investment smolna
deweloperuch offers get 2377 --investment smolna --json
```

Wynik tekstowy (mock testów, próbki `api.map_inv_visible`, `api.sale_events`):

```
[2377] C224 · aktywna
Cena: 1 620 175 PLN · 69,5 m² · 23 311,87 PLN/m²
Od pierwszej ceny: +175 PLN (+0,01%)
Inwestycja: Smolna [smolna] · Sopot
Deweloper: Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]
Daty: dodana 2025-02-25 · ostatnie zdarzenie 2026-10-03 · ostatnia zmiana 2026-10-03
Historia ceny (3):
  2025-02-25  cena          1 620 000 PLN
  2025-02-25  wycofanie     1 620 000 PLN
  2026-10-03  przywrócenie  1 620 175 PLN
```

Z `--json` wynik ma wszystkie pola modelu domenowego, także `null` (np. `developer.website`).

_Źródło: `src/deweloperuch_mcp/cli.py`, `uv run deweloperuch offers get --help`_
