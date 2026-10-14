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

## Packaging and releasing

```
make package   # wheel, sdist and the Claude Desktop extension (.mcpb)
make smoke     # checks the built artifacts
make skill     # regenerates skills/deweloperuch-cli/REFERENCE.md from the CLI
```

The build backend is hatchling. The wheel ships the agent skill from `skills/deweloperuch-cli/` as `deweloperuch_mcp/skills/deweloperuch-cli/`. `SKILL.md` and `EXAMPLES.md` are written by hand; `REFERENCE.md` is generated from the CLI by `make skill` (`packaging/skill_reference.py`) and a test fails when it is stale, so run `make skill` after changing any command, option or help text. `make smoke` also installs the skill from the wheel (`deweloperuch skill install --dir build/skill-smoke`) and diffs it against `skills/`. The same folder is what `npx skills add MBratkowski/deweloperuch-mcp` and the Claude Code plugin (`.claude-plugin/`) install from GitHub.

`make package` builds the wheel and sdist and runs `packaging/mcpb/build.py`, which packs the `.mcpb` with the official `mcpb` CLI (2.1.2, `manifest_version` 0.4, uv runtime). CI runs `make fast` and the offline tests on every push and pull request.

`make icons` regenerates the extension icons in `assets/icons/` from `assets/icon.svg` (large sizes) and the simplified `assets/icon-small.svg` and `assets/icon-tiny.svg` (32 and 16 px); it needs `rsvg-convert` from librsvg. The PNGs are committed, so you run it only after changing an SVG.

To release:

1. Bump the version in `pyproject.toml`, `packaging/mcpb/manifest.json` and `packaging/registry/server.json` (all must match; `server.json` has two `version` fields) and move the `## [Unreleased]` entries of [CHANGELOG.md](CHANGELOG.md) under the new version.
2. Run `make package` and `make smoke`.
3. Push a tag `v*` (for example `v0.1.1`). The release workflow builds the wheel, sdist, `.mcpb` and a `server.json` with the bundle's sha256; then two separate jobs create the GitHub Release with the artifacts and publish the package to PyPI (trusted publishing, environment `pypi`).
4. Publish to the official MCP Registry (`io.github.MBratkowski/deweloperuch-mcp`) with `mcp-publisher`, using the `server.json` downloaded from the release:

```
mcp-publisher login github
mcp-publisher publish
```

## Polite-client rules

The service is a community project. Code and tests must keep these rules:

- Never send more than 1 request per second, and only 1 at a time. All processes share one limiter (see [docs/configuration.md](docs/configuration.md)); do not add a second code path to the service that skips it.
- Read only. Never add a call that creates or changes data on the service, and never submit forms.
- Never bypass protections. On 401, 403, 429 or a challenge (captcha, WAF) the client stops and records it; do not add retries or workarounds around that.
- Never change the `User-Agent` to imitate a browser or hide what the client is. It is `deweloperuch-mcp/<version> (+repository URL)`, defined once in `identity.py`. The service's authors have agreed to the project's use of the service, with no conditions; that is why the client is open about itself, and why it must stay as frugal as above.
- Honour the cache headers and `Retry-After`.
- Tests never touch the network (`pytest-socket` enforces it) and use real responses stored in `docs/discovery/samples/` and `tests/fixtures/`. The optional live suite in `tests/e2e/` (`DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e`) sends real requests: run it only when a change really needs it, never in a loop and never in CI.

## Architecture rules

The package `src/deweloperuch_mcp/` has the layers `consumers` (CLI and MCP) → `bootstrap` → `api` → `usecases` → `models`; a layer imports only the ones to its right. Next to them stands `tooling/` (below). A short version of the rules (full text: [docs/decisions.md](docs/decisions.md), D16 and D17):

- One pattern per layer: `models/` are frozen dataclasses; `usecases/` have one module per operation with an `execute` method; `api/` has `adapters/` (`*_api.py`), `dto/` (`*_dto.py`, with `to_model()`), `queries/` (`*_query.py`) and `http/`; every MCP tool is a `*Tool` class.
- A module's file name matches its main class (`SearchOffers` in `search_offers.py`); no module name repeats across layers.
- Folders named after a role (for example `adapters/`, `tools/`) hold the main classes; folders called `support/` hold shared helpers.
- `tooling/` holds non-business helpers outside the layers (since 0.1.2; for example `AgentSkillInstaller`, which installs the agent skill). It uses the standard library only, and only `consumers/cli` imports it: it is not a use case and must not reach `api`, `usecases` or `models`, nor the other way round (D16, D17 "Tooling is not business"). Put there what is neither domain logic nor a service call.
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
