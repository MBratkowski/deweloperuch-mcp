# Architecture decisions

Format: short ADRs. Status: **accepted** (follows directly from discovery), **proposed** (awaiting acceptance), **open**.

---

## D1. Channel order: JSON API → RSC → server actions (accepted)

**Context.** The data is available through four channels of different stability ([discovery/README.md](discovery/README.md#2-data-access-channels)).
**Decision.** For each capability we use the JSON `/api/*` channel if it provides the data. RSC only where no JSON exists (search with filters and pagination, developer profile, reports, GUS/NBP). Server actions only when there is no alternative (today: no v1 capability).
**Consequences.** The client has two transport adapters: `json` and `rsc`. The RSC adapter is isolated and covered by contract tests on recorded samples, because prop names may change without notice.

## D2. A frugal, predictable HTTP client (accepted, details open, see U1/T11)

**Context.** `robots.txt`: `Disallow: /api/`, `Crawl-delay: 1`. The service is a community project behind Cloudflare. No auth.
**Decision.**
- Global limiter: by default ≤1 request/s and 1 request at a time (configurable downwards, not upwards without a deliberate decision).
- In-process response cache. **Clarification (2026-10-10, the user's instruction "popraw" (fix it) after the e2e run):**
  - TTL = the response's freshness minus `Age`, at most 300 s; freshness is `s-maxage`, otherwise `max-age`, otherwise 300 s.
  - TTL ≤ 0 means no caching; errors are never cached.
  - A response with a `no-store` or `no-cache` directive in `Cache-Control` (any letter case, also with a value) is not cached. `private` and `must-revalidate` do not change the TTL, because the cache is private to the process.
  - Local data is therefore never older than 5 minutes, and repeats within that window do not reach the service.
  - The original rule "TTL ≈ `s-maxage`" gave TTL ≤ 0 for pages and `/api/*` with `max-age=28800` whenever Cloudflare reported a large `Age`, so every repeat went to the network (found by the e2e suite).
- No bulk crawling features (e.g. "download all transactions in Poland").
- Timeouts and readable errors for 4xx/429/5xx; `Retry-After` is honoured.
- User-Agent: to be decided (U1/T11). An honest client identifier is preferred, as long as it is not blocked.

**Clarification (2026-10-10, user decision): a persistent STOP across processes.**
- After a 401, 403, 429 or a Cloudflare challenge, the process records a STOP in `stop.json` next to the limiter lock (`${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/`). While the record is active, no process (CLI, MCP server, `recon/probe.py`, `recon/scan_bundles.py`) sends requests.
- A STOP after a 429 expires after the pause; 401, 403 and challenges last until lifted. An unreadable record means an indefinite STOP (fail-closed).
- Only the user lifts it, with `deweloperuch stop clear`, without an extra confirmation in the terminal. Agents are blocked by the Bash hook and the rule in `CLAUDE.md`; there is no MCP tool for lifting it.
- A process that returned a STOP stays latched until restart. This also applies to the MCP server, even after the record is lifted or a 429 expires.
- Details: [configuration.md](configuration.md#stop-shared-lock-between-processes), handoff `2026-10-10-0740-trwaly-stop-miedzy-procesami`.

## D3. Domain naming independent of the backend (accepted)

**Context.** The backend calls an RCN building "invest" and a unit "sale", and its fields have inconsistent types ([entities.md](discovery/entities.md)).
**Decision.** Domain model: `Developer`, `Investment`, `Offer`, `PriceEvent`, `Building`, `Unit`, `Transaction`, `Location`, `Valuation`, `TimeSeries`. DTOs mirror the backend 1:1 (with type tolerance), and the DTO→domain mapping normalizes numbers, dates and empty strings.

## D4. The search limit is explicit in the contract (accepted)

**Context.** RSC lists return at most 20 pages × 100 = 2000 records, while `total` reaches e.g. 351,314.
**Decision.** Search results contain `total`, `returned`, `truncated` and a hint to narrow the filters. Aggregates (e.g. `stats` of the transaction list) are shown instead of requesting the full data.

## D5. Heavy dumps never reach MCP (accepted)

`map/powiat-sales` (up to ~80 MB), `rawTransactions` (12.9 MB of HTML) and the full valuation `radiusPool` (180 KB) are not exposed directly. If they are ever needed, it will be as an internal source of a local index, under a separate decision.

## D6. A shared core with thin adapters (accepted, as the project assumed)

```
deweloperuch client (http + json adapter + rsc adapter + DTO)
        │
        ▼
domain / services  (capabilities from the capability matrix, domain model, DTO→domain mapping)
     │         │
     ▼         ▼
    CLI       MCP     (argument parsing / tool schemas, output formatting)
```
The CLI and MCP call the same service functions. The CLI also serves as a developer tool (`--json`, `--raw` for DTOs).

**Clarification (2026-10-10, user decision):**
- v1 has no `--raw`; raw data comes from `recon/probe.py`.
- `services.Session` is the only entry point.
- The CLI and MCP import from the package only `services`, `errors` and `domain.models`; MCP additionally its own representation `mcp_results`. `tests/test_layering.py` enforces this.

Superseded in structure by D13 (the spirit stays: one core, thin adapters).

## D7. Detecting service drift (proposed)

`recon/scan_bundles.py` lists the `/api/*` paths and server actions in the current bundles. Contract tests on `docs/discovery/samples/` plus periodic (manual) scanner runs show changes after the service deploys. No automatic crawl in CI.

## D8. Technology stack (accepted 2026-10-09: Python)

**User decision:** Python: FastMCP, pydantic, httpx, typer; pytest + pytest-socket + respx, ruff, mypy, uv. The table below stays as the rationale.

**Clarification (2026-10-09, user decision):**
- The MCP server is built on the official SDK `mcp>=2.3`. In the 2.x line FastMCP was renamed to `MCPServer` (`from mcp.server.mcpserver import MCPServer`), and `mcp.server.fastmcp` is only a shim with a migration error. Pinning `mcp<2` was rejected.
- `mcp` 2.x also pulls in the `httpx2` package. The project's client uses `httpx` explicitly, because respx mocks only `httpx`.

| | Python | TypeScript |
|---|---|---|
| MCP | official SDK with FastMCP (decorators, schema from type hints) | official `@modelcontextprotocol/sdk` (the most mature) |
| Models/validation | pydantic: tolerant DTOs, easy normalization | zod: schemas shared with tool input |
| CLI | typer/click | commander/yargs |
| Distribution | `uvx deweloperuch-mcp` | `npx deweloperuch-mcp` |
| Project fit | recon tools already in Python; data work and aggregates | MCP and Next.js ecosystem in JS; one language with the service (no practical gain) |

Recommendation: **Python**. The domain is mostly data normalization and aggregation, pydantic handles the backend's inconsistent types well, and FastMCP needs little boilerplate. TypeScript would be fully justified too if the team preferred JS.

## D9. Live requests until U1 is resolved (accepted 2026-10-09, temporary)

**Context.** The policy towards `robots.txt: Disallow: /api/` (U1) is open.
**User decision.** Until U1 is resolved, every series of live requests (hypothesis verification, drift scan) needs the user's explicit consent in the current conversation. The User-Agent is a single constant. Its value is chosen by the user when U1 is resolved; until then it keeps the scanner's current value, marked `TODO(U1)`.

**Clarification (2026-10-09, user decision):** the `USER_AGENT` constant lives in a module of the `deweloperuch_mcp` package (stdlib only), because the installed package cannot see the `recon/` directory. `recon/config.py` re-exports it. Done 2026-10-09: `BASE_URL` and `USER_AGENT` are defined in `src/deweloperuch_mcp/identity.py`. A test in `tests/test_identity.py` enforces a single User-Agent definition.

## D10. How strictly Claude Code enforces the rules (accepted 2026-10-09)

**User decision.**
- Hooks are a safety net against mistakes, not a security boundary:
  - per-agent file ownership for Edit/Write/NotebookEdit;
  - blocking service URLs in Bash;
  - a handoff reminder.
- Tests block the network with `pytest-socket`.
- Browser tools (`mcp__claude-in-chrome`) need confirmation on every use.
- No Claude Code sandbox.

Configuration: `.claude/settings.json`, `.claude/hooks/`, rules in `CLAUDE.md`.

**Clarification (2026-10-10, user decision):**
- MCP server tests allow AF_UNIX sockets (needed by the asyncio loop); AF_INET, AF_INET6 and DNS stay blocked.
- Tests that start subprocesses install a pytest-socket guard in them (`NO_NETWORK` in `tests/test_mcp_server.py`, the guard in `tests/throttle_worker.py`) and never call paths that could reach the services.
- The Bash hook also blocks agents from lifting a STOP (D2): `deweloperuch … stop clear` and changing or deleting the limiter's files.

**Clarification (2026-10-10, the user's instructions "pisz e2e testy" (write e2e tests) and "zrób jak najwięcej testów e2e" (make as many e2e tests as possible)): an exception for the e2e suite.**
- The optional `tests/e2e/` suite talks to the live service, but only through subprocesses: the MCP server over stdio, the CLI and `probe`. The test process itself keeps the network blocked (AF_UNIX only).
- It runs only with both switches at once: `DEWELOPERUCH_LIVE=1` and `-m live`. A default `uv run pytest` skips it and does not touch the network.
- A run is a series of live requests in the sense of D9: it needs the user's consent and must not run in parallel with recon-verifier or drift-checker.
- The request budget per run is hard and enforced by an assertion in the suite.
- The suite uses the shared limiter and STOP record (D2). A STOP ends the run without retries.
- Offline tests use real service responses: the samples in `docs/discovery/samples/` and the raw payloads in `tests/fixtures/`. Payloads are not built from assumptions, unless the test checks the shape itself.

## D11. The v1 MCP and CLI interface (accepted 2026-10-10, user decision)

**Context.** S1b produced the first public interface; result size for the model is the main MCP constraint.
**Decision.**
- **MCP transport: stdio only** (resolves U3).
  - Tools carry the `readOnlyHint` and `openWorldHint` annotations, without `idempotentHint`.
  - Errors come back as an `isError` result with a Polish message, not as a `ToolError`.
- **The MCP representation** (`mcp_results.py`) is separate from the domain model.
  - Items are compact and `null` fields are omitted, except `total` (D4), which is always present.
  - `search_offers.per_page` ∈ {10, 50}, default 10.
  - `get_investment.limit`: default 20, at most 200.
- **CLI:**
  - `--json` gives the full domain model, `offers search --per-page` accepts 10/50/100, and `investments get` shows all offers by default.
  - Exit codes: 0 OK, 1 other error, 2 invalid input, 3 STOP, 4 service error, 5 limiter, 6 unexpected response, 7 not found.
- **MCP input:**
  - integers are also accepted as text made of digits only; `true`/`false` in numeric fields are rejected;
  - `""` and `null` mean no value or the default value; `sort` is trimmed.
- **Parameters:** services and schemas expose only `[P]` parameters. Extensions come after verification (flow B).

**Consequences.** Larger pages (100) and full models are available in the CLI, not in MCP. Changing these limits changes the snapshot `tests/snapshots/mcp_tools.json`.

## D12. Error messages: no backend details for the model (accepted 2026-10-10, user decision)

**Context.** Paths, prop names and response text from the service in a message for the model are a prompt-injection channel and noise. Terminal sequences in response text are a risk for the CLI.
**Decision.**
- `str(err)` is in domain terms (what happened to the offer, investment or search, and what to do). It contains no paths, props, response text, sizes or decision labels.
- Technical details go to `err.detail`, always escaped (`errors.printable`). MCP writes them only to the log on stderr; the CLI shows them on a `Szczegóły:` line.
- STOP messages only say what stopped the series and tell the model to stop and report to the user. They give no times, source or way of lifting the block, and text from the STOP file never reaches the model.

**Clarification (2026-10-11, the user's instruction that the results table "powinny być linki" (should have links)): links to public pages.**
- Results may contain full addresses of the service's public pages for people, only in dedicated `url` fields (e.g. the investment page, the developer profile, the offer list with the same filters).
- Addresses are built by one function from the confirmed [P] page patterns in `docs/discovery/pages-rsc.md`. No `_rsc` parameter and no `/api/*` paths.
- Error messages still contain no addresses or paths.
- An address whose pattern is not [P] is not given (today: the page of a single offer).
- The offer list link contains the page's public parameters (e.g. `filterPrice`, `sortBy=amount`). This is a deliberate exception to D3: they are part of an address the user opens, not names of result fields.
- Link fields are named after what they point to: `list_url` (offer list), `investment_url`, `developer_url`.

## D13. Architecture: lightweight DDD with ports and adapters (accepted 2026-10-12, the user's instruction)

**Context.** v1 was built as technical layers with procedures ("transaction script"). The concrete problems:
- **An anemic domain:** `domain/models.py` is data only (pydantic); the logic sits in `normalize.py` and in helpers of `services.py`.
- **`services.search_offers` does everything at once:** it validates input, translates it into backend parameters (`filterPrice`, `sortBy`), words the messages, calls the infrastructure through the private `session._http` and builds the link.
- **Primitives instead of value objects:** a price range is the string `"0-99999999"`, and sorting is a tuple of backend names.
- **No ports and fat adapters:** services call the client directly, and `cli.py` and `mcp_server.py` mix validation, formatting and descriptions.

The next features (price-history flags, `market_stats`, GUS/NBP) are domain logic, so the current shape would only deepen.

**Decision.**
- **Packages and dependency direction** (enforced by an AST test, no exceptions):
  - `interfaces` → `application` → `domain`;
  - `infrastructure` → `domain` (implements the ports);
  - `bootstrap` (the composition root) wires the infrastructure into the use cases for the CLI and MCP.
- **`domain/`:** plain Python (`dataclass(frozen=True)`, `Enum`), no I/O, no pydantic, no backend names and no imports from the rest of the package. It contains:
  - value objects: an amount in PLN, an area, price and area ranges, slugs, page and page size, sorting; validation in constructors raises domain errors;
  - entities and aggregates: an offer with its price history, an investment, a developer, a location, a time series;
  - search criteria and a result with the truncation rule (D4) as domain behaviour;
  - ports (`typing.Protocol`) through which the domain and the application see the world.
- **`application/`:** use cases, one per operation (search locations, search offers, get an offer, get an investment, government statistics, STOP status and lifting). They orchestrate ports and do not know the backend.
- **`infrastructure/`:** deweloperuch.pl adapters implementing the ports:
  - transport, RSC and JSON, DTOs;
  - mapping criteria to backend parameters (this is where `filterPrice` and `sortBy` belong);
  - mapping DTOs to the domain;
  - page links (D12).
  - Stdlib-only modules used by `recon/` (`identity`, `throttle`, `http_policy`, `retry_after`, `allowlist`, `flight`) stay importable at their current paths.
- **`interfaces/mcp/` and `interfaces/cli/`:** tools and commands grouped by capability, plus presenters (MCP schemas and the compact representation; CLI text and JSON). They depend only on `application` (and domain types for input) and on `bootstrap`.
- **The refactor does not change behaviour:**
  - the snapshot `tests/snapshots/mcp_tools.json` stays identical;
  - CLI output (text and `--json`) and exit codes stay identical;
  - the live e2e suite is the acceptance test;
  - tests may be reorganized, not weakened.
- **New features start in the domain**, e.g. the flags are methods of the price history and `market_stats` is an aggregate over a set of offers.

**Consequences.** D6 still holds in spirit (one shared core, thin adapters), but the split above replaces its diagram. The layering tests (`tests/test_layering.py`) enforce the new dependency direction. The refactor goes in steps, each reviewed: the domain with ports and use cases; the interfaces; GUS/NBP in the new shape.

## D14. Documentation language: English (accepted 2026-10-12, user decision)

**Decision.** Documentation and handoffs are written in English. Quotes of product text (MCP tool descriptions, messages, CLI output), which is in Polish, stay verbatim; certainty tags (`[P]`, `[P YYYY-MM-DD]`, `[P z kodu]`, `[W]`, `[H]`) stay unchanged. Agent reports and the conversation with the user may stay in Polish. The rule is in `CLAUDE.md` and in the documentation-creator and handoff-updater definitions.

---

## Proposed first vertical slice

**Goal:** go through all layers and both transport channels (JSON and RSC) on the most important user path: *"find new-build apartments in X within budget Y, show the details and the price history"*.

| Capability | Channel | Why in the slice |
|---|---|---|
| `search_locations` | A | the model has to turn "Kraków, Podgórze" into a `city_slug` and a district |
| `search_offers` | **B (RSC)** | the hardest channel; validating it early removes the main architectural risk |
| `get_offer` (with price history) + `get_investment` | A | stable JSON; shows the DTO→domain mapping (string/number types, dates, events) |

Technical scope of the slice: an HTTP client with limiter and cache (D2), JSON and RSC adapters, DTOs + domain for Offer/Investment/Developer/PriceEvent/Location, 4 CLI commands, 4 MCP tools, contract tests on samples and one manual live smoke test.

**Status (2026-10-10):** the slice is done without a live smoke test (S1a `23cd5be`, S1b `a954994`). The smoke test waits for consent to a series of live requests (D9). **Update (2026-10-10/11):** the live e2e suite (`tests/e2e/`) replaced the manual smoke test; its first run found and led to fixes of `search_offers` (RSC parsing) and of the cache TTL.

Beyond the slice (next iterations): RCN transactions and buildings → valuation → statistics → GUS/NBP.
