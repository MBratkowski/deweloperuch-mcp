# CLI `deweloperuch`

Wiersz poleceń nad tymi samymi usługami co [serwer MCP](../mcp/README.md). Tylko odczyt; zapytania idą przez wspólny limiter (najwyżej 1 na sekundę, 1 naraz). Skrypt: `deweloperuch` (`[project.scripts]`), czyli `uv run deweloperuch …` albo `.venv/bin/deweloperuch …`.

```
Usage: deweloperuch [OPTIONS] COMMAND [ARGS]...

Commands:
  locations    Lokalizacje: miasta, dzielnice, ulice.
  offers       Oferty mieszkań od deweloperów.
  investments  Inwestycje deweloperskie.
```

`deweloperuch` bez argumentów wypisuje pomoc i kończy się kodem 2 (konwencja click). Wbudowane teksty pomocy i błędów użycia (typer/click) są po angielsku.

## Komendy

| Komenda | Do czego |
|---|---|
| [`locations search QUERY`](commands/locations-search.md) | Znajduje miasta, dzielnice i ulice; podaje slug miasta do `offers search`. |
| [`offers search CITY`](commands/offers-search.md) | Szuka ofert mieszkań w mieście (albo `polska`) z filtrami ceny i metrażu; najwyżej 20 stron wyników. |
| [`offers get OFFER_ID --investment SLUG`](commands/offers-get.md) | Pokazuje ofertę z historią ceny. |
| [`investments get SLUG`](commands/investments-get.md) | Pokazuje inwestycję z deweloperem i ofertami. |

Typowa kolejność: `locations search` → `offers search` → `investments get` albo `offers get`.

## Format wyjścia

- **Tekst** (domyślnie, stdout): po polsku, liczby z grupowaniem cyfr i przecinkiem dziesiętnym (`1 620 175 PLN`), bez form liczby mnogiej. Dla dzielnic i ulic liczba ofert to `ofert: ok. N` (przybliżona, [W]).
- **`--json`** (stdout): pełny model domenowy, `model_dump_json(indent=2)`, wszystkie pola łącznie z `null`. Jest to inna, bogatsza reprezentacja niż w MCP (tam pozycje są skrócone i bez `null`).
- **Błędy** (stderr, bez tracebacka):
  - `Błąd: <komunikat>`
  - `Szczegóły: <detail>` (gdy jest; cel, status i fragment ciała, znaki niedrukowalne zapisane jako `\xNN`/`\uNNNN`)
  - przy kodzie 3 dodatkowa linia: `Nie uruchamiaj kolejnych poleceń deweloperuch ani pętli: przerwij i zgłoś to. Przy 429 odczekaj co najmniej czas podany wyżej.`

STOP nie jest utrwalany między uruchomieniami CLI: każde nowe uruchomienie zaczyna bez blokady, dlatego pętla w shellu mogłaby dalej wysyłać zapytania. Porada na stderr jest jedynym zabezpieczeniem; po kodzie 3 przerwij serię.

## Kody wyjścia

Stałe `cli.ExitCode` (publiczne):

| Kod | Nazwa | Znaczenie |
|---|---|---|
| 0 | `OK` | Sukces. |
| 1 | `UNEXPECTED` | Inny błąd, np. `SessionClosedError` albo błąd programu (z tracebackiem). |
| 2 | `INVALID_INPUT` | Zły argument (`InvalidInputError`) albo błąd użycia typer/click: zły typ, wartość spoza listy, brak wymaganej opcji, `deweloperuch` bez argumentów. |
| 3 | `STOP` | `ServiceBlockedError` / `RateLimitedError` (401, 403, 429, challenge): przerwij i zgłoś użytkownikowi. |
| 4 | `SERVICE_ERROR` | Błąd serwisu: 5xx, sieć, przekierowanie, inne 4xx, odpowiedź za duża lub za wolna. |
| 5 | `LIMITER_WAIT` | Wspólny limiter wymaga dłuższej przerwy niż dozwolona (60 s); nic nie wysłano. |
| 6 | `UNEXPECTED_RESPONSE` | Odpowiedź 2xx niezgodna z kontraktem (serwis mógł się zmienić). |
| 7 | `NOT_FOUND` | Brak inwestycji, oferty albo miasta. |

## Konfiguracja

Brak własnych flag środowiska. Limiter i cache: [docs/configuration.md](../configuration.md).

_Źródło: `src/deweloperuch_mcp/cli.py`, `uv run deweloperuch --help`_
