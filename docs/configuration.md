# Konfiguracja

Stan na bootstrap (A#1). Cache odpowiedzi, klient HTTP, serwer MCP i CLI jeszcze nie istnieją, więc ich ustawień tu nie ma. Dojdą razem z implementacją.

## Zmienne środowiskowe

| Nazwa | Typ | Domyślna | Opis |
|---|---|---|---|
| `XDG_CACHE_HOME` | ścieżka bezwzględna | `~/.cache` | Standardowa zmienna XDG. Katalog zamka limitera to `$XDG_CACHE_HOME/deweloperuch-mcp`. Wartość pusta lub względna jest ignorowana (użyty zostaje `~/.cache`). |

Żadnych innych zmiennych środowiskowych kod nie czyta.

## Pliki

| Ścieżka | Opis |
|---|---|
| `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/throttle.lock` | Zamek (`flock`) i stan wspólnego limitera zapytań. Tworzony automatycznie (katalog, plik z uprawnieniami `0600`). Wewnętrzny protokół między procesami: nie edytuj. |

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

## Skrypty recon

Skrypty `recon/` uruchamiane jako `python3 recon/<skrypt>.py` wymagają Pythona 3.11 lub nowszego. Systemowy `python3` z macOS to 3.9 i kończy się komunikatem o wymaganej wersji. Alternatywa: `uv run python recon/<skrypt>.py`.

`recon/config.py` udostępnia skryptom `BASE_URL`, `USER_AGENT` (tymczasowy, `TODO(U1)`, do rozstrzygnięcia w U1/D9) i ten sam limiter co pakiet.

_Źródło: `src/deweloperuch_mcp/throttle.py`, `recon/config.py`_
