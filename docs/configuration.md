# Configuration

The package has an internal HTTP client (`api/http/transport.py`) with an in-memory cache and two entry points: the [`deweloperuch`](cli/README.md) CLI and the [`deweloperuch-mcp`](mcp/README.md) MCP server. Neither has its own environment variables or configuration files (the values below are constants in the code).

## Environment variables

| Name | Type | Default | Description |
|---|---|---|---|
| `XDG_CACHE_HOME` | absolute path | `~/.cache` | The standard XDG variable. The directory of the limiter lock and the STOP record is `$XDG_CACHE_HOME/deweloperuch-mcp`. An empty or relative value is ignored (`~/.cache` is used). Processes with different `XDG_CACHE_HOME` do not see each other's STOP or lock. |

The code reads no other environment variables.

## Files

| Path | Description |
|---|---|
| `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/throttle.lock` | The lock and state of the shared request limiter (`fcntl.flock` on POSIX, `msvcrt` byte-range locking on Windows). Created automatically; `0600` permissions on POSIX, inherited directory ACLs on Windows. An internal protocol between processes: do not edit. |
| `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/stop.json` | The STOP record shared by all processes (see [STOP](#stop-shared-lock-between-processes)). Created after 401/403/429/challenge; cleared by the user with `deweloperuch stop clear`. Do not edit by hand. |
| `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/chunks/` | The JS chunk cache of the `recon/scan_bundles.py` scanner (the path after `/_next/static/chunks/`). `0600` files, atomic write, only for a complete 200 with a non-empty body. Names with a hash are immutable, so such a chunk is not fetched again; an empty file is fetched again, and chunks without a hash in the name on every scan. It can be deleted with no side effects (the next scan fetches the chunks anew). |

On Windows the default is `%USERPROFILE%\.cache\deweloperuch-mcp`. Use Windows 10 (1903+) or Windows 11 with a local NTFS cache directory; these support immediate deletion while a status reader is open. `XDG_CACHE_HOME` may override it with an absolute Windows path; give every CLI, MCP and recon process the same value so they share the same lock and STOP record.

## Request limiter

All processes on one machine (the `recon/` scripts and the package client) go through the same lock, so together they keep to the polite-client policy: at most one request per second, one at a time ([decisions.md](decisions.md)).

| Parameter | Value | Description |
|---|---|---|
| Interval between requests | 1 s (minimum) | Counted from the end of the previous request. It may only be lengthened. |
| Concurrency | 1 request at a time | Across processes and threads. |
| Max wait (`max_wait`) | 60 s | A longer required pause ends with an error instead of sleeping. It does not cover waiting for the lock while another process's request is running (that is bounded by the request timeout). |
| Max pause from `Retry-After` | 3600 s | A longer value is recorded as 3600 s and reported as an error. |

Behavior from the user's point of view:

- A process killed during a request does not hold the lock forever. The next process will still wait the standard interval.
- After a wait error (`WaitTooLongError`, message „Następne zapytanie do deweloperuch.pl wolno wysłać dopiero za N s…”) wait the stated time and retry. As a last resort (a person) delete the `throttle.lock` file itself, but only when no process is using the service for certain and the `Retry-After` time has passed; do not clear a STOP record this way (use `stop clear`).
- A `Retry-After` longer than 1 h is clipped to 1 h and reported as an error, and the next request waits that hour.
- Supported systems: Linux, macOS and Windows. Windows locks byte zero of the same state file, without truncating it on acquisition; both implementations release the lock when its descriptor closes or the owning process dies. See the [Python locking documentation](https://docs.python.org/3/library/msvcrt.html#msvcrt.locking).

## STOP: shared lock between processes

After 401, 403, 429 or a Cloudflare challenge a process writes STOP to `stop.json` next to `throttle.lock`. While the record is active, no process (CLI, MCP server, `recon/probe.py`, `recon/scan_bundles.py`) sends requests: the CLI, probe and the scanner end with exit code 3, and the MCP server returns `isError` with `STOP:`. The package writes STOP right after the response headers, recon after reading the body (a known limitation: an interruption while reading the body of a 401/403/429 will not leave a record).

| Property | Value |
|---|---|
| Location | `${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/stop.json` |
| Format | JSON, `"format": 1`: `{"format": 1, "since": ISO-UTC, "status": 401\|403\|429\|"challenge", "reason": text, "until": ISO-UTC\|null, "source": "pakiet"\|"probe"\|"scan_bundles", "pid": number}` |
| Contents | Only the status and the canonical reason text (`reason`); no target, URL, headers or response content. |
| Permissions, write | `0600` on POSIX, inherited directory ACLs on Windows; atomic write (temporary file `.stop-*.tmp`, `fsync`, then `os.replace` on POSIX or `FileRenameInfoEx` with POSIX rename semantics on Windows), only under the `throttle.lock` lock. Windows readers share delete access so an open status reader can keep reading the old record while new readers receive the replacement. Directory syncing is best effort where the OS supports it. |
| Read | `slot()` reads the record under the lock, before counting time: with an active record nothing is sent, and the limiter's timing state stays untouched. `stop status` reads without the lock. |

Validity rules:

- **429** expires: `until` is the write time plus the limiter pause (`max(Retry-After, 60 s)`, at most 3600 s). A 429 without a known pause is indefinite.
- **401, 403, challenge** do not expire (`until` is `null`; `until` in such a record is ignored). A challenge always has `status` `"challenge"`, also with a 429 or 403 status.
- **The first active record wins**; a later STOP can only extend the end or make the record indefinite. An expired record is replaced by a new one.
- **An unreadable record is an indefinite STOP** (fail-closed): bad JSON, a missing key, `format` and `pid` other than an integer, a time without a time zone, `status` outside 401/403/429/`challenge`, `reason` inconsistent with the status, `source` outside `pakiet`/`probe`/`scan_bundles`, a file over 64 KiB, a symlink, FIFO, directory, a read error. The content of such a file does not reach any message (`stop status` gives only a short description of the problem).
- The pause after a 429 is also in the timing state of `throttle.lock`. Clearing the record does not shorten it; after `stop clear`, code 5 (`LimiterWaitError`) may therefore still mean the rest of the pause for a while.

Clearing: only by the user, `deweloperuch stop clear` ([description](cli/commands/stop-clear.md)), after checking the cause (`deweloperuch stop status`, [description](cli/commands/stop-status.md)). The command waits for the lock at most 300 s, also removes orphaned `.stop-*.tmp` files and does not clear the lock when it cannot get the lock. An MCP server that returned STOP once (its own or from another process's record, also an expiring 429) stays latched until restart.

### Lifting a STOP without a checkout

Users of the Claude Desktop extension (`.mcpb`) have no `deweloperuch` command installed. After checking the cause (`stop status` first), they lift a STOP by running the `stop clear` command through uvx:

```
uvx --from deweloperuch-mcp deweloperuch stop clear
```

Then restart the MCP server, which stays latched after a STOP.

**Do not delete the `~/.cache/deweloperuch-mcp` directory or the files in it.** Deleting the directory clears STOP together with the 429 pause and the lock, that is, it bypasses the block without checking the cause. Use `stop clear` instead.

## Package client

The client (`deweloperuch_mcp.api.http.transport`) is synchronous (`httpx`), with the User-Agent from `identity`: `deweloperuch-mcp/<version> (+https://github.com/MBratkowski/deweloperuch-mcp)` (the version of the installed package, `0+unknown` when it cannot be read). The client states plainly what it is; the authors of the service agreed to the project's use of it (2026-10-14), and it stays frugal all the same. Every request, including reading the body, fits in one slot of the shared limiter.

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
| Cache | in process memory | Not written to disk. Freshness is `s-maxage`, without it `max-age`, without both 300 s. TTL = freshness minus `Age`, at most 300 s. When `Age` is at or above the freshness (Cloudflare serves its copy past `max-age`, e.g. the GUS page `polska` with `age: 69574` at `max-age=28800`, verified 2026-10-13) the reply is cached for 300 s (a repeat within 5 minutes would get the same Cloudflare copy anyway). Never cached: `no-store` and `no-cache` (any letter case, also with a value), an explicit freshness of 0 (`max-age=0`, `s-maxage=0`, treated like `no-cache`) and errors (also „no such page”). `private` and `must-revalidate` do not change the TTL. The computed TTL is logged at DEBUG (`TTL cache …`, only `Cache-Control` and `Age`); no entry point enables DEBUG by default. LRU: 256 entries and 64 MiB. |
| Closed session | `SessionClosedError` | Use after leaving a `Session`. |

The request target is checked before sending against the allowlist (`allowlist.py`) and the no-bulk-dump rule: paths from `DUMP_PATHS` (`/api/map/powiat-sales/{id}`, the page `/statystyki/ceny-transakcyjne/{mieszkania|domy}/{city}` without `/mapa`) are never called. `valuation-pdf` and server actions are excluded. A violation is an `InvalidInputError` with the prefix „Błąd programu”.

## Package errors

All intended errors inherit from `DeweloperuchError(message, detail=)` (`deweloperuch_mcp.errors`) and are shared by the client, services, CLI and MCP.

| Element | Behavior |
|---|---|
| `str(err)` | A domain-level message in Polish: what happened and what to do. It never contains service paths, prop names or response content. It is the only text that reaches the model (MCP) and follows `Błąd:` on stderr (CLI). |
| `err.detail` | Technical details: the request target, HTTP status, a fragment of the response body; `None` when there are none. Goes to the MCP server log (stderr) and to the `Szczegóły:` line in the CLI. |
| Escaping | `detail` always passes through `errors.printable`: every non-printable character (OSC/CSI control sequences, line endings, bidi controls) becomes `\xNN`, `\uNNNN` or `\UNNNNNNNN`. Polish letters stay. |
| Domain context | Services prepend a prefix, e.g. `Inwestycja 'smolna': …`, `Wyszukiwanie ofert w 'warszawa': …`; `NotFoundError` has a domain message (e.g. „Nie znaleziono inwestycji 'smolna'. …”). The error type, `pause_seconds` and `detail` are preserved. |
| Data not matching the contract | `UnexpectedResponseError` with the suffix „Serwis mógł się zmienić po aktualizacji: ponawianie nie pomoże, zgłoś to użytkownikowi.” |
| Internal labels | Only in `detail`, never in `str(err)`. |

Mapping to CLI exit codes: [docs/cli/README.md](cli/README.md#exit-codes). Mapping to the MCP result: [docs/mcp/README.md](mcp/README.md#errors).

## For developers

`DEWELOPERUCH_UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/consumers/mcp/test_server.py` refreshes the snapshot `tests/snapshots/mcp_tools.json` (the full `tools/list`, `instructions`, `serverInfo.name`). It is a test tool, not product configuration; a regular `uv run pytest` compares the result with the snapshot. `DEWELOPERUCH_UPDATE_GOLDEN=1 uv run pytest tests/characterization` rewrites the golden outputs of `tests/golden/` ([tests/golden/README.md](../tests/golden/README.md)); review `git diff --stat tests/golden` afterwards.

`DEWELOPERUCH_LIVE=1` (with the pytest marker `live`) enables the live e2e tests from `tests/e2e/`: `DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e -rs --maxfail=3`. Without it the e2e tests are skipped. It is a switch for tests only, not product configuration; the server and CLI do not read it. Use it sparingly: a run is a series of live requests; more: [tests/e2e/README.md](../tests/e2e/README.md). `make test` runs the offline suite with `DEWELOPERUCH_LIVE` unset (`env -u DEWELOPERUCH_LIVE`), so `tests/e2e` stays skipped whatever the shell has set.

## Development scripts (`recon/`)

The `recon/` scripts are maintainer tools for checking the service (they are not part of the installed package). They run as `python3 recon/<script>.py` require Python 3.11 or newer. The system `python3` on macOS is 3.9 and ends with a message about the required version. Alternative: `uv run python recon/<script>.py`.

`BASE_URL` and `USER_AGENT` are defined in one place: `src/deweloperuch_mcp/identity.py`. `recon/config.py` re-exports them and gives them to the scripts together with the same limiter as the package.

`recon/flight.py` and `recon/allowlist.py` re-export the implementations from the package (`deweloperuch_mcp.flight`, `deweloperuch_mcp.allowlist`). `recon/flight.py` run as a CLI also requires Python 3.11+ (it used to work on 3.9).

### `recon/probe.py`

A single GET request per run (no redirects or retries), in a slot of the same `throttle.lock` lock and with the same User-Agent as everything else. Allowed targets: only paths from the allowlist, never full URLs. `api PATH` makes a `GET /api/*`; `page PATH [--prop NAME]` reads a page as RSC (without `--prop` it lists the props with data). Other options: `--save NAME[.VARIANT]` (writes a trimmed sample to `docs/discovery/samples/`, never overwrites; arrays cut to `--trim` elements, default 3; personal data replaced with `"[usunięte]"`), `--max-wait SECONDS`, `--full`. Exit codes: 0 success; 2 usage or allowlist error (nothing sent); 3 STOP (also an earlier STOP written by another process: nothing is sent); 4 other HTTP or network error, response too large, truncated or read for too long; 5 the limiter requires waiting longer than `--max-wait`; 6 a 2xx response without the expected data. More: `python3 recon/probe.py --help`.

| Parameter | Value | Description |
|---|---|---|
| `--max-wait` | 60 s (default) | A finite number of seconds. A longer required pause ends with code 5, without sending a request. |
| Pause after 429 | at least 60 s | `max(Retry-After, 60)`. |
| Pause after 502/503/504 | `Retry-After` or 30 s | A `Retry-After` > 3600 s is clipped to 3600 s. |
| Response limit | 32 MiB | A larger response ends with code 4 (recon is not meant for bulk dumps). |
| Response read limit | about 120 s | Worst case about 120 s + 2 × 30 s. A response shorter than `Content-Length` is code 4, with no sample written. |
| `--save` | `docs/discovery/samples/` | The only write directory; an existing file is not overwritten. |

After a STOP in a response, probe writes `stop.json` (source `probe`) and prints `Zapisano STOP: inne procesy też zostały wstrzymane.` to stderr. When a record is already active (from any process), it ends with code 3 without a request; usage errors (code 2) are checked earlier. The STOP line for a challenge on a status other than 401/403/429 reads `STOP: challenge Cloudflare (captcha/WAF)`, without „HTTP 200”.

Probe reads no environment variables of its own. The `Retry-After` parser (seconds or an HTTP date) is shared with the package.

### `recon/scan_bundles.py`

The JS bundle scanner (detects changes of the service after a deploy). All requests go through the same `throttle.lock` lock and with the same User-Agent. It fetches only the pages from its `PAGES` list and `GET /_next/static/chunks/*.js`: each page once per scan, a chunk only when the cache does not hold it (see the "Files" table). The first scan with an empty cache was about 140 requests (22 pages and 118 chunks) before the redesign of the service on 2026-10-29; the new build has more chunks ([T62](open-questions.md)), so run it rarely. `--json` prints `build_id`, `pages` (the number of entries of `PAGES`, whatever the service answered), `chunks`, `chunks_fetched`, `chunks_cached`, `api`, `actions`, `incomplete`, `redirects`, `missing` and, with `--compare`, `drift`. `--compare FILE` compares `/api` paths and action names with a baseline; `--baseline-out FILE` writes one (refused for an incomplete result). `--save-pages DIR` keeps the HTML of the pages for offline analysis. Pages that moved or are gone, `--save-pages` and the exit codes are described below. More: `python3 recon/scan_bundles.py --help`.

| Parameter | Value | Description |
|---|---|---|
| `max_wait` | 60 s (fixed) | No flag. A longer required pause ends the scan with code 5, before sending a request. |
| Pauses, response limits | as in probe | Pause after 429 at least 60 s, after 502/503/504 `Retry-After` or 30 s; response limit 32 MiB and read time as above. |
| Redirects, retries | none | A redirect is never followed and nothing is retried. A page of `PAGES` that answers a redirect within the site, 404 or 410 is recorded and skipped; any other failure ends the scan (a STOP with code 3, the rest with code 4). |
| `PAGES` | 24 pages | The fixed list of pages the scanner requests, each once per scan and before any chunk. A page that moved or is gone does not end the scan (see "Moved and missing pages"). |
| `MAX_CHUNKS` | 400 | Hard limit of chunk requests per scan (also when cache files are unreadable); exceeding it is code 6. |
| Cache | `chunks/` | See the "Files" table. The scanner respects `XDG_CACHE_HOME`. |
| STOP | `stop.json` | As in probe: after STOP a record with source `scan_bundles`; with an active record (from any process) the scan ends with code 3 before a request. |

#### Moved and missing pages

A page of `PAGES` can move or disappear when the service is redesigned. The scanner never follows a redirect; a page that answers with one of these is recorded and skipped, and the scan goes on:

- a redirect (3xx) within the site: a `Location` that is a path or a full address on the service's own host, or no `Location` at all;
- 404 or 410 with a complete body.

Nothing else is requested for such a page, so the chunks only it names are missed and the result is incomplete (see "Exit codes"). The skipped pages are reported so that `PAGES` in `recon/scan_bundles.py` can be fixed:

- stderr, for a redirect: `Uwaga (niepełny wynik): GET <page>: HTTP <status>: przekierowanie na <target>. Skaner nie podąża za przekierowaniami: chunki tej strony pominięte. Jeśli strona się przeniosła, zaktualizuj PAGES w recon/scan_bundles.py.` (`<target>` is `?` without a `Location`); for 404 or 410: `Uwaga (niepełny wynik): GET <page>: HTTP <status>: strony nie ma, chunki tej strony pominięte. Popraw albo usuń ten wpis PAGES w recon/scan_bundles.py.` The text after `Uwaga (niepełny wynik): ` is also an entry of `incomplete`;
- `--json`: `redirects` maps a redirected page to its `Location`, or to `null` when the answer had none; `missing` maps a page that answered 404 or 410 to that status (an integer). Both are `{}` when no page was skipped, and both keep the order of `PAGES`;
- text output: a section `## strony pominięte (zaktualizuj PAGES)` with one line per page, `<page>: przekierowanie na <target>` or `<page>: HTTP <status>`, redirected pages first.

A `Location` is made safe to print before it reaches stdout, stderr or the JSON: every non-printable character (ESC, CSI, line breaks, bidi controls) is escaped as Python's `repr` does (`\x1b`, `\n`, `\u202e`), and the text is cut to 300 characters, counted after escaping, with „…” appended. `printable` in `recon/http_common.py` does this; `recon/probe.py` uses it for the `Location` in its redirect message too.

A redirect of a page to another host (also a subdomain, or an address that cannot be read) still ends the scan with code 4: a page cannot leave the site, and an access gate must end the scan at its first page. So does a redirect, 404 or 410 of a chunk (chunk addresses come from the pages, so there is no `PAGES` entry to fix), and a redirect, 404 or 410 whose body is truncated. A STOP wins over everything else, also when it comes as a challenge on a 3xx or 404 answer (code 3).

#### `--save-pages DIR`

Keeps the HTML of every page of `PAGES` that answered 2xx, byte for byte, in `DIR/<name>.html`, at no extra request. The name is the path without its first „/”, with „/” replaced by `__` and every character outside `[A-Za-z0-9._-]` replaced by `_`; the start page is `index.html` (`/a/b` is `a__b.html`). A skipped page has no file.

It is for offline analysis only (the props of a page sit in its inline `self.__next_f` flight data), never for samples or fixtures: a page may hold personal data. Hence the rules:

- `DIR` must be new or an empty directory and must lie outside the repository. The location is compared with the repository by file identity, so a symlink, another letter case on a case-insensitive file system or a second mount of the repository does not get around it. Otherwise the scan ends with code 2 before the first request.
- New directories (missing parents too) are created with mode `0700` and files with `0600`; these are POSIX modes and are not verified on Windows. A file is created exclusively, so nothing is overwritten.
- A page that cannot be written is only a line `Info: nie zapisano strony <page> do <file> (<error>).` on stderr; the scan, its result and its exit code are not affected.
- `DIR` is created before the first request. A scan that ends early leaves it with the pages saved so far, so a rerun needs a new or emptied directory.

#### Exit codes

A result is incomplete when it may miss `/api` paths or actions: a page was skipped (above), a chunk was skipped (outside the allowlist, empty or not a 200), the webpack runtime is missing or unreadable, or the pages named different build IDs. It is still printed, with its reasons: the `incomplete` field, the `Uwaga (niepełny wynik): …` lines on stderr and a header in the text output. Without `--compare` and `--baseline-out` it does not change the exit code.

| Code | Meaning |
|---|---|
| 0 | Success. With `--compare`: no differences from the baseline. Also an incomplete result when neither `--compare` nor `--baseline-out` is given. |
| 2 | Usage error. Before the first request: a bad option; `--compare` without a file or with a file in a wrong format; `--baseline-out` naming a directory or a missing directory; `--save-pages` naming a file, a non-empty directory, a directory in the repository or one that cannot be created. After the scan: the `--baseline-out` file could not be written. Also a request outside the scanner's allowlist (it is not sent). |
| 3 | STOP: 401, 403, 429 or a Cloudflare challenge (also one served with a 3xx or 404 status) on a page or a chunk, or an earlier STOP record (then before the request). The scan ends; do not retry, report it. |
| 4 | Another HTTP or network error: a redirect of a page to another host; a redirect, 404 or 410 of a chunk; other 4xx; 5xx; a timeout or no connection; a response that is too large or read for too long; a truncated body. The scan ends. A page that redirects within the site or answers 404 or 410 does not end it. |
| 5 | The limiter requires waiting longer than 60 s; the scan ends before that request. |
| 6 | The scan ends without a result when no page names a chunk (also when every page of `PAGES` was skipped, with the message „Każda strona z PAGES odpowiedziała przekierowaniem albo kodem 404 lub 410 (szczegóły wyżej): zaktualizuj PAGES w recon/scan_bundles.py. Skan przerwany przed pobraniem chunków.”), when a chunk is served as HTML, or when more than `MAX_CHUNKS` chunk requests would be needed. Also an incomplete result with `--compare` (takes precedence over 0 and 7) or with `--baseline-out` (the baseline is not written): the result and the reasons are printed. |
| 7 | `--compare`: differences from a complete result (printed; `--baseline-out` written). |

_Source: `src/deweloperuch_mcp/throttle.py`, `src/deweloperuch_mcp/identity.py`, `src/deweloperuch_mcp/retry_after.py`, `src/deweloperuch_mcp/http_policy.py`, `recon/config.py`, `recon/http_common.py`, `recon/probe.py`, `recon/scan_bundles.py`, `recon/allowlist.py`, `recon/flight.py`, `src/deweloperuch_mcp/api/http/transport.py`, `src/deweloperuch_mcp/usecases/`, `src/deweloperuch_mcp/consumers/`, `src/deweloperuch_mcp/allowlist.py`, `src/deweloperuch_mcp/flight.py`, `src/deweloperuch_mcp/errors.py`_
