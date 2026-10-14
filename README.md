<p align="center"><img src="assets/icon.svg" alt="deweloperuch-mcp icon" width="160"></p>

<h1 align="center">deweloperuch-mcp</h1>

Ask an AI assistant about new-build apartments in Poland: asking prices with their history, real transaction prices and official statistics.

An unofficial [MCP](https://modelcontextprotocol.io) server and command-line tool over the public data of [deweloperuch.pl](https://deweloperuch.pl): developers' asking prices (with price history), transaction prices from the Real Estate Price Register (RCN) and statistics of GUS and NBP. Thirteen read-only tools, usable from an MCP client such as Claude Desktop or Claude Code, or from the `deweloperuch` CLI.

> **Disclaimer.** This is an independent project. It is **not affiliated with, endorsed by or sponsored by** deweloperuch.pl, GUS, NBP or the Register's publishers.
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

Pick the option that fits you. Supported systems: macOS and Linux. **Windows is not supported** (the shared request limiter uses `fcntl` file locks).

### 1. Claude Desktop, one click

1. Download `deweloperuch-mcp-<version>.mcpb` from the [latest release](https://github.com/MBratkowski/deweloperuch-mcp/releases/latest).
2. Double-click it, or drag it into Claude Desktop → Settings → Extensions → Install.

The first start installs Python and the dependencies with [uv](https://docs.astral.sh/uv/) and takes about a minute. The extension has no command-line tool; if the server is ever stopped (STOP), see [lifting a STOP without a checkout](docs/configuration.md#lifting-a-stop-without-a-checkout).

### 2. With uv, straight from GitHub

Requires [uv](https://docs.astral.sh/uv/). Nothing to clone.

**Claude Desktop** (`claude_desktop_config.json`; any MCP client that starts a stdio server works the same way). If Claude Desktop reports `spawn uvx ENOENT`, put the full path from `which uvx` in `command`:

```json
{
  "mcpServers": {
    "deweloperuch": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/MBratkowski/deweloperuch-mcp", "deweloperuch-mcp"]
    }
  }
}
```

**Claude Code:**

```
claude mcp add deweloperuch -- uvx --from git+https://github.com/MBratkowski/deweloperuch-mcp deweloperuch-mcp
```

**CLI:**

```
uvx --from git+https://github.com/MBratkowski/deweloperuch-mcp deweloperuch --help
```

To pin a release, add `@v0.1.0` at the end of the git URL.

### 3. From source (developers)

Requirements: Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```
git clone https://github.com/MBratkowski/deweloperuch-mcp.git
cd deweloperuch-mcp
uv sync
uv run deweloperuch --help                  # sends no requests
uv run deweloperuch locations search krak   # first real request
```

As the client command use `uv run --directory /path/to/deweloperuch-mcp deweloperuch-mcp` (Claude Code: `claude mcp add deweloperuch -- uv run --directory /path/to/deweloperuch-mcp deweloperuch-mcp`). The server speaks stdio and logs to stderr. More: [docs/mcp/README.md](docs/mcp/README.md#mcp-client-configuration).

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

The layers are wired in `bootstrap.py`, and import-linter enforces the direction of imports. Design decisions and their reasons: [docs/decisions.md](docs/decisions.md). The service's data, endpoints and limits: [docs/discovery/README.md](docs/discovery/README.md). Configuration, the limiter and the STOP lock: [docs/configuration.md](docs/configuration.md).

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
| `tests/architecture/`, `tests/safeguards/` | Layering and naming rules; no-network guarantees. |
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
| [docs/mcp/README.md](docs/mcp/README.md) | The MCP server: tools, client configuration, argument rules, errors, result sizes |
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

The code is licensed under the [MIT licence](LICENSE). The licence covers code only; the samples and fixtures used for testing contain data from the sources above and are described in [NOTICE](NOTICE).

## Contributing

Issues and pull requests are welcome; please read [CONTRIBUTING.md](CONTRIBUTING.md) first, especially the polite-client rules. Security reports: [SECURITY.md](SECURITY.md).
