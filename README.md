<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/MBratkowski/deweloperuch-mcp/main/assets/icon-on-dark.png">
    <img src="https://raw.githubusercontent.com/MBratkowski/deweloperuch-mcp/main/assets/icon-on-light.png" alt="deweloperuch-mcp icon: a grinning builder in a hard hat labelled MCP+CLI" width="160">
  </picture>
</p>

<h1 align="center">deweloperuch-mcp</h1>

<p align="center">
  <a href="https://github.com/MBratkowski/deweloperuch-mcp/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/MBratkowski/deweloperuch-mcp/ci.yml?branch=main&label=CI" alt="CI"></a>
  <a href="https://github.com/MBratkowski/deweloperuch-mcp/releases/latest"><img src="https://img.shields.io/github/v/release/MBratkowski/deweloperuch-mcp" alt="Latest release"></a>
  <a href="https://pypi.org/project/deweloperuch-mcp/"><img src="https://img.shields.io/pypi/v/deweloperuch-mcp" alt="PyPI version"></a>
  <a href="https://pypi.org/project/deweloperuch-mcp/"><img src="https://img.shields.io/pypi/pyversions/deweloperuch-mcp" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT"></a>
</p>

<p align="center">
  <a href="https://mbratkowski.github.io/deweloperuch-mcp-site/"><b>Website</b></a> ·
  <a href="https://mbratkowski.github.io/deweloperuch-mcp-site/docs/"><b>Documentation in Polish</b></a>, with a visual install guide
</p>

<!-- mcp-name: io.github.MBratkowski/deweloperuch-mcp -->

Ask an AI assistant about new-build apartments in Poland: asking prices with their history, real transaction prices and official statistics.

