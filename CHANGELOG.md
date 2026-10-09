# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/).

## [Unreleased]

### Added
- `recon/probe.py`: narzędzie deweloperskie do pojedynczych zapytań weryfikacyjnych GET (`api`, `page`), tylko ścieżki z allowlisty, przez wspólny limiter; `--save` zapisuje przycięte próbki bez danych osobowych. Szczegóły: [README.md](README.md), [docs/configuration.md](docs/configuration.md).
- `recon/allowlist.py`: allowlista ścieżek API i tras stron dla probe.
- `src/deweloperuch_mcp/retry_after.py`: wspólny parser `Retry-After` (sekundy albo data HTTP); `recon/config.py` reeksportuje go razem z `DEFAULT_MAX_WAIT`.
- Wspólny limiter zapytań do deweloperuch.pl między procesami (min. 1 s odstępu, 1 zapytanie naraz), stan w `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/throttle.lock`. Szczegóły: [docs/configuration.md](docs/configuration.md).
- Respektowanie zmiennej środowiskowej `XDG_CACHE_HOME` przy wyborze katalogu zamka (względna lub pusta wartość jest ignorowana).
- `recon/config.py`: wspólne `BASE_URL`, `USER_AGENT` (tymczasowy, `TODO(U1)`) i limiter dla skryptów `recon/`; skrypty recon wymagają Pythona >= 3.11.
- Bootstrap pakietu `deweloperuch-mcp` (`pyproject.toml`, uv, ruff, mypy, pytest z `--disable-socket`). Brak jeszcze narzędzi MCP i komend CLI.

### Changed
- `BASE_URL` i `USER_AGENT` zdefiniowane w `src/deweloperuch_mcp/identity.py` (jedno miejsce, D9); `recon/config.py` je reeksportuje. Nazwy i wartości bez zmian.
- `recon/flight.py` objęty lintem (ruff); nowe funkcje `flight_from_html(html)` i `component_props(text)`.
- **BREAKING:** `recon/flight.py` jako CLI wymaga Pythona >= 3.11 (na 3.9 czytelny komunikat zamiast działania).
