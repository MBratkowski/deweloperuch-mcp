# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `get_transaction_statistics` / `stats transactions`: incomplete newest periods are marked. Each such period has `incomplete: true` (MCP: only when true; CLI `--json`: a bool on every period; the text table marks it with ` *` and a legend line), and the result has `last_complete_period` (omitted when it cannot be judged). The hint names the incomplete periods and the last period with a usual count (its data may still change); for small series it says there are too few transactions to judge. The rule is the package's own [W]: the longest trailing run of periods (at most 12 months or 4 quarters) with fewer than half of the median count of the reference window before it; not judged when that median is below 10 transactions or with fewer than 3 reference periods (open question T46). The `note` text, the tool description, the server instructions and the prompt `porownaj_miasta` changed accordingly.
- `estimate_property_value` / `valuation estimate`: `low_confidence` (`true` exactly when the estimate rests on fewer than 5 comparable transactions; present on every estimate, `false` included; omitted without one). The hint carries a caveat with the facts (number of transactions, radius, months), or a softer sentence when only the radius reached the service's ceiling of 1000 m. The CLI prints it as an `Uwaga: …` line and the valuation cautions as `Wskazówka: …`. The prompt `ocen_oferte` tells the model to pass the caveat on.
- `get_building` / `buildings get`: `non_regular_transactions` (counts of transactions with a classification other than `regular`, e.g. shares and enforcement sales; omitted in MCP when none, `{}` in CLI `--json`; the CLI prints a `Transakcje inne niż zwykłe: …` line) and `hint` (e.g. an empty neighbourhood trend). The service's averages probably do not include non-regular transactions (checked in one building, T48).

### Changed
- **BREAKING:** `rank_locations` / `stats cities`: when `--min-transactions` / `min_transactions` is not given and the sort is by price (`price_per_m2_desc`, `price_per_m2_asc`; both levels), places with fewer than 20 transactions are now left out. `transactions_desc` keeps 0; an explicit value, including 0, always wins. The MCP argument is now an integer or null with default null (it was an integer with default 0); the output `min_transactions` echoes the applied threshold; the hint says so when the default left places out. The refusal message gained „albo pusty”. For all places use `min_transactions=0` / `--min-transactions 0`.
- **BREAKING:** `get_building`: the output field `name` is optional (a blank address from the register is absent instead of an empty value). Consumers validating the strict output schema, where `name` was required, must accept its absence. In CLI `--json` `name` is `null` and the text header falls back to the city.
- `get_building`: a unit's `floor` and `rooms` are absent when the register's text is blank (they read 0); building averages, a trend quarter's price and the trend radius of 0 or less are no value.
- `estimate_property_value`: the estimate and the price per m² come as a pair; a value of 0 or less is no value. The CLI groups digits and agrees "z ostatniego miesiąca".
- Descriptions of the tools `rank_locations`, `get_transaction_statistics`, `estimate_property_value` and `get_building` and of their parameters and fields changed (see the pages under `docs/mcp/tools/`).
- Maintenance, not part of the package: the live e2e request budget is 120 (was 115); see `tests/e2e/README.md`.
- Maintenance, not part of the package: releases automatically render and attach a changelog PNG from short Polish copy in `packaging/announcements/<version>.json`. The release workflow can also regenerate only the graphic for an existing release.
- Maintenance, not part of the package: the bundle scanner `recon/scan_bundles.py` no longer ends the scan at the first moved or missing page. A page of `PAGES` that answers a redirect within the site (never followed), 404 or 410 is recorded and the scan goes on with an incomplete result, so one scan lists every such page. The exit code for it is 0 in a plain run and 6 with `--compare` or `--baseline-out` (it was 4, which stopped the scan there and left the rest of the pages and all chunks unscanned); when every page is skipped it is 6, with its own message. `--json` gains `redirects` and `missing`, and the text output a section `## strony pominięte (zaktualizuj PAGES)`. A redirect to another host, any redirect, 404 or 410 of a chunk and every other HTTP or network error still end the scan with 4, a STOP with 3. A redirect's `Location` is printed escaped and cut to 300 characters, also by `recon/probe.py`. See [docs/configuration.md](docs/configuration.md#development-scripts-recon).
- Maintenance, not part of the package: `recon/scan_bundles.py --save-pages DIR` keeps the HTML of every page that answered 2xx, byte for byte, in `DIR/<name>.html` at no extra request, for offline analysis only (never as samples or fixtures: pages may hold personal data). `DIR` must be new or empty and outside the repository, else the exit code is 2 before the first request; directories get mode 0700, files 0600 (POSIX), and nothing is overwritten.
- Maintenance, not part of the package: `PAGES` of `recon/scan_bundles.py` follows the redesign of deweloperuch.pl of 2026-10-29 (24 pages, was 22): `/statystyki/warszawa/transakcje` and `/statystyki/warszawa/dane-rzadowe` replace the two statistics routes that moved, and `/ceny-ofertowe/polska/miasta` and `/statystyki/polska/oferty` are new.

