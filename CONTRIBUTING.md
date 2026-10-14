# Contributing

Thank you for your interest. This project is an unofficial, read-only client of a service run by other people, so the rules about how it talks to that service matter as much as the code rules.

## Setup

Requirements: Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```
uv sync
make fast     # ruff, ruff format --check, mypy, import-linter: a few seconds
make check    # fast + the offline tests + dead-code check + complexity and duplication reports
```

Run `make fast` before every pull request and `make check` before asking for a review. Every `make` target is offline.

## Polite-client rules

The service is a community project. Code and tests must keep these rules:

- Never send more than 1 request per second, and only 1 at a time. All processes share one limiter (see [docs/configuration.md](docs/configuration.md)); do not add a second code path to the service that skips it.
- Read only. Never add a call that creates or changes data on the service, and never submit forms.
- Never bypass protections. On 401, 403, 429 or a challenge (captcha, WAF) the client stops and records it; do not add retries or workarounds around that.
- Never change the `User-Agent` to imitate a browser or hide what the client is.
- Honour the cache headers and `Retry-After`.
- Tests never touch the network (`pytest-socket` enforces it) and use real responses stored in `docs/discovery/samples/` and `tests/fixtures/`. The optional live suite in `tests/e2e/` (`DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e`) sends real requests: run it only when a change really needs it, never in a loop and never in CI.

## Architecture rules

The package `src/deweloperuch_mcp/` has the layers `consumers` (CLI and MCP) → `bootstrap` → `api` → `usecases` → `models`; a layer imports only the ones to its right. A short version of the rules (full text: [docs/decisions.md](docs/decisions.md), D16 and D17):

- One pattern per layer: `models/` are frozen dataclasses; `usecases/` have one module per operation with an `execute` method; `api/` has `adapters/` (`*_api.py`), `dto/` (`*_dto.py`, with `to_model()`), `queries/` (`*_query.py`) and `http/`; every MCP tool is a `*Tool` class.
- A module's file name matches its main class (`SearchOffers` in `search_offers.py`); no module name repeats across layers.
- Folders named after a role (for example `adapters/`, `tools/`) hold the main classes; folders called `support/` hold shared helpers.
- New behaviour starts in the models or use cases, not in the CLI or MCP code. Both consumers present the same use cases.

`make fast` (import-linter) and the architecture tests enforce most of this.

## Tests

- `tests/unit/` mirrors `src/`: the test for `src/deweloperuch_mcp/<path>/<module>.py` is `tests/unit/<path>/test_<module>.py`.
- `tests/support/` holds test infrastructure only (fakes, builders, checks, the live harness); it contains no tests.
- Other folders: `contract` (samples against the DTOs), `integration`, `characterization` (golden outputs of the CLI and MCP in `tests/golden/`), `architecture`, `safeguards`, `recon_scripts`, `e2e`.
- After an intended change of tool descriptions or output, refresh the snapshot with `DEWELOPERUCH_UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/consumers/mcp/test_server.py` and the goldens with `DEWELOPERUCH_UPDATE_GOLDEN=1 uv run pytest tests/characterization`, then review the diff.

## Language

- Product text (MCP tool descriptions, error messages, CLI output and `--help`) is in Polish, as the service and its users are Polish.
- Documentation, code comments, commit messages and issues are in English. Polish product text is quoted verbatim in the docs.

## Documentation

A change to a tool, a command, an option or an environment variable updates the matching page in `docs/mcp/`, `docs/cli/` or `docs/configuration.md` and adds a line under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md).

## Reporting issues

Open an issue with the command or tool call, the exact output and the commit you run. If the service changed its responses, say so: the client then reports that the service may have changed. Do not paste personal data. For a security problem see [SECURITY.md](SECURITY.md).
