# deweloperuch-mcp

An integration layer between an agent/LLM and the data of [deweloperuch.pl](https://deweloperuch.pl) (developers' asking prices, transactions from the Real Estate Price Register (RCN), market statistics, valuation).

```
deweloperuch.pl → client (JSON API + RSC) → domain/services → CLI + MCP → agent
```

## Status

**Stages 1-2 (discovery + capability matrix): completed 2026-10-09.** Package bootstrap (A#1) is done: `pyproject.toml`, the shared request limiter and tests. S1a is done: the package core (client, DTOs, domain, services). S1b is done: the `deweloperuch` CLI and the `deweloperuch-mcp` MCP server (stdio) with four capabilities: location search, offer search, an offer with its price history, and an investment with its offers. Chosen stack (D8): Python >= 3.11, MCP SDK (`mcp`), pydantic, httpx, typer; pytest, pytest-socket, respx, ruff, mypy, uv. The agent team is configured (rules and workflows in [CLAUDE.md](CLAUDE.md)).

Note on language: the documentation is in English, but the product texts it quotes (MCP tool descriptions, schema field descriptions, `instructions`, error messages, CLI output and `--help`) are in Polish, as in the code, and are quoted verbatim. Longer quotes come with a short English summary.

## Quickstart

```
uv sync
uv run deweloperuch locations search krak     # CLI (sends live requests to the service, through the 1/s limiter)
uv run deweloperuch-mcp                       # MCP server on stdio; usually started by an MCP client
```

Live requests (every CLI command without `--help` and every MCP tool) go to deweloperuch.pl; rules for polite use: [CLAUDE.md](CLAUDE.md). `--help` sends no requests.

MCP client configuration (`mcpServers` format):

```json
{
  "mcpServers": {
    "deweloperuch": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/deweloperuch-mcp", "deweloperuch-mcp"]
    }
  }
}
```

Alternative: `"command": "/path/to/deweloperuch-mcp/.venv/bin/deweloperuch-mcp"`. The host should read the server's stderr; details: [docs/mcp/README.md](docs/mcp/README.md).

## MCP tools

The `deweloperuch-mcp` server (stdio only, read-only); overview: [docs/mcp/README.md](docs/mcp/README.md).

| Tool | Description |
|---|---|
| [`search_locations`](docs/mcp/tools/search_locations.md) | Finds cities, districts and streets by a name fragment and returns `city_slug`. |
| [`search_offers`](docs/mcp/tools/search_offers.md) | A page of developers' apartment offers in a city or the whole of Poland, with price and area filters. |
| [`get_offer`](docs/mcp/tools/get_offer.md) | One offer with its full price history. |
| [`get_investment`](docs/mcp/tools/get_investment.md) | An investment with its developer, average prices and a list of offers. |

## CLI commands

Overview, output format and exit codes 0-7: [docs/cli/README.md](docs/cli/README.md).

| Command | Description |
|---|---|
| [`deweloperuch locations search QUERY`](docs/cli/commands/locations-search.md) | Finds cities, districts and streets; returns the city slug. |
| [`deweloperuch offers search CITY`](docs/cli/commands/offers-search.md) | Searches offers in a city or the whole of Poland with filters and price sorting. |
| [`deweloperuch offers get OFFER_ID --investment SLUG`](docs/cli/commands/offers-get.md) | Shows an offer with its price history. |
| [`deweloperuch investments get SLUG`](docs/cli/commands/investments-get.md) | Shows an investment with its developer and offers. |
| [`deweloperuch stop status [--json]`](docs/cli/commands/stop-status.md) | Shows the STOP lock shared by all processes (offline; exit code 3 when active). |
| [`deweloperuch stop clear`](docs/cli/commands/stop-clear.md) | Clears the STOP lock; humans only, after checking the cause (agents do not run it). |

## For developers

```
uv sync
uv run pytest            # no network (--disable-socket)
uv run ruff check .
uv run mypy src
```

Offline tests use real raw RSC payloads in `tests/fixtures/rsc/` (not mocks built from assumptions).

The e2e suite `tests/e2e/` (61 tests) runs against the live service, so it is outside the regular `uv run pytest` and needs the user's explicit consent (D9). Do not run it in parallel with recon-verifier or drift-checker; STOP ends the run with exit code 3. The plan is 45 live requests (58 at most), with a hard limit of 60 per run:

```
DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e -rs --maxfail=3
```

Scenarios and budget: [tests/e2e/README.md](tests/e2e/README.md).

Configuration, the request limiter and the lock file: [docs/configuration.md](docs/configuration.md).

## Documentation

| Document | Contents |
|---|---|
| [docs/discovery/README.md](docs/discovery/README.md) | Map of the data layer: service architecture, access channels, key findings |
| [docs/discovery/endpoints.md](docs/discovery/endpoints.md) | Catalog of 34 `/api/*` endpoints and server actions |
| [docs/discovery/pages-rsc.md](docs/discovery/pages-rsc.md) | SSR pages as a data source: filters, sorting, pagination, props |
| [docs/discovery/entities.md](docs/discovery/entities.md) | Entities, identifiers, relations, value dictionaries |
| [docs/discovery/samples/](docs/discovery/samples/) | Trimmed response samples (the basis of contract tests) |
| [docs/capability-matrix.md](docs/capability-matrix.md) | Capabilities → requests → CLI / MCP tool → status |
| [docs/open-questions.md](docs/open-questions.md) | Gaps, hypotheses, questions awaiting a decision |
| [docs/decisions.md](docs/decisions.md) | Architecture decisions and the proposal for the first vertical slice |
| [docs/mcp/README.md](docs/mcp/README.md) | MCP server: tools, client configuration, argument rules, errors, result sizes |
| [docs/cli/README.md](docs/cli/README.md) | The `deweloperuch` CLI: commands, output format, exit codes |
| [docs/configuration.md](docs/configuration.md) | Environment variables, configuration files and the request limiter |
| [CLAUDE.md](CLAUDE.md) | Shared rules for working with the service, file ownership and the team's A/B/C workflows |
| [handoffs/INDEX.md](handoffs/INDEX.md) | Index of handoffs between sessions |
| [prompts/agent-team-setup.md](prompts/agent-team-setup.md) | The meta-prompt the agent team was installed from |

## Glossary (PL → EN)

Terms used in the documentation; the service and its data are Polish.

| Polish | English |
|---|---|
| oferta | offer (one apartment on sale) |
| inwestycja | investment (a development project) |
| deweloper | developer |
| historia ceny | price history |
| cena ofertowa / cena transakcyjna | asking price / transaction price |
| rynek pierwotny | primary market |
| slug miasta (`city_slug`) | city slug |
| lokalizacja | location (city, district or street) |
| metraż | area (m²) |
| limiter | request limiter (shared between processes) |
| STOP | STOP lock (written after 401/403/429/challenge; stops all processes) |
| kod wyjścia | exit code |
| rekonesans (recon) | reconnaissance (discovery of the service's data) |

## Package structure

The package is `src/deweloperuch_mcp/`. The product's public interface is `cli.py` and `mcp_server.py`; the rest is internal:

- `cli.py`: the `deweloperuch` CLI (typer), exit codes `ExitCode`; [docs/cli/README.md](docs/cli/README.md)
- `mcp_server.py`: the `deweloperuch-mcp` MCP server (stdio), four tools; [docs/mcp/README.md](docs/mcp/README.md)
- `mcp_results.py`: the representation of results for MCP (shortened items, no `null` fields) on top of the domain model
- `client/`: the HTTP client (`transport.py`, `json_api.py`, `rsc.py`) and DTOs (`dto.py`); settings: [docs/configuration.md](docs/configuration.md)
- `domain/`: models and normalization (`models.py`, `normalize.py`)
- `services.py`: services over the client (the only entry point for CLI and MCP)
- `errors.py`: the `DeweloperuchError` error hierarchy (`message`, `detail`)
- `flight.py`: the RSC decoder; `allowlist.py`: the read allowlist (`recon/flight.py` and `recon/allowlist.py` re-export them)

## Recon tools

The scripts require Python >= 3.11 (the system `python3` on macOS is 3.9; alternative: `uv run python recon/<script>.py`).

- `recon/config.py`: shared script configuration (re-exports `BASE_URL` and `USER_AGENT` from `deweloperuch_mcp.identity`, `TODO(U1)`; the shared request limiter with state in `~/.cache/deweloperuch-mcp/throttle.lock`, see [docs/configuration.md](docs/configuration.md))
- `python3 recon/scan_bundles.py`: a JS bundle scanner for detecting changes after a service deploy (build ID, `/api/*` paths, server actions). Every request goes through the shared limiter (<=1 req/s, 1 at a time), with no redirects and no retries; any error ends the whole scan. It fetches only pages from the `PAGES` list (22) and `GET /_next/static/chunks/*.js`. A live run needs the user's consent (D9), and the first scan with an empty cache is about 140 requests. `--help` sends no requests.
  - Chunk cache: `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/chunks/` (`0600` files); a chunk with a hash in its name is not fetched again. Hard limit `MAX_CHUNKS = 400` chunk requests per scan.
  - `--json`: `build_id`, `pages`, `chunks`, `chunks_fetched`, `chunks_cached`, `api`, `actions`, always `incomplete` (a list of reasons for an incomplete result, empty for a complete one), and with `--compare` also `drift` (`api_added`, `api_removed`, `actions_added`, `actions_removed`).
  - `--compare FILE`: comparison with a baseline `{"api": [...], "actions": [names]}`; only `/api` paths and action names count (action IDs and the build ID are ignored). `--baseline-out FILE`: writes the baseline (atomically, must be a file path); refused for an incomplete result.
  - Exit codes: 0 success or no differences; 2 usage error (bad baseline, a directory instead of a file, failed write, a request outside the allowlist); 3 STOP (401/403/429/Cloudflare challenge, also an earlier STOP written by another process: the scan is aborted before the request); 4 other HTTP or network error, or a redirect; 5 the limiter requires waiting longer than 60 s; 6 incomplete result (with `--compare` it takes precedence over 0 and 7; also exceeding `MAX_CHUNKS`); 7 differences from `--compare` (only for a complete result).
  - stderr: `Uwaga (niepełny wynik): …` (affects completeness; the text output then has the header `# NIEPEŁNY WYNIK`) and `Info: …` (no effect). Example: `python3 recon/scan_bundles.py --json --compare baseline.json`.
- `recon/http_common.py`: the shared urllib transport (`read_body`, `get_once`) for probe and the scanner.
- `deweloperuch_mcp.http_policy` (`src/deweloperuch_mcp/http_policy.py`, stdlib only): pure response-policy functions (STOP, challenge, pauses, `body_length`), used by recon and meant for the future httpx client.
- `recon/flight.py`: a re-export from `deweloperuch_mcp.flight`; the RSC payload decoder (`flight(html_path)`, `flight_from_html(html)`, `find_json_after(text, prop)`, `component_props(text)`); as a CLI it requires Python >= 3.11
- `recon/allowlist.py`: a re-export from `deweloperuch_mcp.allowlist`; the allowlist of `/api/*` paths and page routes (consistent with `endpoints.md` and `pages-rsc.md`; without `/api/valuation-pdf` and server actions)
- `python3 recon/probe.py`: the only permitted way to make live verification requests (a single GET, through the shared limiter). It accepts only paths from the allowlist, never full URLs. One run is one request, with no redirects and no retries.
  - `api PATH`: `GET /api/*`, JSON result. `page PATH [--prop NAME]`: a page as RSC (`RSC: 1`, deterministic `_rsc`); without `--prop` it lists the props with data (name, type, size).
  - Options: `--save NAME[.VARIANT]` (writes to `docs/discovery/samples/<api|page>.NAME[.VARIANT].json`, never overwrites; arrays trimmed to 3 elements, large maps with numeric keys to 2 keys, personal data replaced with `"[usunięte]"`), `--max-wait SECONDS` (default 60), `--trim N` (default 3), `--full`.
  - Exit codes: 0 success; 2 usage or allowlist error (request not sent); 3 STOP (401/403/429/Cloudflare challenge, also an earlier STOP written by another process, in which case nothing is sent: stop the series and report); 4 other HTTP or network error, response too large (32 MiB), truncated or read for too long; 5 the limiter requires waiting longer than `--max-wait`; 6 a 2xx response without the expected data.
  - Example: `python3 recon/probe.py api "/api/cities?q=krak"`. Live series need the user's consent (D9), see [CLAUDE.md](CLAUDE.md).