### Fixed
- `rank_locations` / `stats cities`: a price or area of 0 from the service is no value. The place sorts last on price and shows no price fields (CLI text `?`, `--json` `null`); before, Ignatki-osiedle (listed with 0) ranked as the cheapest place [P 2026-10-15].
- `get_developer` / `developers get`: a price or area of 0 from the service is no value. The service writes 0 for the averages of a developer without active offers in that city; the result showed an average price of 0 PLN next to "0 active offers" (now CLI text `?`, `--json` `null`). The averages of the page's investments and its cities follow the same rule.
- `get_building` / `buildings get`: units with an unknown floor no longer show "piętro 0".

## [0.1.3] - 2026-10-16

### Added
- Native Windows support for the CLI, MCP server and shared request limiter, with standard-library file locking, PowerShell setup instructions and offline CI on Windows, macOS and Linux (Python 3.11 and 3.13). Windows support starts in 0.1.3. [#8](https://github.com/MBratkowski/deweloperuch-mcp/issues/8)
- Links to the project's [website](https://mbratkowski.github.io/deweloperuch-mcp-site/) and its [documentation in Polish](https://mbratkowski.github.io/deweloperuch-mcp-site/docs/), with a visual install guide, in the README.

### Changed
- Maintenance, not part of the package: a daily workflow (`.github/workflows/stats.yml`) archives GitHub traffic, release downloads, repository counters and PyPI downloads as CSV files on the `stats` branch. See [CONTRIBUTING.md](CONTRIBUTING.md#statistics-archive).
- New official icon (a builder in a hard hat labelled MCP+CLI) in the README and the Claude Desktop extension, in every size from 16 to 512 px (thicker strokes at 32 and 64 px, a hand-drawn 16 px version). It is used with permission of the deweloperuch.pl authors and is not covered by the MIT licence; see [NOTICE](NOTICE).
- `make icons` builds the images from the raster `assets/icon-source.webp` and needs ImageMagick 7 (`magick`) instead of `rsvg-convert`. `assets/icon.svg` only wraps `icon.png` now, for the README of the releases up to 0.1.2.
- The homepage in the package metadata (PyPI), the extension manifest and the Claude Code plugin is the website.

### Removed
- The old icon drawings `assets/icon-small.svg` and `assets/icon-tiny.svg`.

### Fixed
- Fractional-area valuations now warn in CLI and MCP hints that the service may ignore the fractional part; requested area and the upstream estimate remain unchanged, including when comparable transactions are truncated. [#6](https://github.com/MBratkowski/deweloperuch-mcp/issues/6)
- The CLI agent skill verifies this package's command groups before using an executable found on `PATH`; a legacy CLI with the same name uses the explicit package-qualified `uvx` invocation. [#7](https://github.com/MBratkowski/deweloperuch-mcp/issues/7)

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

[Unreleased]: https://github.com/MBratkowski/deweloperuch-mcp/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/MBratkowski/deweloperuch-mcp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/MBratkowski/deweloperuch-mcp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/MBratkowski/deweloperuch-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/MBratkowski/deweloperuch-mcp/releases/tag/v0.1.0
