# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Links to the public pages of deweloperuch.pl in MCP and CLI results (D12): `search_offers` returns `list_url` (the same list with the same filters, sorting and page) and `investment_url` in every item; `get_offer` and `get_investment` return `investment_url` and `developer_url`. In text mode the CLI adds the lines „Ta lista na deweloperuch.pl”, the investment address under the offers, „Strona inwestycji” and „Profil dewelopera”; `--json` has the same fields. Only three page patterns confirmed [P], no link to a single offer; a missing slug means no link. A new sentence in `instructions`; results are larger (10 items about 4.5k characters, 50 about 21-23k). See [docs/mcp/README.md](docs/mcp/README.md#links-to-service-pages).
- An e2e suite `tests/e2e/` (61 tests) against the live service: `DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e -rs`; needs consent (D9), plan of 45 requests (58 at most), limit 60. Offline tests now use real raw RSC payloads (`tests/fixtures/rsc/`). See [tests/e2e/README.md](tests/e2e/README.md).
- A persistent STOP shared between processes. After 401, 403, 429 or a Cloudflare challenge every process (CLI, MCP server, `recon/probe.py`, `recon/scan_bundles.py`) writes a lock to `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/stop.json`, next to `throttle.lock` (format 1, `0600`, atomic write under the lock). While the record is active, no process sends requests. A 429 expires after the pause; 401, 403 and a challenge are indefinite; an unreadable record (also a symlink, FIFO, directory, foreign `source`, non-canonical `reason`) is an indefinite STOP. The package writes STOP right after the headers, recon after reading the body. Details: [docs/configuration.md](docs/configuration.md#stop-shared-lock-between-processes).
- `deweloperuch stop status [--json]`: shows the STOP lock (times, source, PID, path); offline, without the lock, creates nothing; exit code 0 without STOP or with an expired one, 3 with an active one. Documentation: [docs/cli/commands/stop-status.md](docs/cli/commands/stop-status.md).
- `deweloperuch stop clear`: clears the STOP lock under the limiter lock (waits for the lock at most 300 s, a stderr note after 2 s, exit code 1 after the limit without clearing), removes orphaned `.stop-*.tmp` files, does not shorten the 429 pause. For the user only; agents are blocked by the Bash hook and a rule in `CLAUDE.md`, and there is no MCP tool for clearing. Documentation: [docs/cli/commands/stop-clear.md](docs/cli/commands/stop-clear.md).
- The MCP server `deweloperuch-mcp` (stdio, `serverInfo.name` `deweloperuch`, `version` from the package metadata, `instructions`) with the tools `search_locations`, `search_offers` (`per_page` 10 or 50, default 10), `get_offer` and `get_investment` (`limit` default 20, max 200). Results are structured and repeated as compact JSON, without `null` fields (except `total` in `search_locations`). Documentation: [docs/mcp/README.md](docs/mcp/README.md).
- The `deweloperuch` CLI with the commands `locations search QUERY`, `offers search CITY` (`--price-min`, `--price-max`, `--area-min`, `--area-max`, `--sort price_asc|price_desc`, `--page`, `--per-page 10|50|100`), `offers get OFFER_ID --investment SLUG` and `investments get SLUG` (`--history`, `--limit`); `--json` in all of them. Exit codes 0-7 (`cli.ExitCode`); errors on stderr as `Błąd:` and `Szczegóły:`. Documentation: [docs/cli/README.md](docs/cli/README.md).
- `[project.scripts]`: `deweloperuch` and `deweloperuch-mcp`.
- `mcp_results` (the representation of results for MCP), `services.WHOLE_COUNTRY`, `services.PerPage`, `errors.printable` (escaping non-printable characters in `detail`) and `DeweloperuchError.detail`.
- The internal package core (S1a, without CLI and MCP): the HTTP client `client/` (transport with the limiter, in-memory cache, `json_api`, `rsc`, DTOs), `domain/` (models, normalization), `services.py`, `errors.py` (the `DeweloperuchError` hierarchy), `flight.py` and `allowlist.py` in the package. New `DUMP_PATHS` in the allowlist (D5 dumps the client does not call). Details: [docs/configuration.md](docs/configuration.md).
- `recon/scan_bundles.py`: new `--compare FILE` (differences in `/api` and action names against a baseline, exit code 7), `--baseline-out FILE`, a chunk cache in `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/chunks/`, the `MAX_CHUNKS = 400` limit, the `incomplete` field (and `drift` with `--compare`) in `--json` and new exit codes 2-7. Details: [README.md](README.md), [docs/configuration.md](docs/configuration.md).
- `recon/http_common.py`: the shared urllib transport (`read_body`, `get_once`) for probe and the scanner.
- `src/deweloperuch_mcp/http_policy.py`: pure response-policy functions (STOP, challenge, pauses, `body_length`) for recon and the future HTTP client.
- `recon/probe.py`: a development tool for single verification GET requests (`api`, `page`), only paths from the allowlist, through the shared limiter; `--save` writes trimmed samples without personal data. Details: [README.md](README.md), [docs/configuration.md](docs/configuration.md).
- `recon/allowlist.py`: the allowlist of API paths and page routes for probe.
- `src/deweloperuch_mcp/retry_after.py`: a shared `Retry-After` parser (seconds or an HTTP date); `recon/config.py` re-exports it together with `DEFAULT_MAX_WAIT`.
- A shared request limiter for deweloperuch.pl between processes (at least 1 s apart, 1 request at a time), state in `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/throttle.lock`. Details: [docs/configuration.md](docs/configuration.md).
- Support for the `XDG_CACHE_HOME` environment variable when choosing the lock directory (a relative or empty value is ignored).
- `recon/config.py`: shared `BASE_URL`, `USER_AGENT` (temporary, `TODO(U1)`) and the limiter for the `recon/` scripts; recon scripts require Python >= 3.11.
- Bootstrap of the `deweloperuch-mcp` package (`pyproject.toml`, uv, ruff, mypy, pytest with `--disable-socket`). No MCP tools or CLI commands yet.

### Changed
- The local in-memory cache keeps a response for at most 300 s (previously up to 24 h with a large `s-maxage`). See [docs/configuration.md](docs/configuration.md).
- Exit code behavior change (unreleased version, no `**BREAKING:**`): with an active STOP record, the CLI data commands, `recon/probe.py` and `recon/scan_bundles.py` end with exit code 3 without a request. During a 429 pause written by another process they used to wait or return code 5; now it is code 3. Code 5 (`LimiterWaitError`) remains for pauses without a record (502/503/504) and for the rest of a 429 pause after a manual `stop clear`. Previously STOP was not persisted between runs. The MCP tools react the same way (`isError` with `STOP:`).
- STOP messages for the model (MCP and CLI): the first STOP also says that other processes were halted (without the limiter pause); a repeat in the same process is „… jest już przerwana; zapytanie nie zostało wysłane. Powód: …”; separate texts for STOP from a record (401/403/challenge, 429 with „jeszcze ok. N s”, unreadable record). A challenge on a status other than 401/403/429 is labeled „challenge Cloudflare (captcha/WAF)” without „HTTP 200”; the same in the recon STOP line. The texts contain no times, source, paths or the way to clear the lock. See [docs/mcp/README.md](docs/mcp/README.md#errors).
- MCP server `instructions`: on STOP the model must stop using the tools, retry nothing, not look for a workaround, report the reason to the user and neither unblock nor restart anything itself (the snapshot `tests/snapshots/mcp_tools.json` was refreshed; tool schemas unchanged).
- The advice for exit code 3 in the CLI (`STOP_ADVICE`): „Nie uruchamiaj kolejnych poleceń deweloperuch ani pętli: przerwij i zgłoś to użytkownikowi. Blokada obejmuje też inne procesy.”
- `recon/probe.py` and `recon/scan_bundles.py`: after STOP they write the lock (sources `probe`, `scan_bundles`) and print „Zapisano STOP: inne procesy też zostały wstrzymane.” to stderr; the description of code 3 in `--help` was extended.
- After STOP the MCP server stays latched until restart, also after `stop clear` or after a 429 expires.
- Client and service error messages are domain-level (what happened and what to do), without paths, prop names or response content; technical details are in `err.detail` (always escaped), and the label „(D5)” only there. Services prepend context, e.g. „Inwestycja 'smolna': …”. See [docs/configuration.md](docs/configuration.md#package-errors).
- `recon/flight.py` and `recon/allowlist.py` re-export the package modules, and probe uses them with no change in behavior (API and CLI unchanged). `recon/config.py` has new re-exports.
- **BREAKING:** `recon/scan_bundles.py` sends requests through the shared limiter (<=1 req/s), fetches only pages from the `PAGES` list and `/_next/static/chunks/*.js` chunks, does not follow redirects, does not retry and ends the whole scan at the first error (a STOP 401/403/429/challenge is code 3). Before: its own 1 s `sleep` instead of the limiter, `urlopen` following redirects by default and no STOP handling. Requires Python >= 3.11.
- `recon/probe.py`: the message for a too-large response now says „recon nie służy do zrzutów” (previously „probe…”); behavior, flags and codes unchanged.
- `BASE_URL` and `USER_AGENT` are defined in `src/deweloperuch_mcp/identity.py` (one place, D9); `recon/config.py` re-exports them. Names and values unchanged.
- `recon/flight.py` is covered by lint (ruff); new functions `flight_from_html(html)` and `component_props(text)`.
- **BREAKING:** `recon/flight.py` as a CLI requires Python >= 3.11 (on 3.9 a readable message instead of running).

### Fixed
- The cache stores responses with `max-age` but no `s-maxage` (at most 300 s, after subtracting `Age`); previously pages and `/api/*` with `max-age=28800` and a large `Age` were never cached.
- Repeated requests no longer go to the service while the response is fresh in the cache.
- The cache respects `no-store` and `no-cache`; errors are not cached.
- MCP argument validation errors no longer contain the `errors.pydantic.dev` link.
- `search_offers` (MCP) and `offers search` (CLI) work on the live service again. The RSC parser did not see the data row after the `T` text rows (without `\n`), so every call ended with the error „Na stronie serwisu brakuje oczekiwanych danych…”.
- An unknown city in `search_offers` / `offers search` gives „Serwis nie zna miasta '<slug>'…” (CLI code 7) instead of „Serwis mógł się zmienić…” (code 6).

### Removed
- `probe.rsc_token` in `recon/probe.py` (an unused function).
