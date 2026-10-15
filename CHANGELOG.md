# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Links to the project's [website](https://mbratkowski.github.io/deweloperuch-mcp-site/) and its [documentation in Polish](https://mbratkowski.github.io/deweloperuch-mcp-site/docs/), with a visual install guide, in the README.

### Changed
- Maintenance, not part of the package: a daily workflow (`.github/workflows/stats.yml`) archives GitHub traffic, release downloads, repository counters and PyPI downloads as CSV files on the `stats` branch. See [CONTRIBUTING.md](CONTRIBUTING.md#statistics-archive).
- New official icon (a builder in a hard hat labelled MCP+CLI) in the README and the Claude Desktop extension, in every size from 16 to 512 px (thicker strokes at 32 and 64 px, a hand-drawn 16 px version). It is used with permission of the deweloperuch.pl authors and is not covered by the MIT licence; see [NOTICE](NOTICE).
- `make icons` builds the images from the raster `assets/icon-source.webp` and needs ImageMagick 7 (`magick`) instead of `rsvg-convert`. `assets/icon.svg` only wraps `icon.png` now, for the README of the releases up to 0.1.2.
- The homepage in the package metadata (PyPI), the extension manifest and the Claude Code plugin is the website.

### Removed
- The old icon drawings `assets/icon-small.svg` and `assets/icon-tiny.svg`.

## [0.1.2] - 2026-10-14

### Added
- Agent skill `deweloperuch-cli`, which teaches AI coding agents (Claude Code, Codex, Cursor and others) to use the `deweloperuch` CLI. Source in `skills/deweloperuch-cli/` (`SKILL.md`, `EXAMPLES.md`; `REFERENCE.md` is generated from the CLI by `make skill`). Install with `npx skills add MBratkowski/deweloperuch-mcp`, with the Claude Code plugin marketplace (`/plugin marketplace add MBratkowski/deweloperuch-mcp`, then `/plugin install deweloperuch@deweloperuch-mcp`), or without Node.js with `deweloperuch skill install`. See [README](README.md#3-agent-skill-for-the-cli).
- New offline command group `deweloperuch skill`: `install` (`--agent`, `--project` / `--user`, `--dir PATH`, `--force`; never writes through symlinks and does not overwrite a different copy without `--force`), `show` and `path`. See [docs/cli/commands/skill.md](docs/cli/commands/skill.md).
- Package `tooling/` for non-business helpers outside the layers (standard library only, imported only by the CLI); it holds the skill installer. See [CONTRIBUTING.md](CONTRIBUTING.md#architecture-rules).
- README install guide from no terminal to expert, with troubleshooting.

### Changed
- The client identifies itself honestly: User-Agent `deweloperuch-mcp/<version> (+https://github.com/MBratkowski/deweloperuch-mcp)` instead of a browser-like one. The authors of deweloperuch.pl agreed to the project's use of the service on 2026-10-14, with no conditions; the client stays frugal (at most 1 request per second, cache, STOP). See [docs/configuration.md](docs/configuration.md).
- The build backend is hatchling; the wheel ships the skill. `make smoke` also installs the skill from the wheel and compares it with `skills/`.

## [0.1.1] - 2026-10-14

### Added
- Four MCP prompts that appear in Claude Desktop as ready-made commands: `znajdz_mieszkanie`, `ocen_oferte`, `przeswietl_dewelopera` and `porownaj_miasta`. They send no requests; they guide the model through the 13 tools. See [docs/mcp/prompts.md](docs/mcp/prompts.md).
- Distribution on PyPI: `uvx deweloperuch-mcp` runs the server, `uvx --from deweloperuch-mcp deweloperuch --help` the CLI, and `pip install deweloperuch-mcp` works too.
- Metadata for the official MCP Registry: entry `io.github.MBratkowski/deweloperuch-mcp` (`packaging/registry/server.json`); the release attaches a `server.json` with the bundle's sha256.
- Claude Desktop extension icons in several sizes (16 to 512 px, simplified drawings for the small sizes) and `make icons` to regenerate them (needs `rsvg-convert` from librsvg).

### Changed
- The release workflow is split into a build job and separate GitHub Release and PyPI jobs (trusted publishing, environment `pypi`). See [CONTRIBUTING.md](CONTRIBUTING.md#packaging-and-releasing).
- README: install options are now the Claude Desktop extension, `uvx` from PyPI, `uvx` from GitHub (pinned to `@v0.1.1`) and from source; badges added.

## [0.1.0] - 2026-10-14

### Added
- Claude Desktop extension `deweloperuch-mcp-<version>.mcpb` (one-click install, uv runtime, macOS and Linux; Windows is not supported) and an installable wheel and sdist, so the server also runs with `uvx --from git+https://github.com/MBratkowski/deweloperuch-mcp deweloperuch-mcp`. `make package` builds them, `make smoke` checks them. See [README](README.md#install).
- CI (`make fast` and the offline tests on every push and pull request) and a release workflow that builds the artifacts and attaches them to a GitHub release for every `v*` tag. See [CONTRIBUTING.md](CONTRIBUTING.md#packaging-and-releasing).
- MCP server `deweloperuch-mcp` (stdio, read-only) with 13 tools and the matching `deweloperuch` CLI commands. See [docs/mcp/README.md](docs/mcp/README.md) and [docs/cli/README.md](docs/cli/README.md).
  - Search and details: `search_locations`, `search_offers`, `get_offer`, `search_investments`, `get_investment`, `search_developers`, `get_developer`.
  - Statistics and valuation: `get_market_statistics`, `get_transaction_statistics` (RCN), `rank_locations`, `get_building`, `estimate_property_value`, `get_government_statistics` (GUS and NBP time series for Poland, aggregates and 66 cities; command `stats government`).
- `search_offers` / `offers search` filters `district`, `price_dropped`, `status` (`active`, `archived`, `all`) and `price_per_m2_min` / `price_per_m2_max`; sorts `price_per_m2_asc`, `price_per_m2_desc`, `area_asc`, `area_desc` and `biggest_drop`.
- `get_offer` / `offers get` return `price_flags`: lowest price of the last 30 and 90 days, number of price changes, largest drop and rise, and a `suspicious_reduction` flag.
- Links to the public pages of deweloperuch.pl in results (`list_url`, `investment_url`, `developer_url`, `stats_url`, `ranking_url`, `building_url`); see [docs/mcp/README.md](docs/mcp/README.md#links-to-service-pages).
- A request limiter shared by all processes (at most 1 request per second, one at a time) and an in-memory response cache (at most 300 s). See [docs/configuration.md](docs/configuration.md).
- A persistent STOP lock shared by all processes: after a 401, 403, 429 or a Cloudflare challenge no process sends requests until the lock expires (429) or is cleared by hand. New commands `deweloperuch stop status [--json]` and `deweloperuch stop clear`. See [docs/configuration.md](docs/configuration.md#stop-shared-lock-between-processes).
- Development tools: `make fast` and `make check` quality gates (ruff, mypy, import-linter, vulture, complexity and duplication reports), an offline test suite with real stored responses, golden outputs for the CLI and MCP server, and an opt-in live end-to-end suite (`DEWELOPERUCH_LIVE=1`).
- `recon/probe.py` and `recon/scan_bundles.py`, maintainer scripts for checking the service and detecting changes after a deploy. See [docs/configuration.md](docs/configuration.md#development-scripts-recon).

### Changed
- RCN unit and transaction identifiers in the samples and tests are pseudonymised.
- **BREAKING:** every MCP tool rejects arguments that are not in its schema (`additionalProperties: false`) with an error that lists the allowed names. Clients that relied on unknown arguments being silently ignored now get an error. Argument validation errors are now in Polish instead of the SDK's English text. See [docs/mcp/README.md](docs/mcp/README.md#errors).
- **BREAKING:** `recon/scan_bundles.py` goes through the shared limiter, fetches only a fixed list of pages and chunks, follows no redirects, does not retry and ends at the first error. `recon/flight.py` and the recon scripts require Python 3.11 or newer.
- With an active STOP lock, CLI data commands and the recon scripts end with exit code 3 without sending a request (before, they could wait or end with code 5).
- Error messages describe what happened and what to do, without service paths or response content; technical details are in the log (MCP) or on a `Szczegóły:` line (CLI). After a STOP the MCP server stays halted until it is restarted.
- The MCP server `instructions` explain the three kinds of prices (asking, RCN transaction, official NBP/GUS), sparing use and what to do on a STOP.
- Responses that the CDN serves past their freshness are cached for 300 s instead of not at all; `no-store`, `no-cache` and errors are still never cached.
- Internal: the package is organised into the layers `api`, `models`, `usecases` and `consumers` plus `bootstrap.py`, and the tests mirror it; entry points and behaviour are unchanged. See [CONTRIBUTING.md](CONTRIBUTING.md#architecture-rules).

### Fixed
- `search_offers` / `offers search` work on the live service again (the page data parser missed the data row after text rows).
- An unknown city gives "Serwis nie zna miasta ..." (CLI exit code 7) instead of a "service may have changed" error (code 6).
- The cache stores responses that have `max-age` but no `s-maxage`, respects `no-store` and `no-cache`, and no longer sends repeated requests while a response is fresh.
- One malformed GUS dataset no longer breaks the others on the statistics page.
- MCP validation errors no longer contain a link to the validation library's documentation.

[Unreleased]: https://github.com/MBratkowski/deweloperuch-mcp/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/MBratkowski/deweloperuch-mcp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/MBratkowski/deweloperuch-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/MBratkowski/deweloperuch-mcp/releases/tag/v0.1.0
