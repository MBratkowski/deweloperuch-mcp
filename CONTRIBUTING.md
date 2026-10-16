# Contributing

Thank you for your interest. This project is an unofficial, read-only client of a service run by other people, so the rules about how it talks to that service matter as much as the code rules.

## Setup

Requirements: Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```
uv sync
make fast     # ruff, ruff format --check, mypy (also .github/scripts), import-linter: a few seconds
make check    # fast + the offline tests + dead-code check + complexity and duplication reports
```

Run `make fast` before every pull request and `make check` before asking for a review. Every `make` target is offline.

On Windows, run the tools directly from PowerShell (no Make installation needed):

```powershell
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests recon packaging .github/scripts
uv run lint-imports
$env:DEWELOPERUCH_LIVE = "0"
uv run pytest -q
```

CI runs the offline tests and CLI/MCP startup checks on Windows, macOS and Linux with Python 3.11 and 3.13. Lint, format, type and import checks run on Linux; packaging and artifact smoke checks run in a separate Linux job. Tests use UTF-8 for Polish product text (`PYTHONUTF8=1` in CI).

## Packaging and releasing

```
make package   # wheel, sdist and the Claude Desktop extension (.mcpb)
make smoke     # checks the built artifacts
make skill     # regenerates skills/deweloperuch-cli/REFERENCE.md from the CLI
```

The build backend is hatchling. The wheel ships the agent skill from `skills/deweloperuch-cli/` as `deweloperuch_mcp/skills/deweloperuch-cli/`. `SKILL.md` and `EXAMPLES.md` are written by hand; `REFERENCE.md` is generated from the CLI by `make skill` (`packaging/skill_reference.py`) and a test fails when it is stale, so run `make skill` after changing any command, option or help text. `make smoke` also installs the skill from the wheel (`deweloperuch skill install --dir build/skill-smoke`) and diffs it against `skills/`. The same folder is what `npx skills add MBratkowski/deweloperuch-mcp` and the Claude Code plugin (`.claude-plugin/`) install from GitHub.

`make package` builds the wheel and sdist and runs `packaging/mcpb/build.py`, which packs the `.mcpb` with the official `mcpb` CLI (2.1.2, `manifest_version` 0.4, uv runtime). CI runs `make fast` and the offline tests on every push and pull request. A separate workflow, `stats.yml`, archives the project's statistics once a day (next section); it is not part of the package.

`make icons` regenerates the images in `assets/` from the official raster `assets/icon-source.webp`; it needs ImageMagick 7 (`magick`). It writes the extension icons (`assets/icon.png` and `assets/icons/`, white rounded tiles; at 32 and 64 px the strokes are thickened so they stay legible, and the 16 px icon is copied from the hand-drawn `assets/icon-tiny.png`), the README header images `assets/icon-on-light.png` and `assets/icon-on-dark.png`, and `assets/icon.svg`, which only wraps `icon.png` for the README of releases up to 0.1.2. The outputs are committed, so you run it only after changing the source or `icon-tiny.png`. The icon is not covered by the MIT licence (see [NOTICE](NOTICE)).

ImageMagick must be built with WebP support; check with `magick -list format | grep -i '^ *webp'` (the Homebrew build has it).

Never rename or delete a file that README.md links by an absolute URL (today `assets/icon-on-light.png`, `assets/icon-on-dark.png` and `assets/icon.svg`): the READMEs of published releases (on PyPI and GitHub) keep linking it on `main`. `tests/architecture/test_assets.py` fails otherwise; add a new file linked that way to `PUBLISHED` in that test. The same test fails when the `make icons` outputs are stale and when the homepage differs between `pyproject.toml`, the extension manifest and the Claude Code plugin files (the registry `websiteUrl` in `packaging/registry/server.json` is intentionally different).

To release:

1. Bump the version in `pyproject.toml`, `packaging/mcpb/manifest.json` and `packaging/registry/server.json` (all must match; `server.json` has two `version` fields) and move the `## [Unreleased]` entries of [CHANGELOG.md](CHANGELOG.md) under the new version. Copy `packaging/announcements/0.1.3.json` to `<version>.json` in the same directory; update its version, date and short Polish announcement copy (one to three highlights).
2. Run `make package` and `make smoke`.
3. Push a tag `v*` (for example `v0.1.1`). The release workflow builds the wheel, sdist, `.mcpb` and a `server.json` with the bundle's sha256; then two separate jobs create the GitHub Release with the artifacts and publish the package to PyPI (trusted publishing, environment `pypi`). After the GitHub Release is created, a separate job renders the Polish announcement and attaches `deweloperuch-mcp-<version>-changelog.png` to it.
4. Publish to the official MCP Registry (`io.github.MBratkowski/deweloperuch-mcp`) with `mcp-publisher`, using the `server.json` downloaded from the release:

```
mcp-publisher login github
mcp-publisher publish
```

The announcement renderer is pinned to a reviewed commit of
`MBratkowski/deweloperuch-mcp-site`; release copy comes from this repository's
`packaging/announcements/<version>.json`, not the renderer's example data.
The JSON version must match the tag. Missing or invalid copy, missing assets or
text that does not fit makes the graphics job fail; the package has already
been published. No additional token or secret is needed, and no housing data is
fetched. The job also saves the PNG as an Actions artifact.

To regenerate a published release's graphic after correcting its JSON, use
**Actions → release → Run workflow** and enter the existing tag, or run:

```bash
gh workflow run release.yml -f tag=v0.1.3
```

