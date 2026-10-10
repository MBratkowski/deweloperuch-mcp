# CLI `deweloperuch`

Wiersz poleceń nad tymi samymi usługami co [serwer MCP](../mcp/README.md). Tylko odczyt; zapytania idą przez wspólny limiter (najwyżej 1 na sekundę, 1 naraz). Skrypt: `deweloperuch` (`[project.scripts]`), czyli `uv run deweloperuch …` albo `.venv/bin/deweloperuch …`.

```
Usage: deweloperuch [OPTIONS] COMMAND [ARGS]...

Commands:
  locations    Lokalizacje: miasta, dzielnice, ulice.
  offers       Oferty mieszkań od deweloperów.
  investments  Inwestycje deweloperskie.
  stop         Blokada STOP: po 401, 403, 429 albo challenge Cloudflare żaden
               proces (CLI, serwer MCP, recon) nie wysyła zapytań. Działa offline.
```

`deweloperuch` bez argumentów wypisuje pomoc i kończy się kodem 2 (konwencja click). Wbudowane teksty pomocy i błędów użycia (typer/click) są po angielsku.

## Komendy

| Komenda | Do czego |
|---|---|
| [`locations search QUERY`](commands/locations-search.md) | Znajduje miasta, dzielnice i ulice; podaje slug miasta do `offers search`. |
| [`offers search CITY`](commands/offers-search.md) | Szuka ofert mieszkań w mieście (albo `polska`) z filtrami ceny i metrażu; najwyżej 20 stron wyników. |
| [`offers get OFFER_ID --investment SLUG`](commands/offers-get.md) | Pokazuje ofertę z historią ceny. |
| [`investments get SLUG`](commands/investments-get.md) | Pokazuje inwestycję z deweloperem i ofertami. |

| [`stop status [--json]`](commands/stop-status.md) | Pokazuje blokadę STOP wspólną dla wszystkich procesów; offline, od razu. |
| [`stop clear`](commands/stop-clear.md) | Zdejmuje blokadę STOP. **Tylko człowiek**, po sprawdzeniu przyczyny. |

Typowa kolejność: `locations search` → `offers search` → `investments get` albo `offers get`.

## Format wyjścia

- **Tekst** (domyślnie, stdout): po polsku, liczby z grupowaniem cyfr i przecinkiem dziesiętnym (`1 620 175 PLN`), bez form liczby mnogiej. Dla dzielnic i ulic liczba ofert to `ofert: ok. N` (przybliżona, [W]).
- **`--json`** (stdout): pełny model domenowy, `model_dump_json(indent=2)`, wszystkie pola łącznie z `null`. Jest to inna, bogatsza reprezentacja niż w MCP (tam pozycje są skrócone i bez `null`).
- **Błędy** (stderr, bez tracebacka):
  - `Błąd: <komunikat>`
  - `Szczegóły: <detail>` (gdy jest; cel, status i fragment ciała, znaki niedrukowalne zapisane jako `\xNN`/`\uNNNN`)
  - przy kodzie 3 dodatkowa linia (`cli.STOP_ADVICE`): `Nie uruchamiaj kolejnych poleceń deweloperuch ani pętli: przerwij i zgłoś to użytkownikowi. Blokada obejmuje też inne procesy.`

## STOP

Po 401, 403, 429 albo challenge Cloudflare proces zapisuje STOP w pliku obok `throttle.lock` ([docs/configuration.md](../configuration.md#stop-blokada-między-procesami)). Zapis jest wspólny dla wszystkich procesów na maszynie: CLI, serwera MCP, `recon/probe.py` i `recon/scan_bundles.py`. Dopóki jest aktywny, żaden z nich nie wysyła zapytań:

- komendy danych, probe i skaner kończą się kodem 3 bez zapytania; serwer MCP zwraca `isError` z tekstem zaczynającym się od `STOP:`. Pętla w shellu zatrzymuje się więc przy pierwszej komendzie po STOP, także gdy STOP zapisał inny proces;
- **429** wygasa sam po pauzie (`max(Retry-After, 60 s)`); w jej trakcie komendy z innego procesu dają kod 3, a nie czekanie albo kod 5 (zmiana zachowania w tej wersji);
- **401, 403 i challenge** są bezterminowe: zdejmuje je człowiek;
- **nieczytelny zapis** (zły JSON, inny format, symlink, FIFO, katalog, obce `source`, `reason` niezgodny ze statusem, plik powyżej 64 KiB) to STOP bezterminowy, żeby błąd pliku nie otwierał drogi do serwisu;
- kod 5 (`LimiterWaitError`) zostaje dla pauz bez zapisu (502/503/504) i dla reszty pauzy 429 po ręcznym zdjęciu zapisu;
- stan sprawdzisz przez [`stop status`](commands/stop-status.md) (kod 0 bez STOP lub przy wygasłym, 3 przy aktywnym). **Zdejmuje go tylko użytkownik** przez [`stop clear`](commands/stop-clear.md), po sprawdzeniu przyczyny; agentom blokuje to hook Bash i reguła w `CLAUDE.md`. Usunięcie katalogu cache też zdejmuje STOP, więc tak go nie zdejmuj.

Serwer MCP, który raz zwrócił STOP (własny albo z zapisu innego procesu), pozostaje zatrzaśnięty do restartu, także po zdjęciu zapisu albo wygaśnięciu 429.

## Kody wyjścia

Stałe `cli.ExitCode` (publiczne):

| Kod | Nazwa | Znaczenie |
|---|---|---|
| 0 | `OK` | Sukces. |
| 1 | `UNEXPECTED` | Inny błąd, np. `SessionClosedError` albo błąd programu (z tracebackiem). `stop clear`: zamek nie uzyskany w 300 s albo zapisu nie da się usunąć. |
| 2 | `INVALID_INPUT` | Zły argument (`InvalidInputError`) albo błąd użycia typer/click: zły typ, wartość spoza listy, brak wymaganej opcji, `deweloperuch` bez argumentów. |
| 3 | `STOP` | `ServiceBlockedError` / `RateLimitedError` (401, 403, 429, challenge) albo wcześniejszy STOP zapisany przez dowolny proces (komenda nic nie wysyła); także `stop status` przy aktywnej blokadzie. Przerwij i zgłoś użytkownikowi. |
| 4 | `SERVICE_ERROR` | Błąd serwisu: 5xx, sieć, przekierowanie, inne 4xx, odpowiedź za duża lub za wolna. |
| 5 | `LIMITER_WAIT` | Wspólny limiter wymaga dłuższej przerwy niż dozwolona (60 s); nic nie wysłano. Dotyczy pauz bez zapisu STOP (502/503/504) i reszty pauzy 429 po ręcznym zdjęciu zapisu; w czasie aktywnego STOP jest kod 3. |
| 6 | `UNEXPECTED_RESPONSE` | Odpowiedź 2xx niezgodna z kontraktem (serwis mógł się zmienić). |
| 7 | `NOT_FOUND` | Brak inwestycji, oferty albo miasta. |

## Konfiguracja

Brak własnych flag środowiska. Limiter i cache: [docs/configuration.md](../configuration.md).

_Źródło: `src/deweloperuch_mcp/cli.py`, `src/deweloperuch_mcp/throttle.py`, `uv run deweloperuch --help`_
