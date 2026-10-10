# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/).

## [Unreleased]

### Added
- Zestaw e2e `tests/e2e/` (60 testów: MCP 48, CLI 10, recon 2) na żywym serwisie: `DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e -rs`; wymaga zgody (D9), plan ok. 46 zapytań, limit 60. Testy offline korzystają teraz z prawdziwych surowych payloadów RSC (`tests/fixtures/rsc/`). Zob. [tests/e2e/README.md](tests/e2e/README.md).
- Trwały STOP między procesami. Po 401, 403, 429 albo challenge Cloudflare każdy proces (CLI, serwer MCP, `recon/probe.py`, `recon/scan_bundles.py`) zapisuje blokadę w `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/stop.json`, obok `throttle.lock` (format 1, `0600`, zapis atomowy pod zamkiem). Dopóki zapis jest aktywny, żaden proces nie wysyła zapytań. 429 wygasa po pauzie; 401, 403 i challenge są bezterminowe; nieczytelny zapis (także symlink, FIFO, katalog, obce `source`, niekanoniczny `reason`) to STOP bezterminowy. Pakiet zapisuje STOP zaraz po nagłówkach, recon po przeczytaniu ciała. Szczegóły: [docs/configuration.md](docs/configuration.md#stop-blokada-między-procesami).
- `deweloperuch stop status [--json]`: pokazuje blokadę STOP (czasy, źródło, PID, ścieżka); offline, bez zamka, niczego nie tworzy; kod 0 bez STOP lub przy wygasłym, 3 przy aktywnym. Dokumentacja: [docs/cli/commands/stop-status.md](docs/cli/commands/stop-status.md).
- `deweloperuch stop clear`: zdejmuje blokadę STOP pod zamkiem limitera (czeka na zamek najwyżej 300 s, po 2 s notatka na stderr, po limicie kod 1 bez zdejmowania), usuwa sieroty `.stop-*.tmp`, nie skraca pauzy 429. Tylko dla użytkownika; agentom blokuje ją hook Bash i reguła w `CLAUDE.md`, nie ma narzędzia MCP do zdejmowania. Dokumentacja: [docs/cli/commands/stop-clear.md](docs/cli/commands/stop-clear.md).
- Serwer MCP `deweloperuch-mcp` (stdio, `serverInfo.name` `deweloperuch`, `version` z metadanych pakietu, `instructions`) z narzędziami `search_locations`, `search_offers` (`per_page` 10 lub 50, domyślnie 10), `get_offer` i `get_investment` (`limit` domyślnie 20, maks. 200). Wyniki są strukturalne i powtórzone jako kompaktowy JSON, bez pól `null` (poza `total` w `search_locations`). Dokumentacja: [docs/mcp/README.md](docs/mcp/README.md).
- CLI `deweloperuch` z komendami `locations search QUERY`, `offers search CITY` (`--price-min`, `--price-max`, `--area-min`, `--area-max`, `--sort price_asc|price_desc`, `--page`, `--per-page 10|50|100`), `offers get OFFER_ID --investment SLUG` i `investments get SLUG` (`--history`, `--limit`); we wszystkich `--json`. Kody wyjścia 0–7 (`cli.ExitCode`); błędy na stderr jako `Błąd:` i `Szczegóły:`. Dokumentacja: [docs/cli/README.md](docs/cli/README.md).
- `[project.scripts]`: `deweloperuch` i `deweloperuch-mcp`.
- `mcp_results` (reprezentacja wyników dla MCP), `services.WHOLE_COUNTRY`, `services.PerPage`, `errors.printable` (escapowanie znaków niedrukowalnych w `detail`) oraz `DeweloperuchError.detail`.
- Wewnętrzny rdzeń pakietu (S1a, bez CLI i MCP): klient HTTP `client/` (transport z limiterem, cache w pamięci, `json_api`, `rsc`, DTO), `domain/` (modele, normalizacja), `services.py`, `errors.py` (hierarchia `DeweloperuchError`), `flight.py` i `allowlist.py` w pakiecie. Nowe `DUMP_PATHS` w allowliście (zrzuty D5, których klient nie woła). Szczegóły: [docs/configuration.md](docs/configuration.md).
- `recon/scan_bundles.py`: nowe `--compare PLIK` (różnice `/api` i nazw akcji względem baseline'u, kod 7), `--baseline-out PLIK`, cache chunków w `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/chunks/`, limit `MAX_CHUNKS = 400`, pole `incomplete` (oraz `drift` z `--compare`) w `--json` i nowe kody wyjścia 2-7. Szczegóły: [README.md](README.md), [docs/configuration.md](docs/configuration.md).
- `recon/http_common.py`: wspólny transport urllib (`read_body`, `get_once`) dla probe i skanera.
- `src/deweloperuch_mcp/http_policy.py`: czyste funkcje polityki odpowiedzi (STOP, challenge, pauzy, `body_length`) dla recon i przyszłego klienta HTTP.
- `recon/probe.py`: narzędzie deweloperskie do pojedynczych zapytań weryfikacyjnych GET (`api`, `page`), tylko ścieżki z allowlisty, przez wspólny limiter; `--save` zapisuje przycięte próbki bez danych osobowych. Szczegóły: [README.md](README.md), [docs/configuration.md](docs/configuration.md).
- `recon/allowlist.py`: allowlista ścieżek API i tras stron dla probe.
- `src/deweloperuch_mcp/retry_after.py`: wspólny parser `Retry-After` (sekundy albo data HTTP); `recon/config.py` reeksportuje go razem z `DEFAULT_MAX_WAIT`.
- Wspólny limiter zapytań do deweloperuch.pl między procesami (min. 1 s odstępu, 1 zapytanie naraz), stan w `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/throttle.lock`. Szczegóły: [docs/configuration.md](docs/configuration.md).
- Respektowanie zmiennej środowiskowej `XDG_CACHE_HOME` przy wyborze katalogu zamka (względna lub pusta wartość jest ignorowana).
- `recon/config.py`: wspólne `BASE_URL`, `USER_AGENT` (tymczasowy, `TODO(U1)`) i limiter dla skryptów `recon/`; skrypty recon wymagają Pythona >= 3.11.
- Bootstrap pakietu `deweloperuch-mcp` (`pyproject.toml`, uv, ruff, mypy, pytest z `--disable-socket`). Brak jeszcze narzędzi MCP i komend CLI.

### Changed
- Zmiana zachowania kodów (wersja niewydana, bez `**BREAKING:**`): przy aktywnym zapisie STOP komendy danych CLI, `recon/probe.py` i `recon/scan_bundles.py` kończą się kodem 3 bez zapytania. W czasie pauzy po 429 zapisanej przez inny proces dawały wcześniej czekanie albo kod 5; teraz kod 3. Kod 5 (`LimiterWaitError`) zostaje dla pauz bez zapisu (502/503/504) i dla reszty pauzy 429 po ręcznym `stop clear`. Wcześniej STOP nie był utrwalany między uruchomieniami. Tak samo reagują narzędzia MCP (`isError` z `STOP:`).
- Komunikaty STOP dla modelu (MCP i CLI): pierwszy STOP mówi też, że inne procesy zostały wstrzymane (bez pauzy limitera); powtórny w procesie to „… jest już przerwana; zapytanie nie zostało wysłane. Powód: …”; osobne teksty dla STOP z zapisu (401/403/challenge, 429 z „jeszcze ok. N s”, nieczytelny zapis). Challenge na statusie spoza 401/403/429 ma etykietę „challenge Cloudflare (captcha/WAF)” bez „HTTP 200”; to samo w linii STOP recon. Teksty nie zawierają czasów, źródła, ścieżek ani sposobu zdjęcia blokady. Zob. [docs/mcp/README.md](docs/mcp/README.md#błędy).
- `instructions` serwera MCP: przy STOP model ma przestać używać narzędzi, niczego nie ponawiać, nie szukać obejścia, zgłosić powód użytkownikowi i niczego sam nie odblokowywać ani nie uruchamiać ponownie (zrzut `tests/snapshots/mcp_tools.json` odświeżony; schematy narzędzi bez zmian).
- Porada przy kodzie 3 w CLI (`STOP_ADVICE`): „Nie uruchamiaj kolejnych poleceń deweloperuch ani pętli: przerwij i zgłoś to użytkownikowi. Blokada obejmuje też inne procesy.”
- `recon/probe.py` i `recon/scan_bundles.py`: po STOP zapisują blokadę (źródła `probe`, `scan_bundles`) i piszą na stderr „Zapisano STOP: inne procesy też zostały wstrzymane.”; opis kodu 3 w `--help` rozszerzony.
- Serwer MCP po STOP pozostaje zatrzaśnięty do restartu, także po `stop clear` albo wygaśnięciu 429.
- Komunikaty błędów klienta i usług są domenowe (co się stało i co zrobić), bez ścieżek, nazw propsów i treści odpowiedzi; szczegóły techniczne są w `err.detail` (zawsze escapowane), a etykieta „(D5)” tylko tam. Usługi dopisują kontekst, np. „Inwestycja 'smolna': …”. Zob. [docs/configuration.md](docs/configuration.md#błędy-pakietu).
- `recon/flight.py` i `recon/allowlist.py` reeksportują moduły pakietu, a probe korzysta z nich bez zmiany zachowania (API i CLI bez zmian). `recon/config.py` ma nowe reeksporty.
- **BREAKING:** `recon/scan_bundles.py` wysyła żądania przez wspólny limiter (≤1 req/s), pobiera tylko strony z listy `PAGES` i chunki `/_next/static/chunks/*.js`, nie podąża za przekierowaniami, nie ponawia i kończy cały skan przy pierwszym błędzie (STOP 401/403/429/challenge to kod 3). Wcześniej: własny `sleep` 1 s zamiast limitera, `urlopen` z domyślnym podążaniem za przekierowaniami i brak obsługi STOP. Wymaga Pythona >= 3.11.
- `recon/probe.py`: komunikat przy za dużej odpowiedzi brzmi „recon nie służy do zrzutów” (wcześniej „probe…”); zachowanie, flagi i kody bez zmian.
- `BASE_URL` i `USER_AGENT` zdefiniowane w `src/deweloperuch_mcp/identity.py` (jedno miejsce, D9); `recon/config.py` je reeksportuje. Nazwy i wartości bez zmian.
- `recon/flight.py` objęty lintem (ruff); nowe funkcje `flight_from_html(html)` i `component_props(text)`.
- **BREAKING:** `recon/flight.py` jako CLI wymaga Pythona >= 3.11 (na 3.9 czytelny komunikat zamiast działania).

### Fixed
- `search_offers` (MCP) i `offers search` (CLI) znów działają na żywym serwisie. Parser RSC nie widział wiersza z danymi za wierszami tekstowymi `T` (bez `\n`), więc każde wywołanie kończyło się błędem „Na stronie serwisu brakuje oczekiwanych danych…”.
- Nieznane miasto w `search_offers` / `offers search` daje „Serwis nie zna miasta '<slug>'…” (CLI kod 7) zamiast „Serwis mógł się zmienić…” (kod 6).

### Removed
- `probe.rsc_token` w `recon/probe.py` (nieużywana funkcja).