This manual path uses the announcement JSON from the selected workflow ref
(normally `main`) and only replaces that release's changelog PNG. It does not
build packages or publish them again. Automatic runs use the JSON committed
with the release tag. Check the workflow outcome and review the PNG before
using it in a post.

## Statistics archive

GitHub keeps a repository's traffic for 14 days and pypistats.org keeps PyPI downloads for about 180 days. The workflow `.github/workflows/stats.yml` runs `.github/scripts/archive_stats.py` daily at 04:37 UTC (and on `workflow_dispatch`) and stores the numbers as CSV files on the orphan branch `stats` of this public repository, which the first run creates. The script uses the standard library only, reads api.github.com and pypistats.org, and never contacts the deweloperuch.pl service. It sends the honest User-Agent `deweloperuch-mcp-stats (+https://github.com/MBratkowski/deweloperuch-mcp)`.

| File on `stats` | Columns | Notes |
|---|---|---|
| `github/views.csv`, `github/clones.csv` | `date,count,uniques` | traffic, 14-day window; upsert by date, older dates kept |
| `github/referrers.csv` | `captured,referrer,count,uniques` | 14-day aggregate ending on `captured` |
| `github/paths.csv` | `captured,path,title,count,uniques` | 14-day aggregate ending on `captured` |
| `github/releases.csv` | `captured,tag,asset,download_count` | cumulative downloads of release assets; drafts skipped |
| `github/repo.csv` | `captured,stars,forks,watchers` | |
| `pypi/downloads.csv` | `date,category,downloads` | `with_mirrors` and `without_mirrors` |

The branch also holds a `README.md` describing the files. Dates are UTC days and rows are sorted. A rerun on the same day replaces that day's snapshot, files are written only when they change, and the job commits as `github-actions[bot]` (`Archive project statistics for YYYY-MM-DD`) only when something changed, pushing to `stats` only.

The job runs only in `MBratkowski/deweloperuch-mcp` and only from `refs/heads/main`. The `schedule` event has no payload, so the default branch is hard-coded in the `if:`: if the default branch is renamed, change it there. Permissions are `contents: read`, and `contents: write` for the job only.

**Token.** The traffic endpoints need a token with the repository permission "Administration: read"; the job's `GITHUB_TOKEN` gets 403 there. Create a fine-grained personal access token (resource owner `MBratkowski`, only this repository, repository permission "Administration: Read-only"; Metadata read-only is added automatically) and store it as the Actions secret `STATS_TOKEN` (Settings, Secrets and variables, Actions, or `gh secret set STATS_TOKEN --repo MBratkowski/deweloperuch-mcp` and paste it at the prompt). Releases and repository counters use the job's `GITHUB_TOKEN`; pypistats gets no token. Tokens are never printed.

**Exit codes of the script and what a run means.**

| Code | Meaning | Workflow |
|---|---|---|
| 0 | archived; a source that failed gives a `::warning::` and its file stays untouched; a missing `STATS_TOKEN` only skips the traffic, with a warning | commits and pushes |
| 1 | no source could be read, nothing archived | fails before the commit |
| 2 | bad arguments | fails before the commit |
| 3 | `STATS_TOKEN` is set but GitHub refused it (401 or 403 on traffic); the rest was archived | commits and pushes, then fails the run |

A red run means exit 1, 2 or 3. For 3 the token has most likely expired or lost its permission: create a new one and update the secret. GitHub sends the failure email of a scheduled run to the person who last changed the `cron` line.

**Run it locally** (the token is read from the environment; `--repo` defaults to `GITHUB_REPOSITORY`):

```
STATS_TOKEN=... uv run --no-project --python 3.13 python .github/scripts/archive_stats.py \
    --out build/stats --repo MBratkowski/deweloperuch-mcp
```

To run the workflow by hand after it is on `main`: `gh workflow run stats.yml --repo MBratkowski/deweloperuch-mcp`. The first scheduled run happens only after the workflow is on `main`.

**Caveats.**

- GitHub disables scheduled workflows in a public repository after 60 days without repository activity; re-enable it in the Actions tab. It is not known whether the bot's pushes to `stats` count as activity.
- A ruleset or branch protection that matches all branches would reject the push to `stats`.
- `make types` type-checks `.github/scripts`; pytest `pythonpath`, ruff `src`, mypy `mypy_path` and vulture `paths` include it. The offline tests are in `tests/repo_stats/`. Nothing here is part of the published package (sdist and wheel use `only-include`).

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
- Other folders: `contract` (samples against the DTOs), `integration`, `characterization` (golden outputs of the CLI and MCP in `tests/golden/`), `architecture`, `safeguards`, `recon_scripts`, `repo_stats` (the statistics archive script, on real GitHub and PyPI responses in `tests/fixtures/repo_stats/`), `e2e`.
- After an intended change of tool descriptions or output, refresh the snapshot with `DEWELOPERUCH_UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/consumers/mcp/test_server.py` and the goldens with `DEWELOPERUCH_UPDATE_GOLDEN=1 uv run pytest tests/characterization`, then review the diff.

## Language

- Product text (MCP tool descriptions, error messages, CLI output and `--help`) is in Polish, as the service and its users are Polish.
- Documentation, code comments, commit messages and issues are in English. Polish product text is quoted verbatim in the docs.

## Documentation

A change to a tool, a command, an option or an environment variable updates the matching page in `docs/mcp/`, `docs/cli/` or `docs/configuration.md` and adds a line under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md).

## Reporting issues

Open an issue with the command or tool call, the exact output and the commit you run. If the service changed its responses, say so: the client then reports that the service may have changed. Do not paste personal data. For a security problem see [SECURITY.md](SECURITY.md).
