# `deweloperuch offers search`
Szuka ofert mieszkań od deweloperów (ceny ofertowe, rynek pierwotny) w mieście albo w całej Polsce (`polska`), z filtrami ceny i metrażu; najwyżej 20 stron wyników. Odpowiednik narzędzia MCP [`search_offers`](../../mcp/tools/search_offers.md).

## Użycie
```
deweloperuch offers search [OPTIONS] CITY
```

## Opcje
| Flaga | Typ | Domyślna | Opis |
|---|---|---|---|
| `CITY` (argument, wymagany) | tekst | — | Slug miasta (np. warszawa; podaje go `locations search`) albo polska. |
| `--price-min` | int | brak | Najniższa cena w PLN. |
| `--price-max` | int | brak | Najwyższa cena w PLN. |
| `--area-min` | int | brak | Najmniejszy metraż w m². |
| `--area-max` | int | brak | Największy metraż w m². |
| `--sort` | `price_asc` \| `price_desc` | brak (kolejność serwisu) | Kolejność po cenie. Sortowanie po cenie rosnąco i malejąco potwierdzone [P 2026-10-10]. |
| `--page` | int | `1` | Numer strony, 1–20. |
| `--per-page` | `10` \| `50` \| `100` | `10` | Liczba ofert na stronie. |
| `--json` | flaga | wyłączona | Wypisz wynik jako JSON (model domenowy). |
| `--help` | flaga | | Pokaż pomoc. |

Zakresy filtrów to 0–99 999 999 PLN i 0–9 999 m² (wartownicy [P z kodu]); `--price-min` większe niż `--price-max` to błąd (kod 2).

## Kody wyjścia
Zob. [tabela kodów](../README.md#kody-wyjścia). Najczęstsze: 0, 2 (zły filtr, `--sort` lub `--per-page` spoza listy), 3 STOP, 4 błąd serwisu, 7 nieznane miasto (tylko przy HTTP 404; strona bez danych daje dziś kod 6, bo serwis zwraca 200).

## Przykłady
```
deweloperuch offers search warszawa
deweloperuch offers search warszawa --price-max 1000000 --sort price_asc
deweloperuch offers search krakow --area-min 40 --area-max 60 --per-page 50 --page 2
deweloperuch offers search polska --json
```

Wynik pierwszego wywołania (domyślne `--per-page 10`) z mocka testów (`tests/service_mocks.offers_page(count=10)`): pozycje są kopiami ofert z próbki `page.offers_list` z syntetycznymi `offer_id` (900000+), `total` pochodzi z próbki. Pokazano 2 pierwsze pozycje z 10, pozostałe 8 pominięto:

```
Pasujące oferty: 13 324 · strona 1 z 20 (po 10) · pokazano 10 · obcięte: serwis pozwala przejrzeć najwyżej 20 stron.
Wskazówka: Pasujących ofert jest 13324, a serwis pozwala przejrzeć najwyżej 20 stron po 10 (200). Zawęź filtry (cena, metraż) albo zwiększ per_page do 100.
[900000] D1.1.1.4 · 994 012 PLN · 55,25 m² · 17 991,17 PLN/m² · aktywna · od pierwszej ceny -5 988 PLN (-0,6%)
    Nowy Targówek VI [nowy-targowek-vi] · ATAL S.A. · Warszawa
[900001] D1.2.0.1 · 659 315 PLN · 36,49 m² · 18 068,37 PLN/m² · aktywna · od pierwszej ceny -30 685 PLN (-4,45%)
    Nowy Targówek VI [nowy-targowek-vi] · ATAL S.A. · Warszawa
(… 8 pozostałych ofert pominięto …)
Szczegóły oferty: deweloperuch offers get OFFER_ID --investment INVESTMENT_SLUG
```

_Źródło: `src/deweloperuch_mcp/cli.py`, `uv run deweloperuch offers search --help`_
