# deweloperuch-mcp

Warstwa integracyjna między agentem/LLM a danymi [deweloperuch.pl](https://deweloperuch.pl) (ceny ofertowe deweloperów, transakcje z Rejestru Cen Nieruchomości, statystyki rynku, wycena).

```
deweloperuch.pl → client (JSON API + RSC) → domain/services → CLI + MCP → agent
```

## Status

**Etap 1–2 (discovery + capability matrix): ukończone 2026-10-09.** Bootstrap pakietu (A#1) gotowy: `pyproject.toml`, wspólny limiter zapytań i testy. S1a gotowe: wewnętrzny rdzeń pakietu (klient, DTO, domena, usługi) bez CLI i MCP; narzędzi MCP ani komend CLI jeszcze nie ma (S1b). Stos wybrany (D8): Python >= 3.11, MCP SDK (`mcp`), pydantic, httpx, typer; pytest, pytest-socket, respx, ruff, mypy, uv. Zespół agentów skonfigurowany (zasady i przepływy w [CLAUDE.md](CLAUDE.md)).

## Dla dewelopera

```
uv sync
uv run pytest            # bez sieci (--disable-socket)
uv run ruff check .
uv run mypy src
```

Konfiguracja, limiter zapytań i plik zamka: [docs/configuration.md](docs/configuration.md).

## Dokumentacja

| Dokument | Zawartość |
|---|---|
| [docs/discovery/README.md](docs/discovery/README.md) | Mapa warstwy danych: architektura serwisu, kanały dostępu, kluczowe ustalenia |
| [docs/discovery/endpoints.md](docs/discovery/endpoints.md) | Katalog 34 endpointów `/api/*` i server actions |
| [docs/discovery/pages-rsc.md](docs/discovery/pages-rsc.md) | Strony SSR jako źródło danych: filtry, sortowanie, paginacja, propsy |
| [docs/discovery/entities.md](docs/discovery/entities.md) | Encje, identyfikatory, relacje, słowniki wartości |
| [docs/discovery/samples/](docs/discovery/samples/) | Przycięte próbki odpowiedzi (podstawa testów kontraktowych) |
| [docs/capability-matrix.md](docs/capability-matrix.md) | Capabilities → requesty → CLI / MCP tool → status |
| [docs/open-questions.md](docs/open-questions.md) | Luki, hipotezy, pytania do decyzji |
| [docs/decisions.md](docs/decisions.md) | Decyzje architektoniczne i propozycja pierwszego vertical slice |
| [docs/configuration.md](docs/configuration.md) | Zmienne środowiskowe, pliki konfiguracyjne i limiter zapytań |
| [CLAUDE.md](CLAUDE.md) | Wspólne zasady pracy z serwisem, własność plików i przepływy A/B/C zespołu agentów |
| [handoffs/INDEX.md](handoffs/INDEX.md) | Indeks handoffów między sesjami |
| [prompts/agent-team-setup.md](prompts/agent-team-setup.md) | Meta-prompt, z którego zainstalowano zespół agentów |

## Struktura pakietu

Rdzeń `src/deweloperuch_mcp/` (S1a) jest wewnętrzny, bez publicznego interfejsu produktu:

- `client/`: klient HTTP (`transport.py`, `json_api.py`, `rsc.py`) i DTO (`dto.py`); ustawienia: [docs/configuration.md](docs/configuration.md)
- `domain/`: modele i normalizacja (`models.py`, `normalize.py`)
- `services.py`: usługi nad klientem (punkt wejścia dla przyszłego CLI i MCP)
- `errors.py`: hierarchia błędów `DeweloperuchError`
- `flight.py`: dekoder RSC; `allowlist.py`: allowlista odczytu (`recon/flight.py` i `recon/allowlist.py` je reeksportują)

## Narzędzia recon

Skrypty wymagają Pythona >= 3.11 (systemowy `python3` z macOS to 3.9; alternatywa: `uv run python recon/<skrypt>.py`).

- `recon/config.py`: wspólna konfiguracja skryptów (reeksport `BASE_URL` i `USER_AGENT` z `deweloperuch_mcp.identity`, `TODO(U1)`; wspólny limiter zapytań ze stanem w `~/.cache/deweloperuch-mcp/throttle.lock`, zob. [docs/configuration.md](docs/configuration.md))
- `python3 recon/scan_bundles.py`: skaner bundli JS do wykrywania zmian po deployu serwisu (build ID, ścieżki `/api/*`, server actions). Każde żądanie idzie przez wspólny limiter (≤1 req/s, 1 naraz), bez przekierowań i ponowień; każdy błąd kończy cały skan. Pobiera tylko strony z listy `PAGES` (22) i `GET /_next/static/chunks/*.js`. Żywe uruchomienie wymaga zgody użytkownika (D9), a pierwszy skan z pustym cache to ok. 140 żądań. `--help` nie wysyła żądań.
  - Cache chunków: `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/chunks/` (pliki `0600`); chunk z hashem w nazwie nie jest pobierany ponownie. Twardy limit `MAX_CHUNKS = 400` żądań chunków na skan.
  - `--json`: `build_id`, `pages`, `chunks`, `chunks_fetched`, `chunks_cached`, `api`, `actions`, zawsze `incomplete` (lista powodów niepełnego wyniku, pusta przy pełnym), z `--compare` także `drift` (`api_added`, `api_removed`, `actions_added`, `actions_removed`).
  - `--compare PLIK`: porównanie z baseline'em `{"api": [...], "actions": [nazwy]}`; liczą się tylko ścieżki `/api` i nazwy akcji (ID akcji i build ID są ignorowane). `--baseline-out PLIK`: zapis baseline'u (atomowo, musi być ścieżką pliku); przy wyniku niepełnym odmowa.
  - Kody wyjścia: 0 sukces lub brak różnic; 2 błąd użycia (zły baseline, katalog zamiast pliku, nieudany zapis, zapytanie spoza allowlisty); 3 STOP (401/403/429/challenge Cloudflare); 4 inny błąd HTTP, sieci lub przekierowanie; 5 limiter wymaga czekania dłuższego niż 60 s; 6 wynik niepełny (z `--compare` ma pierwszeństwo przed 0 i 7; także przekroczenie `MAX_CHUNKS`); 7 różnice z `--compare` (tylko przy pełnym wyniku).
  - stderr: `Uwaga (niepełny wynik): …` (wpływa na kompletność; wynik tekstowy ma wtedy nagłówek `# NIEPEŁNY WYNIK`) i `Info: …` (bez wpływu). Przykład: `python3 recon/scan_bundles.py --json --compare baseline.json`.
- `recon/http_common.py`: wspólny transport urllib (`read_body`, `get_once`) dla probe i skanera.
- `deweloperuch_mcp.http_policy` (`src/deweloperuch_mcp/http_policy.py`, tylko stdlib): czyste funkcje polityki odpowiedzi (STOP, challenge, pauzy, `body_length`), używane przez recon i przeznaczone dla przyszłego klienta httpx.
- `recon/flight.py`: reeksport z `deweloperuch_mcp.flight`; dekoder payloadu RSC (`flight(html_path)`, `flight_from_html(html)`, `find_json_after(text, prop)`, `component_props(text)`); jako CLI wymaga Pythona >= 3.11
- `recon/allowlist.py`: reeksport z `deweloperuch_mcp.allowlist`; allowlista ścieżek `/api/*` i tras stron (zgodna z `endpoints.md` i `pages-rsc.md`; bez `/api/valuation-pdf` i server actions)
- `python3 recon/probe.py`: jedyna dozwolona droga żywych zapytań weryfikacyjnych (pojedynczy GET, przez wspólny limiter). Przyjmuje tylko ścieżki z allowlisty, nigdy pełne URL-e. Jedno uruchomienie to jedno żądanie, bez przekierowań i ponowień.
  - `api ŚCIEŻKA`: `GET /api/*`, wynik JSON. `page ŚCIEŻKA [--prop NAZWA]`: strona jako RSC (`RSC: 1`, deterministyczny `_rsc`); bez `--prop` wypisuje propsy z danymi (nazwa, typ, rozmiar).
  - Opcje: `--save NAZWA[.WARIANT]` (zapis do `docs/discovery/samples/<api|page>.NAZWA[.WARIANT].json`, nigdy nie nadpisuje; tablice przycięte do 3 elementów, duże mapy o kluczach numerycznych do 2 kluczy, dane osobowe zastąpione `"[usunięte]"`), `--max-wait SEKUNDY` (domyślnie 60), `--trim N` (domyślnie 3), `--full`.
  - Kody wyjścia: 0 sukces; 2 błąd użycia lub allowlisty (zapytanie niewysłane); 3 STOP (401/403/429/challenge Cloudflare: przerwij serię i zgłoś); 4 inny błąd HTTP, sieci, odpowiedź za duża (32 MiB), ucięta lub czytana za długo; 5 limiter wymaga dłuższego czekania niż `--max-wait`; 6 odpowiedź 2xx bez oczekiwanych danych.
  - Przykład: `python3 recon/probe.py api "/api/cities?q=krak"`. Żywe serie wymagają zgody użytkownika (D9), zob. [CLAUDE.md](CLAUDE.md).
