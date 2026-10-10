# Konfiguracja

Stan po S1b. Pakiet ma wewnętrzny klient HTTP z cache w pamięci oraz dwa punkty wejścia: CLI [`deweloperuch`](cli/README.md) i serwer MCP [`deweloperuch-mcp`](mcp/README.md). Żaden z nich nie ma własnych zmiennych środowiskowych ani plików konfiguracyjnych (wartości poniżej są stałymi w kodzie).

## Zmienne środowiskowe

| Nazwa | Typ | Domyślna | Opis |
|---|---|---|---|
| `XDG_CACHE_HOME` | ścieżka bezwzględna | `~/.cache` | Standardowa zmienna XDG. Katalog zamka limitera i zapisu STOP to `$XDG_CACHE_HOME/deweloperuch-mcp`. Wartość pusta lub względna jest ignorowana (użyty zostaje `~/.cache`). Procesy z różnym `XDG_CACHE_HOME` nie widzą nawzajem swojego STOP ani zamka. |

Żadnych innych zmiennych środowiskowych kod nie czyta.

## Pliki

| Ścieżka | Opis |
|---|---|
| `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/throttle.lock` | Zamek (`flock`) i stan wspólnego limitera zapytań. Tworzony automatycznie (katalog, plik z uprawnieniami `0600`). Wewnętrzny protokół między procesami: nie edytuj. |
| `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/stop.json` | Zapis STOP wspólny dla wszystkich procesów (zob. [STOP](#stop-blokada-między-procesami)). Powstaje po 401/403/429/challenge; zdejmuje go użytkownik przez `deweloperuch stop clear`. Nie edytuj ręcznie. |
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
- Po błędzie oczekiwania (`WaitTooLongError`, komunikat „Następne zapytanie do deweloperuch.pl wolno wysłać dopiero za N s…”) odczekaj podany czas i ponów. W ostateczności (człowiek) usuń sam plik `throttle.lock`, ale tylko gdy na pewno żaden proces nie korzysta z serwisu i minął czas z `Retry-After`; zapisu STOP w ten sposób nie zdejmuj (użyj `stop clear`).
- `Retry-After` dłuższe niż 1 h jest przycinane do 1 h i zgłaszane jako błąd, a następne zapytanie czeka tę godzinę.
- Obsługiwane systemy: Linux i macOS. Na Windows limiter zgłasza czytelny błąd (brak `fcntl.flock`).

## STOP: blokada między procesami

Po 401, 403, 429 albo challenge Cloudflare proces zapisuje STOP w `stop.json` obok `throttle.lock`. Dopóki zapis jest aktywny, żaden proces (CLI, serwer MCP, `recon/probe.py`, `recon/scan_bundles.py`) nie wysyła zapytań: CLI, probe i skaner kończą się kodem 3, serwer MCP zwraca `isError` z `STOP:`. Pakiet zapisuje STOP zaraz po nagłówkach odpowiedzi, recon po przeczytaniu ciała (znane ograniczenie: przerwanie w trakcie czytania ciała 401/403/429 nie zostawi zapisu).

| Właściwość | Wartość |
|---|---|
| Lokalizacja | `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/stop.json` |
| Format | JSON, `"format": 1`: `{"format": 1, "since": ISO-UTC, "status": 401\|403\|429\|"challenge", "reason": tekst, "until": ISO-UTC\|null, "source": "pakiet"\|"probe"\|"scan_bundles", "pid": liczba}` |
| Zawartość | Tylko status i kanoniczny tekst powodu (`reason`); bez celu, URL-a, nagłówków i treści odpowiedzi. |
| Uprawnienia, zapis | `0600`; zapis atomowy (plik tymczasowy `.stop-*.tmp`, `fsync`, `os.replace`), wyłącznie pod zamkiem `throttle.lock`. |
| Odczyt | `slot()` czyta zapis pod zamkiem, przed liczeniem czasu: przy aktywnym zapisie nic nie jest wysyłane, a stan czasowy limitera zostaje nietknięty. `stop status` czyta bez zamka. |

Reguły ważności:

- **429** wygasa: `until` to czas zapisu plus pauza limitera (`max(Retry-After, 60 s)`, maks. 3600 s). 429 bez znanej pauzy jest bezterminowy.
- **401, 403, challenge** nie wygasają (`until` to `null`; `until` w takim zapisie jest ignorowane). Challenge zawsze ma `status` `"challenge"`, także przy statusie 429 lub 403.
- **Pierwszy aktywny zapis wygrywa**; późniejszy STOP może tylko wydłużyć koniec albo uczynić zapis bezterminowym. Wygasły zapis zastępuje nowy.
- **Nieczytelny zapis to STOP bezterminowy** (fail-closed): zły JSON, brak klucza, `format` i `pid` inne niż liczba całkowita, czas bez strefy, `status` spoza 401/403/429/`challenge`, `reason` niezgodny ze statusem, `source` spoza `pakiet`/`probe`/`scan_bundles`, plik powyżej 64 KiB, symlink, FIFO, katalog, błąd odczytu. Treść takiego pliku nie trafia do żadnego komunikatu (`stop status` podaje tylko krótki opis problemu).
- Pauza po 429 jest też w stanie czasowym `throttle.lock`. Zdjęcie zapisu jej nie skraca; po `stop clear` kod 5 (`LimiterWaitError`) może więc jeszcze chwilę oznaczać resztę pauzy.

Zdejmowanie: wyłącznie przez użytkownika, `deweloperuch stop clear` ([opis](cli/commands/stop-clear.md)), po sprawdzeniu przyczyny (`deweloperuch stop status`, [opis](cli/commands/stop-status.md)). Komenda czeka na zamek najwyżej 300 s, usuwa też sieroty `.stop-*.tmp` i nie zdejmuje blokady, gdy nie dostanie zamka. Serwer MCP, który raz zwrócił STOP (własny albo z zapisu innego procesu, także wygasającego 429), pozostaje zatrzaśnięty do restartu.

**Nie usuwaj katalogu `~/.cache/deweloperuch-mcp` ani plików w nim.** Usunięcie katalogu zdejmuje STOP razem z pauzą 429 i zamkiem, czyli omija blokadę bez sprawdzenia przyczyny. Agentom blokuje to hook Bash; człowiek powinien użyć `stop clear`.

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
| STOP (401/403/429/challenge) | blokada procesu do restartu i zapis dla innych procesów | Dotyczy wszystkich sesji w procesie (`ServiceBlockedError`, przy 429 `RateLimitedError`) i jest zapisany w `stop.json` ([STOP](#stop-blokada-między-procesami)); zapis innego procesu też blokuje zapytania. Odpowiedzi z cache nadal są zwracane. |
| Cache | w pamięci procesu | Nie jest zapisywany na dysk. TTL = `s-maxage` minus `Age`; bez `s-maxage` domyślnie 300 s (maks. 24 h). Serwis podaje `s-maxage` tylko dla `city-sales` (300 s) [P 2026-10-10]; strony RSC, `/api/cities`, `sale-events`, `map/investments/visible` i `location-search` go nie mają, więc dostają domyślne 300 s. LRU: 256 wpisów i 64 MiB. |
| Sesja zamknięta | `SessionClosedError` | Użycie po wyjściu z `Session`. |

Cel żądania jest sprawdzany przed wysłaniem według allowlisty (`allowlist.py`) i reguły D5: ścieżki z `DUMP_PATHS` (`/api/map/powiat-sales/{id}`, strona `/statystyki/ceny-transakcyjne/{mieszkania|domy}/{city}` bez `/mapa`) nigdy nie są wywoływane. `valuation-pdf` i server actions są wykluczone. Naruszenie to `InvalidInputError` z prefiksem „Błąd programu”.

## Błędy pakietu

Wszystkie błędy zamierzone dziedziczą po `DeweloperuchError(message, detail=)` (`deweloperuch_mcp.errors`) i są wspólne dla klienta, usług, CLI i MCP.

| Element | Zachowanie |
|---|---|
| `str(err)` | Komunikat domenowy po polsku: co się stało i co zrobić. Nigdy nie zawiera ścieżek serwisu, nazw propsów ani treści odpowiedzi. To jedyny tekst, który trafia do modelu (MCP) i po `Błąd:` na stderr (CLI). |
| `err.detail` | Szczegóły techniczne: cel zapytania, status HTTP, fragment ciała odpowiedzi; `None`, gdy ich nie ma. Trafia do logu serwera MCP (stderr) i do linii `Szczegóły:` w CLI. |
| Escapowanie | `detail` jest zawsze przepuszczany przez `errors.printable`: każdy znak niedrukowalny (sekwencje sterujące OSC/CSI, końce linii, sterowanie bidi) staje się `\xNN`, `\uNNNN` lub `\UNNNNNNNN`. Polskie litery zostają. |
| Kontekst domenowy | Usługi dopisują przedrostek, np. `Inwestycja 'smolna': …`, `Wyszukiwanie ofert w 'warszawa': …`; `NotFoundError` ma komunikat domenowy (np. „Nie znaleziono inwestycji 'smolna'. …”). Typ błędu, `pause_seconds` i `detail` są zachowane. |
| Dane niezgodne z kontraktem | `UnexpectedResponseError` z dopiskiem „Serwis mógł się zmienić po aktualizacji: ponawianie nie pomoże, zgłoś to użytkownikowi.” |
| Etykiety decyzji (np. „D5”) | Tylko w `detail`, nigdy w `str(err)`. |

Mapowanie na kody wyjścia CLI: [docs/cli/README.md](cli/README.md#kody-wyjścia). Mapowanie na wynik MCP: [docs/mcp/README.md](mcp/README.md#błędy).

## Dla deweloperów

`DEWELOPERUCH_UPDATE_SNAPSHOTS=1 uv run pytest tests/test_mcp_server.py` odświeża zrzut `tests/snapshots/mcp_tools.json` (pełny `tools/list`, `instructions`, `serverInfo.name`). To narzędzie testów, nie konfiguracja produktu; zwykły `uv run pytest` porównuje wynik ze zrzutem.

`DEWELOPERUCH_LIVE=1` (z markerem pytest `live`) włącza żywe testy e2e z `tests/e2e/`: `DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e -rs --maxfail=3`. Bez niej testy e2e są pomijane. To przełącznik tylko dla testów, nie konfiguracja produktu; serwer i CLI go nie czytają. Przebieg wymaga zgody (D9), więcej: [tests/e2e/README.md](../tests/e2e/README.md).

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

Po STOP w odpowiedzi probe zapisuje `stop.json` (źródło `probe`) i pisze na stderr `Zapisano STOP: inne procesy też zostały wstrzymane.` Gdy zapis jest już aktywny (z dowolnego procesu), kończy się kodem 3 bez zapytania; błędy użycia (kod 2) są sprawdzane wcześniej. Linia STOP dla challenge na statusie spoza 401/403/429 brzmi `STOP: challenge Cloudflare (captcha/WAF)`, bez „HTTP 200”.

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
| STOP | `stop.json` | Jak w probe: po STOP zapis ze źródłem `scan_bundles`; przy aktywnym zapisie (z dowolnego procesu) skan kończy się kodem 3 przed zapytaniem. |

_Źródło: `src/deweloperuch_mcp/throttle.py`, `src/deweloperuch_mcp/identity.py`, `src/deweloperuch_mcp/retry_after.py`, `src/deweloperuch_mcp/http_policy.py`, `recon/config.py`, `recon/http_common.py`, `recon/probe.py`, `recon/scan_bundles.py`, `recon/allowlist.py`, `recon/flight.py`, `src/deweloperuch_mcp/client/transport.py`, `src/deweloperuch_mcp/services.py`, `src/deweloperuch_mcp/cli.py`, `src/deweloperuch_mcp/mcp_server.py`, `src/deweloperuch_mcp/allowlist.py`, `src/deweloperuch_mcp/flight.py`, `src/deweloperuch_mcp/errors.py`_