An unofficial [MCP](https://modelcontextprotocol.io) server and command-line tool over the public data of [deweloperuch.pl](https://deweloperuch.pl): developers' asking prices (with price history), transaction prices from the Real Estate Price Register (RCN) and statistics of GUS and NBP. Thirteen read-only tools, usable from an MCP client such as Claude Desktop or Claude Code, or from the `deweloperuch` CLI.

> **Disclaimer.** This is an independent project. It is **not affiliated with, endorsed by or sponsored by** deweloperuch.pl, GUS, NBP or the Register's publishers. The authors of deweloperuch.pl have agreed to the project's use of their service; the client identifies itself as `deweloperuch-mcp/<version>` with a link to this repository.
>
> - It is **read-only**: it never creates or changes anything on the service.
> - It is a **polite client**: at most 1 request per second, one at a time, shared by all processes on your machine; responses are cached; after a 401, 403, 429 or a captcha/WAF challenge it stops sending requests until you clear the lock yourself.
> - **Please respect the service.** It is run by other people; ask narrow questions and do not build loops or bulk downloads on top of this tool.
> - Data accuracy is not guaranteed. Prices are asking or registered prices, not valuations or advice.
> - You are responsible for how you use the tool and the data, including the terms of the service.

## What you can ask

- *Buying a flat:* "Find flats of 40–55 m² in Kraków's Podgórze up to 800 000 PLN, cheapest per m² first." (The service has no filter by number of rooms; filter by area instead.)
- *Judging an offer's price:* "Is this offer a good deal? Show its price history, the lowest price of the last 30 and 90 days, and whether the reduction looks suspicious."
- *Checking a developer:* "What does this developer build, and how many offers are active in which cities?"
- *Market and transaction prices:* "How do asking prices in Gdańsk compare with registered transaction prices over the last quarters?"
- *Valuation:* "Roughly what is a 55 m² flat at this address worth, based on nearby transactions?"
- *Comparing cities:* "Rank cities by transaction price per m², and show wages and unemployment next to them."

## Install

Pick the first option that fits you; they go from no terminal to expert. Supported systems: macOS, Linux and Windows 10 (1903+) / 11 with a local NTFS cache directory.

**Windows is supported starting with 0.1.3**, including the PyPI package and `.mcpb` extension. Releases up to 0.1.2 support macOS and Linux only.

Prefer a visual walkthrough? The [install guide on the project's website](https://mbratkowski.github.io/deweloperuch-mcp-site/docs/) (in Polish) shows the installation step by step and has a prompt that lets an AI agent install it for you.

### 1. Claude Desktop, no terminal

1. Download `deweloperuch-mcp-<version>.mcpb` from the [latest release](https://github.com/MBratkowski/deweloperuch-mcp/releases/latest).
2. Double-click it, or drag it into Claude Desktop → Settings → Extensions → Install, then restart Claude Desktop.

You get: the 13 tools and 4 prompts in Claude Desktop. The extension uses the `uv` runtime (`server.type` is `uv` in its manifest), so the first start fetches Python and the dependencies and takes about a minute; you install nothing yourself. It has no command-line tool; if the server is ever stopped (STOP), see [lifting a STOP without a checkout](docs/configuration.md#lifting-a-stop-without-a-checkout).

### 2. Any MCP client, with uv

You get: the same tools in Claude Desktop, Claude Code or any client that starts a stdio server. Nothing to clone.

Install [uv](https://docs.astral.sh/uv/) once (macOS and Linux):

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows, use PowerShell ([uv installation](https://docs.astral.sh/uv/getting-started/installation/)):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new terminal after installation so it sees uv on `PATH`.

**Claude Code:**

```
claude mcp add deweloperuch -- uvx deweloperuch-mcp
```

**Claude Desktop** (`claude_desktop_config.json`; other clients use the same `command` and `args`):

```json
{
  "mcpServers": {
    "deweloperuch": {
      "command": "uvx",
      "args": ["deweloperuch-mcp"]
    }
  }
}
```

To run straight from GitHub instead of PyPI, use `uvx --from git+https://github.com/MBratkowski/deweloperuch-mcp@v0.1.3 deweloperuch-mcp` (`@v0.1.3` pins the release; drop it to follow `main`). `pip install deweloperuch-mcp` works too.

If a Windows MCP client cannot find `uvx`, use the full executable path from `(Get-Command uvx).Source` as `command`. Escape backslashes in JSON, for example `"C:\\Users\\YOUR_NAME\\.local\\bin\\uvx.exe"`. A source checkout instead uses `"command": "uv"` and `"args": ["run", "--directory", "C:\\path\\to\\deweloperuch-mcp", "deweloperuch-mcp"]`.

### 3. Agent skill for the CLI

You get: an AI coding agent that knows how to use the `deweloperuch` CLI (which command to call, how to read the output, what to do on STOP), without an MCP server. The skill is called `deweloperuch-cli`; a new agent session loads it by itself.

```
npx skills add MBratkowski/deweloperuch-mcp
```

This uses the [skills](https://github.com/vercel-labs/skills) CLI (needs Node.js) and works with any agent it supports; you choose the agent. Without Node.js:

```
uvx --from deweloperuch-mcp deweloperuch skill install
```

It writes to `~/.claude/skills/deweloperuch-cli` (Claude Code, for the user). Options: `--project` (this project's `./.claude/skills`), `--agent codex|cursor|gemini-cli|github-copilot`, `--dir PATH` (writes `PATH/deweloperuch-cli`), `--force` (replace a different copy; without it a changed copy is never overwritten, and the installer never writes through symlinks). `deweloperuch skill show` prints the skill, `deweloperuch skill path` its folder. Details: [docs/cli/commands/skill.md](docs/cli/commands/skill.md).

Claude Code plugin marketplace:

```
/plugin marketplace add MBratkowski/deweloperuch-mcp
/plugin install deweloperuch@deweloperuch-mcp
```

### 4. The CLI on its own

You get: the `deweloperuch` command for your terminal and scripts; see [docs/cli/README.md](docs/cli/README.md).

```
uvx --from deweloperuch-mcp deweloperuch --help    # one-off, nothing installed
uv tool install deweloperuch-mcp                   # installs deweloperuch and deweloperuch-mcp
deweloperuch locations search krak
```

### 5. From source (contributors)

Requirements: Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```
git clone https://github.com/MBratkowski/deweloperuch-mcp.git
cd deweloperuch-mcp
uv sync
uv run deweloperuch --help                  # sends no requests
```

As the client command use `uv run --directory /path/to/deweloperuch-mcp deweloperuch-mcp` (Claude Code: `claude mcp add deweloperuch -- uv run --directory /path/to/deweloperuch-mcp deweloperuch-mcp`). More: [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/mcp/README.md](docs/mcp/README.md#mcp-client-configuration).

### Troubleshooting

- **`uvx: command not found` or `spawn uvx ENOENT`**: install uv (option 2). Claude Desktop may not see your shell `PATH`, so put the full path from `which uvx` (macOS/Linux) or `(Get-Command uvx).Source` (PowerShell) in `command`.
- **The server does not appear in Claude Desktop**: quit and restart Claude Desktop after installing the extension or editing the config.
- **Windows with release 0.1.2 or earlier**: update to 0.1.3 or newer. For a uv tool installation, run `uv tool upgrade deweloperuch-mcp`; for pip, run `python -m pip install --upgrade deweloperuch-mcp`; for `uvx`, run `uvx --refresh deweloperuch-mcp --help`. Replace an older `.mcpb` extension with the latest release.
- **STOP / exit code 3**: after a 401, 403, 429 or a captcha/WAF challenge the client stops sending requests in every process, so as not to burden the service. A **429** expires by itself after the pause (at least 60 s). The other causes last until **you** lift them, after checking the cause (`deweloperuch stop status` shows the state; an AI agent must not lift it). The MCP server stays halted until you restart it. Details and the command: [docs/configuration.md](docs/configuration.md#stop-shared-lock-between-processes).
- **Where is the cache?** Responses are cached in memory only. The limiter lock and the STOP record live in `~/.cache/deweloperuch-mcp` (`$XDG_CACHE_HOME/deweloperuch-mcp`). Do not delete that directory: it would also lift a STOP.

## Tools

Overview, argument rules, errors and result sizes: [docs/mcp/README.md](docs/mcp/README.md).

| Tool | Description |
|---|---|
| [`search_locations`](docs/mcp/tools/search_locations.md) | Finds cities, districts and streets by a name fragment and returns `city_slug`. |
| [`search_offers`](docs/mcp/tools/search_offers.md) | A page of developers' apartment offers in a city or the whole of Poland, with price, area, price-per-m², district, status and price-drop filters and sorting. |
| [`get_offer`](docs/mcp/tools/get_offer.md) | One offer with its full price history and price flags (lowest price in 30/90 days, suspicious reduction). |
| [`search_investments`](docs/mcp/tools/search_investments.md) | Investments of a city (averages, sorting, filter by developer) or by name across Poland. |
| [`get_investment`](docs/mcp/tools/get_investment.md) | An investment with its developer, average prices and a list of offers. |
| [`search_developers`](docs/mcp/tools/search_developers.md) | Finds developers by a name fragment and returns `developer_slug`. |
| [`get_developer`](docs/mcp/tools/get_developer.md) | A developer profile: summary, investments with active offers and cities. |
| [`get_market_statistics`](docs/mcp/tools/get_market_statistics.md) | Offer-market statistics of one city: counts, price, price per m² and area distributions, the largest developers. |
| [`get_transaction_statistics`](docs/mcp/tools/get_transaction_statistics.md) | Transaction prices (RCN) of a city by month or quarter. |
| [`rank_locations`](docs/mcp/tools/rank_locations.md) | A ranking of places or powiats by RCN transactions and price per m². |
| [`get_building`](docs/mcp/tools/get_building.md) | A building from the RCN with its units and transactions. |
| [`estimate_property_value`](docs/mcp/tools/estimate_property_value.md) | An approximate apartment value at a point from nearby RCN transactions. |
| [`get_government_statistics`](docs/mcp/tools/get_government_statistics.md) | Official GUS and NBP time series (dwellings, NBP prices, unemployment, wages, demography) for Poland, aggregates and 66 cities. |

Every tool rejects arguments that are not in its schema with an error that lists the allowed names. Tool descriptions, error messages and CLI output are in Polish, because the service and its users are Polish.

## Prompts

Four ready-made prompts appear in Claude Desktop as commands. They send no requests themselves; they guide the model through the tools above. Arguments and details: [docs/mcp/prompts.md](docs/mcp/prompts.md).

| Prompt | Description |
|---|---|
| `znajdz_mieszkanie` ("Znajdź mieszkanie") | Flats from developers in one city with a budget, area and district: a table of offers from the lowest price per m². |
| `ocen_oferte` ("Oceń ofertę") | A price assessment of one offer: price history, comparison with the city market and with the valuation from nearby transactions. |
| `przeswietl_dewelopera` ("Prześwietl dewelopera") | A developer profile: where and how much it builds, its investments, active offers, prices and their changes. |
| `porownaj_miasta` ("Porównaj miasta") | A comparison of the flat market of several cities (at most 5) in one table: asking prices, RCN transaction prices, optionally wages and unemployment. |

## CLI commands

Overview, output format and exit codes: [docs/cli/README.md](docs/cli/README.md).

| Command | Description |
|---|---|
| [`deweloperuch locations search QUERY`](docs/cli/commands/locations-search.md) | Finds cities, districts and streets; returns the city slug. |
| [`deweloperuch offers search CITY`](docs/cli/commands/offers-search.md) | Searches offers in a city or the whole of Poland with filters and sorting. |
| [`deweloperuch offers get OFFER_ID --investment SLUG`](docs/cli/commands/offers-get.md) | Shows an offer with its price history and price flags. |
| [`deweloperuch investments search [CITY]`](docs/cli/commands/investments-search.md) | Searches investments of a city or by name. |
| [`deweloperuch investments get SLUG`](docs/cli/commands/investments-get.md) | Shows an investment with its developer and offers. |
| [`deweloperuch developers search NAME`](docs/cli/commands/developers-search.md) | Finds developers by name; returns the developer slug. |
| [`deweloperuch developers get SLUG`](docs/cli/commands/developers-get.md) | Shows a developer profile. |
| [`deweloperuch buildings get SLUG`](docs/cli/commands/buildings-get.md) | Shows a building from the RCN with its units and transactions. |
| [`deweloperuch valuation estimate --lat --lng --area`](docs/cli/commands/valuation-estimate.md) | Estimates an apartment's value at a point. |
| [`deweloperuch stats market CITY`](docs/cli/commands/stats-market.md) | Shows offer-market statistics of one city. |
| [`deweloperuch stats transactions CITY`](docs/cli/commands/stats-transactions.md) | Shows RCN transaction prices of a city by month or quarter. |
| [`deweloperuch stats cities`](docs/cli/commands/stats-cities.md) | Shows a ranking of places or powiats by RCN transactions. |
| [`deweloperuch stats government LOCATION DATASET`](docs/cli/commands/stats-government.md) | Shows GUS and NBP statistics of a location as a table of periods. |
| [`deweloperuch stop status [--json]`](docs/cli/commands/stop-status.md) | Shows the STOP lock shared by all processes (offline; exit code 3 when active). |
| [`deweloperuch stop clear`](docs/cli/commands/stop-clear.md) | Clears the STOP lock, after you have checked the cause. |
| [`deweloperuch skill install\|show\|path`](docs/cli/commands/skill.md) | Installs, prints or locates the `deweloperuch-cli` agent skill (offline). |

## How it works

```
deweloperuch.pl  →  api  →  models  →  usecases  →  consumers (CLI, MCP server)
```

| Layer | Role |
|---|---|
| `api/` | Talks to the service: an HTTP transport with the shared limiter, cache and STOP lock; readers for its JSON API and page data; DTOs that map responses to models. |
| `models/` | Plain frozen dataclasses (offers, investments, price history, statistics). No I/O. |
| `usecases/` | One module per operation (for example `SearchOffers`), written against ports that `api/` implements. |
| `consumers/` | The CLI and the MCP server, both thin: they parse arguments, call a use case and present the result. |

The layers are wired in `bootstrap.py`; `tooling/` holds non-business helpers (the skill installer) that only the CLI uses. Import-linter enforces the direction of imports. Design decisions and their reasons: [docs/decisions.md](docs/decisions.md). The service's data, endpoints and limits: [docs/discovery/README.md](docs/discovery/README.md). Configuration, the limiter and the STOP lock: [docs/configuration.md](docs/configuration.md).

## Development

```
uv sync
make fast     # ruff, ruff format --check, mypy, import-linter (a few seconds)
make check    # fast + the offline tests + dead-code check + complexity and duplication reports
```

Every `make` target is offline; the tests never open a network socket and run against real responses stored in `docs/discovery/samples/` and `tests/fixtures/`.

| Folder | Contents |
|---|---|
| `tests/unit/` | Unit tests mirroring `src/`. |
| `tests/contract/` | Stored service responses against the DTOs and adapters. |
| `tests/integration/` | Use cases with the real adapters over a mocked service. |
| `tests/characterization/` | Golden outputs of the CLI and MCP server (`tests/golden/`). |
| `tests/architecture/`, `tests/safeguards/` | Layering and naming rules, repository-wide consistency (identity, published assets, metadata); no-network guarantees. |
| `tests/support/` | Test infrastructure (fakes, builders, checks), no tests. |
| `tests/e2e/` | The opt-in live suite, see below. |

After an intended output change, refresh the golden outputs with `DEWELOPERUCH_UPDATE_GOLDEN=1 uv run pytest tests/characterization` and review the diff ([tests/golden/README.md](tests/golden/README.md)).

**Live end-to-end tests** are off by default. They check the installed server, the CLI and the helper scripts against the real service, so they send real requests. Run them sparingly, only when a change needs it:

```
DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e -rs --maxfail=3
```

Both the variable and `-m live` are required. Scenarios and request budget: [tests/e2e/README.md](tests/e2e/README.md). Contributing guide and release procedure: [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentation

| Document | Contents |
|---|---|
| [Website](https://mbratkowski.github.io/deweloperuch-mcp-site/) and [its docs](https://mbratkowski.github.io/deweloperuch-mcp-site/docs/) | The project's landing page and user documentation in Polish, with a visual install guide |
| [docs/mcp/README.md](docs/mcp/README.md) | The MCP server: tools, prompts, client configuration, argument rules, errors, result sizes |
| [docs/cli/README.md](docs/cli/README.md) | The `deweloperuch` CLI: commands, output format, exit codes |
| [docs/configuration.md](docs/configuration.md) | Environment variables, files, the request limiter, the cache and the STOP lock |
| [docs/discovery/README.md](docs/discovery/README.md) | Map of the data layer: service architecture, access channels, key findings |
| [docs/discovery/endpoints.md](docs/discovery/endpoints.md) | Catalog of the service's `/api/*` endpoints |
| [docs/discovery/pages-rsc.md](docs/discovery/pages-rsc.md) | Pages as a data source: filters, sorting, pagination |
| [docs/discovery/entities.md](docs/discovery/entities.md) | Entities, identifiers, relations, value dictionaries |
| [docs/discovery/samples/](docs/discovery/samples/) | Trimmed response samples (the basis of the contract tests) |
| [docs/capability-matrix.md](docs/capability-matrix.md) | Capabilities, the requests behind them and the tool or command that exposes them |
| [docs/open-questions.md](docs/open-questions.md) | Known gaps and unverified assumptions about the service |
| [docs/decisions.md](docs/decisions.md) | Architecture decisions |
| [CHANGELOG.md](CHANGELOG.md) | Changes between versions |

## Data sources and licences

- **deweloperuch.pl**: the source of all offer, investment, developer and statistics data. Its terms apply to your use of the data.
- **RCN** (Real Estate Price Register) transaction data, reached through the service. The service's authors publish raw RCN data as CC0 in their public repository.
- **GUS** (Central Statistical Office) and **NBP** (National Bank of Poland) statistics, reached through the service. Name them as the source when you republish figures.

The code is licensed under the [MIT licence](LICENSE). The licence covers code only; the samples and fixtures used for testing contain data from the sources above and are described in [NOTICE](NOTICE). The project's icon is not covered by the MIT licence either: all rights reserved, used with permission of the deweloperuch.pl authors (see [NOTICE](NOTICE)).

## Contributing

Issues and pull requests are welcome; please read [CONTRIBUTING.md](CONTRIBUTING.md) first, especially the polite-client rules. Security reports: [SECURITY.md](SECURITY.md).
