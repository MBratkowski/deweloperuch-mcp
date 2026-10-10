# Konfiguracja

Stan po S1a. Istnieje wewnętrzny klient HTTP z cache w pamięci; serwer MCP i CLI jeszcze nie istnieją, więc ich ustawień tu nie ma. Klient nie ma własnych zmiennych środowiskowych ani plików (wartości poniżej są stałymi w kodzie).

## Zmienne środowiskowe

| Nazwa | Typ | Domyślna | Opis |
|---|---|---|---|
| `XDG_CACHE_HOME` | ścieżka bezwzględna | `~/.cache` | Standardowa zmienna XDG. Katalog zamka limitera to `$XDG_CACHE_HOME/deweloperuch-mcp`. Wartość pusta lub względna jest ignorowana (użyty zostaje `~/.cache`). |

Żadnych innych zmiennych środowiskowych kod nie czyta.

## Pliki

| Ścieżka | Opis |
|---|---|
| `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/throttle.lock` | Zamek (`flock`) i stan wspólnego limitera zapytań. Tworzony automatycznie (katalog, plik z uprawnieniami `0600`). Wewnętrzny protokół między procesami: nie edytuj. |
| `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/chunks/` | Cache chunków JS skanera `recon/scan_bundles.py` (ścieżka po `/_next/static/chunks/`). Pliki `0600`, zapis atomowy, tylko przy pełnym 200 z niepustym ciałem. Nazwy z hashem są niezmienne, więc taki chunk nie jest pobierany ponownie; pusty plik jest pobierany ponownie, a chunki bez hasha w nazwie przy każdym skanie. Można go usunąć bez skutków ubocznych (kolejny skan pobierze chunki od nowa). |

## Limiter zapytań

Wszystkie procesy na jednej maszynie (skrypty `recon/` i klient pakietu) przechodzą przez ten sam zamek, więc razem trzymają politykę D2 ([decisions.md](decisions.md)).

| Parametr | Wartość | Opis |
|---|---|---|
| Odstęp między zapytaniami | 1 s (minimum) | Liczony od końca poprzedniego zapytania. Wolno go tylko wydłużyć. |
| Współbieżność | 1 zapytanie naraz | Między procesami i wątkami. |
| Maks. oczekiwanie (`max_wait`) | 60 s | Dłuższa wymagana przerwa kończy się błędem zamiast uśpienia. Nie obejmuje czekania na zamek, gdy trwa cudze zapytanie (ogranicza je timeout zapytania). |
| Maks. przerwa z `Retry-After` | 3600 s | Dłuższa wartość jest zapisana jako 3600 s i zgłaszana jako błąd. |

Zachowanie z punktu widzenia użytkownika:

- Proces zabity w trakcie zapytania nie blokuje zamka na stałe. Następny proces odczeka jednak standardowy odstęp.
- Po błędzie oczekiwania (`WaitTooLongError`, komunikat „Następne zapytanie do deweloperuch.pl wolno wysłać dopiero za N s…”) odczekaj podany czas i ponów. W ostateczności usuń `throttle.lock` ręcznie, ale tylko gdy na pewno żaden proces nie korzysta z serwisu i minął czas z `Retry-After`.
- `Retry-After` dłuższe niż 1 h jest przycinane do 1 h i zgłaszane jako błąd, a następne zapytanie czeka tę godzinę.
- Obsługiwane systemy: Linux i macOS. Na Windows limiter zgłasza czytelny błąd (brak `fcntl.flock`).

## Klient pakietu

Klient (`deweloperuch_mcp.client.transport`) jest synchroniczny (`httpx`), z User-Agentem z `identity`. Każde żądanie razem z czytaniem ciała mieści się w jednym slocie wspólnego limitera.

| Parametr | Wartość | Opis |
|---|---|---|
| `max_wait` limitera | 60 s | Jak wyżej; dłuższe oczekiwanie to `LimiterWaitError`. |
| Timeout żądania | 30 s | |
| Limit czytania ciała | 120 s | |
| Limit ciała | 32 MiB | Większa odpowiedź to błąd. |
| Przekierowania, ponowienia | brak | |
| Pauza po 429 | co najmniej 60 s | `max(Retry-After, 60)`. |
| Pauza po 502/503/504 | `Retry-After` albo 30 s | |
| STOP (401/403/429/challenge) | blokada procesu do restartu | Dotyczy wszystkich sesji w procesie (`ServiceBlockedError`, przy 429 `RateLimitedError`). Odpowiedzi z cache nadal są zwracane. |
| Cache | w pamięci procesu | Nie jest zapisywany na dysk. TTL = `s-maxage` minus `Age` (domyślnie 300 s, maks. 24 h). LRU: 256 wpisów i 64 MiB. |
| Sesja zamknięta | `SessionClosedError` | Użycie po wyjściu z `Session`. |

