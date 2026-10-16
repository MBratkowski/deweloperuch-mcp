# CLI `deweloperuch`

A command line over the same services as the [MCP server](../mcp/README.md). Read-only; requests go through the shared limiter (at most 1 per second, 1 at a time). The script is `deweloperuch` (`[project.scripts]`), that is `uv run deweloperuch …` or `.venv/bin/deweloperuch …`.

```
Usage: deweloperuch [OPTIONS] COMMAND [ARGS]...

Commands:
  locations    Lokalizacje: miasta, dzielnice, ulice.
  offers       Oferty mieszkań od deweloperów.
  investments  Inwestycje deweloperskie.
  developers   Deweloperzy.
  buildings    Budynki z rejestru cen transakcyjnych (RCN): lokale i ich
               transakcje.
  valuation    Wycena mieszkania z cen transakcyjnych (RCN) w okolicy.
  stats        Statystyki: rynek ofert miasta, ceny transakcyjne (RCN) miasta,
               ranking miast i powiatów oraz statystyki rządowe GUS i NBP.
  stop         Blokada STOP: po 401, 403, 429 albo challenge Cloudflare żaden
               proces (CLI, serwer MCP, recon) nie wysyła zapytań. Działa
               offline.
  skill        Skill deweloperuch-cli dla agentów AI (Claude Code, Codex,
               Cursor i innych): jak używać tego CLI. Zalecana instalacja: npx
               skills add MBratkowski/deweloperuch-mcp (wybierasz agenta); bez
               Node.js: deweloperuch skill install. Działa offline.
```

`deweloperuch` without arguments prints the help and ends with exit code 2 (a click convention). The CLI's own help and output texts are Polish product texts and are quoted verbatim here; the built-in help and usage-error texts of typer/click are in English.

## Troubleshooting: another `deweloperuch` on PATH

Check the commands in `deweloperuch --help` before using an installed executable. This Python package lists `locations`, `offers`, `investments`, `developers`, `buildings`, `valuation`, `stats`, `stop` and `skill`. The legacy Node package `deweloperuch-poc` instead lists `overview`, `search`, `compare`, `changes`, `history`, `brief` and `mcp-config`; its help also exits successfully. Keep the legacy installation and select the Python package explicitly:

```
uvx --from deweloperuch-mcp deweloperuch --help
```

Use the same `uvx --from deweloperuch-mcp deweloperuch` prefix for subsequent commands. Both help commands are offline; the first `uvx` run may need to download the package.

## Commands

| Command | Purpose |
|---|---|
| [`locations search QUERY`](commands/locations-search.md) | Finds cities, districts and streets; returns the city slug for `offers search`. |
| [`offers search CITY`](commands/offers-search.md) | Searches apartment offers in a city (or `polska`) with price, area, price-per-m², district, status and price-drop filters and sorting; at most 20 pages of results. |
| [`offers get OFFER_ID --investment SLUG`](commands/offers-get.md) | Shows an offer with its price history and price flags. |
| [`investments search [CITY]`](commands/investments-search.md) | Searches investments of a city (or by `--name` across Poland). |
| [`investments get SLUG`](commands/investments-get.md) | Shows an investment with its developer and offers. |
| [`developers search NAME`](commands/developers-search.md) | Finds developers by name; returns the developer slug. |
| [`developers get SLUG`](commands/developers-get.md) | Shows a developer profile: summary, investments and cities. |
| [`buildings get SLUG`](commands/buildings-get.md) | Shows a building from the RCN with its units and transactions (`--trend` adds the neighbourhood trend). |
| [`valuation estimate --lat --lng --area`](commands/valuation-estimate.md) | Estimates an apartment's value at a point from nearby RCN transactions. |
| [`stats market CITY`](commands/stats-market.md) | Shows offer-market statistics of one city: distributions and the largest developers. |
| [`stats transactions CITY`](commands/stats-transactions.md) | Shows RCN transaction prices of a city by month or quarter. |
| [`stats cities`](commands/stats-cities.md) | Shows a ranking of places or powiats by RCN transactions. |
| [`stats government LOCATION DATASET`](commands/stats-government.md) | Shows GUS and NBP statistics of `polska`, an aggregate or a city as a table of periods (`--periods`, default 12, max 1000). |
| [`stop status [--json]`](commands/stop-status.md) | Shows the STOP lock shared by all processes; offline, immediately. |
| [`stop clear`](commands/stop-clear.md) | Clears the STOP lock. Only after checking the cause. |
| [`skill install\|show\|path`](commands/skill.md) | The `deweloperuch-cli` agent skill: installs it into an agent's skills folder, prints it or shows its folder; offline. |

