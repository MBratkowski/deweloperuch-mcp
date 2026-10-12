# Configuration

State after S1b. The package has an internal HTTP client with an in-memory cache and two entry points: the [`deweloperuch`](cli/README.md) CLI and the [`deweloperuch-mcp`](mcp/README.md) MCP server. Neither has its own environment variables or configuration files (the values below are constants in the code).

## Environment variables

| Name | Type | Default | Description |
|---|---|---|---|
| `XDG_CACHE_HOME` | absolute path | `~/.cache` | The standard XDG variable. The directory of the limiter lock and the STOP record is `$XDG_CACHE_HOME/deweloperuch-mcp`. An empty or relative value is ignored (`~/.cache` is used). Processes with different `XDG_CACHE_HOME` do not see each other's STOP or lock. |

The code reads no other environment variables.

## Files

| Path | Description |
|---|---|
| `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/throttle.lock` | The lock (`flock`) and state of the shared request limiter. Created automatically (directory, file with `0600` permissions). An internal protocol between processes: do not edit. |
| `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/stop.json` | The STOP record shared by all processes (see [STOP](#stop-shared-lock-between-processes)). Created after 401/403/429/challenge; cleared by the user with `deweloperuch stop clear`. Do not edit by hand. |
| `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/chunks/` | The JS chunk cache of the `recon/scan_bundles.py` scanner (the path after `/_next/static/chunks/`). `0600` files, atomic write, only for a complete 200 with a non-empty body. Names with a hash are immutable, so such a chunk is not fetched again; an empty file is fetched again, and chunks without a hash in the name on every scan. It can be deleted with no side effects (the next scan fetches the chunks anew). |

## Request limiter

All processes on one machine (the `recon/` scripts and the package client) go through the same lock, so together they keep the D2 policy ([decisions.md](decisions.md)).

| Parameter | Value | Description |
|---|---|---|
| Interval between requests | 1 s (minimum) | Counted from the end of the previous request. It may only be lengthened. |
| Concurrency | 1 request at a time | Across processes and threads. |
| Max wait (`max_wait`) | 60 s | A longer required pause ends with an error instead of sleeping. It does not cover waiting for the lock while another process's request is running (that is bounded by the request timeout). |
| Max pause from `Retry-After` | 3600 s | A longer value is recorded as 3600 s and reported as an error. |

Behavior from the user's point of view:

- A process killed during a request does not hold the lock forever. The next process will still wait the standard interval.
- After a wait error (`WaitTooLongError`, message „Następne zapytanie do deweloperuch.pl wolno wysłać dopiero za N s…”) wait the stated time and retry. As a last resort (a human) delete the `throttle.lock` file itself, but only when no process is using the service for certain and the `Retry-After` time has passed; do not clear a STOP record this way (use `stop clear`).
- A `Retry-After` longer than 1 h is clipped to 1 h and reported as an error, and the next request waits that hour.
- Supported systems: Linux and macOS. On Windows the limiter reports a readable error (no `fcntl.flock`).

## STOP: shared lock between processes

After 401, 403, 429 or a Cloudflare challenge a process writes STOP to `stop.json` next to `throttle.lock`. While the record is active, no process (CLI, MCP server, `recon/probe.py`, `recon/scan_bundles.py`) sends requests: the CLI, probe and the scanner end with exit code 3, and the MCP server returns `isError` with `STOP:`. The package writes STOP right after the response headers, recon after reading the body (a known limitation: an interruption while reading the body of a 401/403/429 will not leave a record).

| Property | Value |
|---|---|
| Location | `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/stop.json` |
| Format | JSON, `"format": 1`: `{"format": 1, "since": ISO-UTC, "status": 401\|403\|429\|"challenge", "reason": text, "until": ISO-UTC\|null, "source": "pakiet"\|"probe"\|"scan_bundles", "pid": number}` |
| Contents | Only the status and the canonical reason text (`reason`); no target, URL, headers or response content. |
| Permissions, write | `0600`; atomic write (temporary file `.stop-*.tmp`, `fsync`, `os.replace`), only under the `throttle.lock` lock. |
| Read | `slot()` reads the record under the lock, before counting time: with an active record nothing is sent, and the limiter's timing state stays untouched. `stop status` reads without the lock. |

Validity rules:

- **429** expires: `until` is the write time plus the limiter pause (`max(Retry-After, 60 s)`, at most 3600 s). A 429 without a known pause is indefinite.
- **401, 403, challenge** do not expire (`until` is `null`; `until` in such a record is ignored). A challenge always has `status` `"challenge"`, also with a 429 or 403 status.
- **The first active record wins**; a later STOP can only extend the end or make the record indefinite. An expired record is replaced by a new one.
- **An unreadable record is an indefinite STOP** (fail-closed): bad JSON, a missing key, `format` and `pid` other than an integer, a time without a time zone, `status` outside 401/403/429/`challenge`, `reason` inconsistent with the status, `source` outside `pakiet`/`probe`/`scan_bundles`, a file over 64 KiB, a symlink, FIFO, directory, a read error. The content of such a file does not reach any message (`stop status` gives only a short description of the problem).
- The pause after a 429 is also in the timing state of `throttle.lock`. Clearing the record does not shorten it; after `stop clear`, code 5 (`LimiterWaitError`) may therefore still mean the rest of the pause for a while.

Clearing: only by the user, `deweloperuch stop clear` ([description](cli/commands/stop-clear.md)), after checking the cause (`deweloperuch stop status`, [description](cli/commands/stop-status.md)). The command waits for the lock at most 300 s, also removes orphaned `.stop-*.tmp` files and does not clear the lock when it cannot get the lock. An MCP server that returned STOP once (its own or from another process's record, also an expiring 429) stays latched until restart.

**Do not delete the `~/.cache/deweloperuch-mcp` directory or the files in it.** Deleting the directory clears STOP together with the 429 pause and the lock, that is, it bypasses the block without checking the cause. The Bash hook blocks this for agents; a human should use `stop clear`.

## Package client

The client (`deweloperuch_mcp.client.transport`) is synchronous (`httpx`), with the User-Agent from `identity`. Every request, including reading the body, fits in one slot of the shared limiter.

| Parameter | Value | Description |
|---|---|---|
| Limiter `max_wait` | 60 s | As above; a longer wait is a `LimiterWaitError`. |
| Request timeout | 30 s | |
| Body read limit | 120 s | |
| Body size limit | 32 MiB | A larger response is an error. |
| Redirects, retries | none | |
| Pause after 429 | at least 60 s | `max(Retry-After, 60)`. |
| Pause after 502/503/504 | `Retry-After` or 30 s | |
| STOP (401/403/429/challenge) | process block until restart and a record for other processes | Applies to all sessions in the process (`ServiceBlockedError`, for a 429 `RateLimitedError`) and is written to `stop.json` ([STOP](#stop-shared-lock-between-processes)); another process's record also blocks requests. Responses from the cache are still returned. |
| Cache | in process memory | Not written to disk. TTL = freshness minus `Age`, at most 300 s. Freshness is `s-maxage`, without it `max-age`, without both 300 s. TTL <= 0 means no cache; so do `no-store` and `no-cache` (any letter case, also with a value). `private` and `must-revalidate` do not change the TTL. Errors (also „no such page”) are not cached. The computed TTL is logged at DEBUG (`TTL cache …`, only `Cache-Control` and `Age`); no entry point enables DEBUG by default. LRU: 256 entries and 64 MiB. |
| Closed session | `SessionClosedError` | Use after leaving a `Session`. |

The request target is checked before sending against the allowlist (`allowlist.py`) and the D5 rule: paths from `DUMP_PATHS` (`/api/map/powiat-sales/{id}`, the page `/statystyki/ceny-transakcyjne/{mieszkania|domy}/{city}` without `/mapa`) are never called. `valuation-pdf` and server actions are excluded. A violation is an `InvalidInputError` with the prefix „Błąd programu”.

## Package errors

All intended errors inherit from `DeweloperuchError(message, detail=)` (`deweloperuch_mcp.errors`) and are shared by the client, services, CLI and MCP.

| Element | Behavior |
|---|---|
| `str(err)` | A domain-level message in Polish: what happened and what to do. It never contains service paths, prop names or response content. It is the only text that reaches the model (MCP) and follows `Błąd:` on stderr (CLI). |
| `err.detail` | Technical details: the request target, HTTP status, a fragment of the response body; `None` when there are none. Goes to the MCP server log (stderr) and to the `Szczegóły:` line in the CLI. |
| Escaping | `detail` always passes through `errors.printable`: every non-printable character (OSC/CSI control sequences, line endings, bidi controls) becomes `\xNN`, `\uNNNN` or `\UNNNNNNNN`. Polish letters stay. |
| Domain context | Services prepend a prefix, e.g. `Inwestycja 'smolna': …`, `Wyszukiwanie ofert w 'warszawa': …`; `NotFoundError` has a domain message (e.g. „Nie znaleziono inwestycji 'smolna'. …”). The error type, `pause_seconds` and `detail` are preserved. |
| Data not matching the contract | `UnexpectedResponseError` with the suffix „Serwis mógł się zmienić po aktualizacji: ponawianie nie pomoże, zgłoś to użytkownikowi.” |
| Decision labels (e.g. „D5”) | Only in `detail`, never in `str(err)`. |

Mapping to CLI exit codes: [docs/cli/README.md](cli/README.md#exit-codes). Mapping to the MCP result: [docs/mcp/README.md](mcp/README.md#errors).

## For developers

`DEWELOPERUCH_UPDATE_SNAPSHOTS=1 uv run pytest tests/test_mcp_server.py` refreshes the snapshot `tests/snapshots/mcp_tools.json` (the full `tools/list`, `instructions`, `serverInfo.name`). It is a test tool, not product configuration; a regular `uv run pytest` compares the result with the snapshot.

`DEWELOPERUCH_LIVE=1` (with the pytest marker `live`) enables the live e2e tests from `tests/e2e/`: `DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e -rs --maxfail=3`. Without it the e2e tests are skipped. It is a switch for tests only, not product configuration; the server and CLI do not read it. A run needs consent (D9); more: [tests/e2e/README.md](../tests/e2e/README.md).

## Recon scripts

The `recon/` scripts run as `python3 recon/<script>.py` require Python 3.11 or newer. The system `python3` on macOS is 3.9 and ends with a message about the required version. Alternative: `uv run python recon/<script>.py`.

`BASE_URL` and `USER_AGENT` (temporary, `TODO(U1)`, to be resolved in U1/D9) are defined in one place: `src/deweloperuch_mcp/identity.py`. `recon/config.py` re-exports them and gives them to the scripts together with the same limiter as the package.

`recon/flight.py` and `recon/allowlist.py` re-export the implementations from the package (`deweloperuch_mcp.flight`, `deweloperuch_mcp.allowlist`). `recon/flight.py` run as a CLI also requires Python 3.11+ (it used to work on 3.9).

### `recon/probe.py`

A single GET request per run (no redirects or retries), in a slot of the same `throttle.lock` lock and with the same User-Agent as everything else. Flag and exit code details: `python3 recon/probe.py --help` and [README.md](../README.md).

| Parameter | Value | Description |
|---|---|---|
| `--max-wait` | 60 s (default) | A finite number of seconds. A longer required pause ends with code 5, without sending a request. |
| Pause after 429 | at least 60 s | `max(Retry-After, 60)`. |
| Pause after 502/503/504 | `Retry-After` or 30 s | A `Retry-After` > 3600 s is clipped to 3600 s. |
| Response limit | 32 MiB | A larger response ends with code 4 (D5: recon is not for dumps). |
| Response read limit | about 120 s | Worst case about 120 s + 2 × 30 s. A response shorter than `Content-Length` is code 4, with no sample written. |
| `--save` | `docs/discovery/samples/` | The only write directory; an existing file is not overwritten. |

After a STOP in a response, probe writes `stop.json` (source `probe`) and prints `Zapisano STOP: inne procesy też zostały wstrzymane.` to stderr. When a record is already active (from any process), it ends with code 3 without a request; usage errors (code 2) are checked earlier. The STOP line for a challenge on a status other than 401/403/429 reads `STOP: challenge Cloudflare (captcha/WAF)`, without „HTTP 200”.

Probe reads no environment variables of its own. The `Retry-After` parser (seconds or an HTTP date) is shared with the package.

### `recon/scan_bundles.py`

The JS bundle scanner (detecting changes after a deploy, D7). All requests go through the same `throttle.lock` lock and with the same User-Agent. Flags, exit codes and the `--json` format: `python3 recon/scan_bundles.py --help` and [README.md](../README.md).

| Parameter | Value | Description |
|---|---|---|
| `max_wait` | 60 s (fixed) | No flag. A longer required pause ends the scan with code 5, before sending a request. |
| Pauses, response limits | as in probe | Pause after 429 at least 60 s, after 502/503/504 `Retry-After` or 30 s; response limit 32 MiB and read time as above. |
| Redirects, retries | none | Any error (also 3xx) ends the whole scan. |
| `MAX_CHUNKS` | 400 | Hard limit of chunk requests per scan (also when cache files are unreadable); exceeding it is code 6. |
| Cache | `chunks/` | See the "Files" table. The scanner respects `XDG_CACHE_HOME`. |
| STOP | `stop.json` | As in probe: after STOP a record with source `scan_bundles`; with an active record (from any process) the scan ends with code 3 before a request. |

_Source: `src/deweloperuch_mcp/throttle.py`, `src/deweloperuch_mcp/identity.py`, `src/deweloperuch_mcp/retry_after.py`, `src/deweloperuch_mcp/http_policy.py`, `recon/config.py`, `recon/http_common.py`, `recon/probe.py`, `recon/scan_bundles.py`, `recon/allowlist.py`, `recon/flight.py`, `src/deweloperuch_mcp/client/transport.py`, `src/deweloperuch_mcp/services.py`, `src/deweloperuch_mcp/cli.py`, `src/deweloperuch_mcp/mcp_server.py`, `src/deweloperuch_mcp/allowlist.py`, `src/deweloperuch_mcp/flight.py`, `src/deweloperuch_mcp/errors.py`_