Cel żądania jest sprawdzany przed wysłaniem według allowlisty (`allowlist.py`) i reguły D5: ścieżki z `DUMP_PATHS` (`/api/map/powiat-sales/{id}`, strona `/statystyki/ceny-transakcyjne/{mieszkania|domy}/{city}` bez `/mapa`) nigdy nie są wywoływane. `valuation-pdf` i server actions są wykluczone. Naruszenie to `InvalidInputError` z prefiksem „Błąd programu”.

## Skrypty recon

Skrypty `recon/` uruchamiane jako `python3 recon/<skrypt>.py` wymagają Pythona 3.11 lub nowszego. Systemowy `python3` z macOS to 3.9 i kończy się komunikatem o wymaganej wersji. Alternatywa: `uv run python recon/<skrypt>.py`.

`BASE_URL` i `USER_AGENT` (tymczasowy, `TODO(U1)`, do rozstrzygnięcia w U1/D9) są zdefiniowane w jednym miejscu: `src/deweloperuch_mcp/identity.py`. `recon/config.py` je reeksportuje i udostępnia skryptom razem z tym samym limiterem co pakiet.

`recon/flight.py` i `recon/allowlist.py` reeksportują implementacje z pakietu (`deweloperuch_mcp.flight`, `deweloperuch_mcp.allowlist`). `recon/flight.py` uruchamiany jako CLI również wymaga Pythona 3.11+ (wcześniej działał na 3.9).

### `recon/probe.py`

Pojedyncze żądanie GET na uruchomienie (bez przekierowań i ponowień), w slocie tego samego zamka `throttle.lock` i z tym samym User-Agentem co reszta. Szczegóły flag i kodów wyjścia: `python3 recon/probe.py --help` oraz [README.md](../README.md).

| Parametr | Wartość | Opis |
|---|---|---|
| `--max-wait` | 60 s (domyślnie) | Skończona liczba sekund. Dłuższa wymagana przerwa kończy się kodem 5, bez wysłania zapytania. |
| Pauza po 429 | co najmniej 60 s | `max(Retry-After, 60)`. |
| Pauza po 502/503/504 | `Retry-After` albo 30 s | `Retry-After` > 3600 s jest przycinane do 3600 s. |
| Limit odpowiedzi | 32 MiB | Większa odpowiedź kończy się kodem 4 (D5: recon nie służy do zrzutów). |
| Limit czytania odpowiedzi | ok. 120 s | Najgorszy przypadek ok. 120 s + 2 × 30 s. Odpowiedź krótsza niż `Content-Length` to kod 4, bez zapisu próbki. |
| `--save` | `docs/discovery/samples/` | Jedyny katalog zapisu; istniejący plik nie jest nadpisywany. |

Probe nie czyta własnych zmiennych środowiskowych. Parser `Retry-After` (sekundy albo data HTTP) jest wspólny z pakietem.

### `recon/scan_bundles.py`

Skaner bundli JS (wykrywanie zmian po deployu, D7). Wszystkie żądania idą przez ten sam zamek `throttle.lock` i z tym samym User-Agentem. Flagi, kody wyjścia i format `--json`: `python3 recon/scan_bundles.py --help` oraz [README.md](../README.md).

| Parametr | Wartość | Opis |
|---|---|---|
| `max_wait` | 60 s (stałe) | Bez flagi. Dłuższa wymagana przerwa kończy skan kodem 5, przed wysłaniem zapytania. |
| Pauzy, limity odpowiedzi | jak w probe | Pauza po 429 co najmniej 60 s, po 502/503/504 `Retry-After` albo 30 s; limit odpowiedzi 32 MiB i czas czytania jak wyżej. |
| Przekierowania, ponowienia | brak | Każdy błąd (także 3xx) kończy cały skan. |
| `MAX_CHUNKS` | 400 | Twardy limit żądań chunków na skan (także gdy pliki cache są nieczytelne); przekroczenie to kod 6. |
| Cache | `chunks/` | Zob. tabela „Pliki”. Skaner respektuje `XDG_CACHE_HOME`. |

_Źródło: `src/deweloperuch_mcp/throttle.py`, `src/deweloperuch_mcp/identity.py`, `src/deweloperuch_mcp/retry_after.py`, `src/deweloperuch_mcp/http_policy.py`, `recon/config.py`, `recon/http_common.py`, `recon/probe.py`, `recon/scan_bundles.py`, `recon/allowlist.py`, `recon/flight.py`, `src/deweloperuch_mcp/client/transport.py`, `src/deweloperuch_mcp/allowlist.py`, `src/deweloperuch_mcp/flight.py`, `src/deweloperuch_mcp/errors.py`_