Typical order: `locations search` → `offers search` → `investments get` or `offers get`; `investments search` and `developers search` turn names into slugs. `stats government` and `stats cities` need no earlier search. `valuation estimate` takes coordinates (for example from `locations search` or `investments get`).

## Output format

- **Text** (default, stdout): in Polish, numbers with digit grouping and a decimal comma (`1 620 175 PLN`), without plural forms. For districts and streets the number of offers is `ofert: ok. N` (for districts it is the number of active offers; for streets it is an approximation).
- **`--json`** (stdout): the full domain model as JSON (`indent=2`), all fields including `null`. It is a different, richer representation than in MCP (where items are shortened and have no `null`). A command has no `--limit` default cut where MCP has one (e.g. `investments get`, `buildings get`, `valuation estimate` show everything without `--limit`).
- **Errors** (stderr, no traceback):
  - `Błąd: <message>`
  - `Szczegóły: <detail>` (when present; target, status and body fragment, non-printable characters written as `\xNN`/`\uNNNN`)
  - with code 3 an additional line (`STOP_ADVICE` in `consumers/cli/support/common.py`): `Nie uruchamiaj kolejnych poleceń deweloperuch ani pętli: przerwij i zgłoś to użytkownikowi. Blokada obejmuje też inne procesy.`

## STOP

After 401, 403, 429 or a Cloudflare challenge a process writes STOP to a file next to `throttle.lock` ([docs/configuration.md](../configuration.md#stop-shared-lock-between-processes)). The record is shared by all processes on the machine: the CLI, the MCP server, `recon/probe.py` and `recon/scan_bundles.py`. While it is active, none of them sends requests:

- the data commands, probe and the scanner end with exit code 3 without a request; the MCP server returns `isError` with a text starting with `STOP:`. A shell loop therefore stops at the first command after STOP, also when the STOP was written by another process;
- **429** expires by itself after the pause (`max(Retry-After, 60 s)`); during it, commands from another process give code 3, not waiting or code 5;
- **401, 403 and a challenge** are indefinite: clear them by hand with `stop clear` after checking the cause;
- **an unreadable record** (bad JSON, another format, a symlink, FIFO, directory, foreign `source`, `reason` inconsistent with the status, a file over 64 KiB) is an indefinite STOP, so that a file error does not open the way to the service;
- code 5 (`LimiterWaitError`) remains for pauses without a record (502/503/504) and for the rest of a 429 pause after the record is cleared by hand;
- check the state with [`stop status`](commands/stop-status.md) (code 0 without STOP or with an expired one, 3 with an active one). **Only the person responsible for the machine clears it**, with [`stop clear`](commands/stop-clear.md), after checking the cause; automated agents and scripts must not run it. Deleting the cache directory also clears STOP, so do not clear it that way.

An MCP server that returned STOP once (its own or from another process's record) stays latched until restart, also after the record is cleared or a 429 expires.

## Exit codes

The `ExitCode` constants (`src/deweloperuch_mcp/consumers/cli/support/common.py`):

| Code | Name | Meaning |
|---|---|---|
| 0 | `OK` | Success. |
| 1 | `UNEXPECTED` | Another error, e.g. `SessionClosedError` or a program error (with a traceback). `stop clear`: the lock was not obtained within 300 s or the record cannot be removed. |
| 2 | `INVALID_INPUT` | A bad argument (`InvalidInputError`) or a typer/click usage error: wrong type, a value outside the list, a missing required option, `deweloperuch` without arguments. |
| 3 | `STOP` | `ServiceBlockedError` / `RateLimitedError` (401, 403, 429, challenge) or an earlier STOP written by any process (the command sends nothing); also `stop status` with an active lock. Stop and report to the user. |
| 4 | `SERVICE_ERROR` | A service error: 5xx, network, a redirect, another 4xx, a response too large or too slow. |
| 5 | `LIMITER_WAIT` | The shared limiter requires a longer pause than allowed (60 s); nothing was sent. Applies to pauses without a STOP record (502/503/504) and the rest of a 429 pause after the record is cleared by hand; while STOP is active it is code 3. |
| 6 | `UNEXPECTED_RESPONSE` | A 2xx response not matching the contract (the service may have changed). |
| 7 | `NOT_FOUND` | No such investment, offer, developer, building or city, or no estimate or transaction prices for the place. |

## Configuration

No flags or environment variables of its own. The limiter and cache: [docs/configuration.md](../configuration.md).

_Source: `src/deweloperuch_mcp/consumers/cli/app.py`, `src/deweloperuch_mcp/consumers/cli/commands/`, `src/deweloperuch_mcp/consumers/cli/presenters/`, `src/deweloperuch_mcp/consumers/cli/support/common.py`, `src/deweloperuch_mcp/throttle.py`, `uv run deweloperuch --help`_
