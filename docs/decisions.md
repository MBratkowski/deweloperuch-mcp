# Architecture decisions

Short architecture decision records (ADRs), newest last. Status: **accepted**, **proposed** or **open**. Certainty tags such as `[P]` and `[W]` are explained in [discovery/README.md](discovery/README.md).

---

## D1. Channel order: JSON API → RSC → server actions (accepted)

**Context.** The data is available through four channels of different stability ([discovery/README.md](discovery/README.md#2-data-access-channels)).
**Decision.** For each capability we use the JSON `/api/*` channel if it provides the data. RSC pages only where no JSON exists (search with filters and pagination, developer profile, reports, GUS/NBP). Server actions only when there is no alternative (today: no capability uses them).
**Consequences.** The client has two transport adapters, JSON and RSC. The RSC adapter is isolated and covered by contract tests on recorded responses, because prop names may change without notice.

## D2. A frugal, predictable HTTP client (accepted; identification open, see U1/T11)

**Context.** `robots.txt`: `Disallow: /api/`, `Crawl-delay: 1`. The service is a community project behind Cloudflare. No authentication.
**Decision.**
- A global limiter shared by all processes: at most 1 request per second and 1 request at a time (configurable downwards only).
- An in-process response cache:
  - TTL = the response's freshness minus `Age`, at most 300 s; freshness is `s-maxage`, otherwise `max-age`, otherwise 300 s;
  - a response whose `Age` is at or above its freshness (Cloudflare serving it beyond `max-age`, e.g. the GUS page `polska`: `age: 69574` at `max-age=28800` [P 2026-10-13]) is cached for 300 s, because a repeat would get the same Cloudflare copy anyway;
  - `no-store`, `no-cache`, an explicit freshness of 0 and errors are never cached; `private` and `must-revalidate` do not change the TTL, because the cache is private to the process;
  - local data is therefore never older than 5 minutes, and repeats within that window do not reach the service.
- No bulk crawling features (e.g. "download all transactions in Poland").
- Timeouts and readable errors for 4xx/429/5xx; `Retry-After` is honoured.
- Identification (User-Agent): a single constant; an honest client identifier is the goal (U1).

**A persistent STOP shared by all processes.**
- After a 401, 403, 429 or a Cloudflare challenge, the process records a STOP in `stop.json` next to the limiter lock (`${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/`). While the record is active, no process (CLI, MCP server, `recon/probe.py`, `recon/scan_bundles.py`) sends requests.
- A STOP after a 429 expires after the pause; 401, 403 and challenges last until a person lifts them with `deweloperuch stop clear`, after checking the cause. An unreadable record means an indefinite STOP (fail-closed). There is no MCP tool for lifting it.
- A process that returned a STOP stays latched until restart, also the MCP server.
- Details: [configuration.md](configuration.md#stop-shared-lock-between-processes).

## D3. Domain naming independent of the backend (accepted)

**Context.** The backend calls an RCN building "invest" and a unit "sale", and its fields have inconsistent types ([entities.md](discovery/entities.md)).
**Decision.** The models use domain names (`Developer`, `Investment`, `Offer`, `PriceEvent`, `Building`, `Unit`, `Transaction`, `Location`, `Valuation`, time series). DTOs mirror the backend 1:1 (with type tolerance), and the DTO → model mapping normalises numbers, dates and empty strings.

## D4. The search limit is explicit in the contract (accepted)

**Context.** RSC lists return at most 20 pages × 100 = 2,000 records, while `total` reaches e.g. 351,314.
**Decision.** Search results contain `total`, `returned`, `truncated` and a hint to narrow the filters. Aggregates are shown instead of requesting full data.

## D5. Heavy dumps never reach MCP (accepted)

`map/powiat-sales` (up to ~80 MB), `rawTransactions` (12.9 MB of HTML) and the full valuation `radiusPool` (180 KB) are not exposed. Using a dump internally needs its own decision (see D15).

## D6. One shared core with thin adapters (accepted; structure superseded by D13 and D16)

The CLI and the MCP server call the same core; neither talks to the service directly. Raw service data for debugging comes from `recon/probe.py`, not from the CLI. The current structure is described in D16 and D17.

## D7. Detecting service drift (proposed)

`recon/scan_bundles.py` lists the `/api/*` paths and server actions in the service's current JavaScript bundles. Contract tests on recorded responses plus occasional manual scanner runs show changes after the service deploys. No automatic crawling in CI.

## D8. Technology stack: Python (accepted 2026-10-09)

Python with the official MCP SDK (`mcp>=2.3`, `MCPServer`), pydantic, httpx and typer; pytest with pytest-socket and respx, ruff, mypy, uv. `mcp` 2.x also pulls in `httpx2`; the client uses `httpx` explicitly, because respx mocks only `httpx`.

Rationale: the domain is mostly normalisation and aggregation of inconsistent backend data, pydantic handles that well at the edges, the recon tools were already in Python, and distribution via `uvx` is simple. TypeScript (official SDK, zod, commander, `npx`) would have been a reasonable alternative.

## D9. Live requests are rare and deliberate (accepted 2026-10-09)

**Context.** The service's policy towards automated access to `/api/` (U1) is not settled yet; the maintainer is contacting its authors.
**Decision.** Development never crawls the service. Checking a hypothesis or scanning bundles is a short, deliberate series of requests through the shared limiter, run by a person on purpose. The User-Agent is one constant in `src/deweloperuch_mcp/identity.py` (re-exported by `recon/config.py`); a test enforces a single definition.

## D10. Safeguards in development (accepted 2026-10-09)

- Offline tests block the network with `pytest-socket`. MCP server tests allow only AF_UNIX sockets (needed by the asyncio loop); tests that start subprocesses install the same guard in them.
- Offline tests use real service responses (samples in `docs/discovery/samples/`, raw payloads in `tests/fixtures/`), not payloads built from assumptions, unless a test checks a shape itself.
- The optional live suite `tests/e2e/` talks to the service only through subprocesses (the MCP server over stdio, the CLI and `probe`), runs only with `DEWELOPERUCH_LIVE=1` and `-m live`, has a hard request budget, uses the shared limiter and STOP record, and stops on the first STOP. A default `uv run pytest` never touches the network.
- The repository also contains Claude Code hooks (`.claude/`) used during development as a safety net: they block service URLs in shell commands, lifting a STOP, and edits outside an agent's files, and they run ruff and mypy after every Python edit.

## D11. The MCP and CLI interface (accepted 2026-10-10)

**Context.** Result size for the model is the main MCP constraint.
**Decision.**
- **MCP transport:** stdio only. Tools carry `readOnlyHint` and `openWorldHint`. Errors come back as an `isError` result with a Polish message. Unknown arguments are rejected with a message that lists the allowed ones.
- **MCP representation:** separate from the models; items are compact and `null` fields are omitted, except `total` (D4), which is always present. Page sizes and limits are bounded per tool and documented in each tool's schema.
- **CLI:** `--json` gives the full result; text output is for people. Exit codes: 0 OK, 1 other error, 2 invalid input, 3 STOP, 4 service error, 5 limiter, 6 unexpected response, 7 not found.
- **MCP input:** integers are also accepted as text made of digits only; `true`/`false` in numeric fields are rejected; `""` and `null` mean "not given" or the default; choices are trimmed.
- **Parameters:** only parameters confirmed against the service (`[P]`) are exposed; others only with an explicit note and a live test.

**Consequences.** Changing a schema or a limit changes the snapshot `tests/snapshots/mcp_tools.json`.

## D12. Error messages and links (accepted 2026-10-10)

**Context.** Paths, prop names and response text from the service in a message for the model are a prompt-injection channel and noise; terminal sequences in response text are a risk for the CLI.
**Decision.**
- The error message is in domain terms (what happened and what to do). It contains no paths, props, response text or sizes.
- Technical details go to `err.detail`, always escaped. MCP writes them only to the log on stderr; the CLI shows them on a `Szczegóły:` line.
- STOP messages only say what stopped the series and that the model should stop and report to the user; no times, sources or ways of lifting the block.

**Links to public pages (2026-10-11).**
- Results may contain addresses of the service's public pages for people, only in dedicated `*_url` fields (`list_url`, `investment_url`, `developer_url`, `building_url`, `stats_url`, `ranking_url`).
- Addresses are built only from confirmed page patterns (`docs/discovery/pages-rsc.md`), never with `_rsc` or `/api/*`. A page whose pattern is not confirmed is not linked (e.g. a single offer).
- The offer-list link carries the page's public parameters (e.g. `filterPrice`), a deliberate exception to D3: they are part of an address a person opens.
- Error messages never contain addresses.

## D13. Ports and adapters (accepted 2026-10-12; package names superseded by D16)

**Context.** The first version mixed responsibilities: data-only models with logic in helper functions, one service function that validated input, built backend parameters, worded messages, called the client and built links, primitive strings instead of value objects, and adapters that mixed validation, formatting and descriptions.
**Decision.**
- Plain-Python models (frozen dataclasses, enums) with behaviour: value objects validate in constructors; entities and aggregates (an offer with its price history, an investment, a developer, a location, a time series) carry their rules, including the truncation rule of D4.
- Use cases, one per operation, depend on ports (`typing.Protocol`); adapters for the service implement the ports; the CLI and MCP depend only on use cases and models; one composition root (`bootstrap.py`) wires everything.
- The dependency direction is enforced by tests; models and use cases may import only an allowlist of pure stdlib modules.
- The parameter names shared by the CLI and MCP, their check order and the refusal messages are the use cases' contract; value objects raise structured errors in neutral domain words.
- New features start in the models (e.g. price-history flags are methods of the price history; market statistics are an aggregate over a set of offers).

**Consequences.** Refactors do not change behaviour: the MCP snapshot, the CLI goldens and the live e2e suite are the acceptance tests.

## D14. Documentation language: English (accepted 2026-10-12)

Documentation is written in English. Product text (tool descriptions, messages, CLI output) is in Polish and is quoted verbatim. Certainty tags (`[P]`, `[P YYYY-MM-DD]`, `[P z kodu]`, `[W]`, `[H]`) stay unchanged.

## D15. `city-sales` as an internal source of offer-market statistics (accepted 2026-10-13)

**Context.** D5 keeps dumps away from MCP. `GET /api/offers/city-sales/{citySlug}` [P] lists every active offer of a city in compact form (Warsaw: 278 investments, 13,351 offers, about 1.3 MB). It is the only confirmed source of a whole city's price, area and price-per-m² values in one request; the histogram endpoints have unconfirmed bucket boundaries (T9).
**Decision.**
- `get_market_statistics` (MCP) and `stats market` (CLI) read `city-sales` for one city and compute aggregates in the models: counts of offers, investments and developers; minimum, quartiles, median and maximum of price, price per m² and area; the largest developers by number of offers.
- The dump stays inside the process; outputs carry only aggregates and a bounded list of developers.
- `city-sales` stays a documented read channel under the D2 client (limiter, cache, body limit).
- Known limits: active offers only (`includeArchived` is ignored) [P 2026-10-10]; `polska` gives `400 Invalid citySlug` [P 2026-10-10], so the whole country is refused before any request; counts may differ slightly from the offer list (Kraków 7,325 vs 7,307 [P 2026-10-13]).

## D16. Visible layers: api → models → usecases → consumers (accepted 2026-10-13)

**Context.** The D13 layers existed under names (`infrastructure`, `domain`, `application`, `interfaces`) that did not read as the usual split, and each capability was spread thinly over them.
**Decision.**
- `api/`: everything that talks to deweloperuch.pl — transport (limiter, cache, STOP), JSON and RSC reading, DTOs with mapping to models, backend query parameters, page links;
- `models/`: value objects, entities and aggregates (plain Python, no I/O, no backend names);
- `usecases/`: one use case per operation, the ports they depend on, the argument contract shared by the CLI and MCP;
- `consumers/mcp/` and `consumers/cli/`: tools and commands with their presenters; `consumers/shared/`: views shared by both;
- `bootstrap.py`: wiring of `api` into `usecases` for the consumers.
- Dependency direction: `consumers` → `usecases` → `models`; `api` → `usecases.ports` and `models`; `models` imports nothing from the package. Enforced by `tests/architecture/test_layering.py` and import-linter (`make fast`).
- Stdlib-only modules used by `recon/` (`identity`, `throttle`, `http_policy`, `retry_after`, `allowlist`, `flight`) keep their import paths.

## D17. One code pattern per layer (accepted 2026-10-13; migration completed 2026-10-14)

**Context.** Mixed shapes made the code hard to read: a use case class next to a loose helper function, a module of loose argument functions, adapter classes next to loose mapping functions, and the same file name (`developers.py`) in several layers.
**Decision.** Every layer has one shape, the same for every capability:
- **models/**: frozen dataclasses only; value objects validate in the constructor and offer `parse(raw)`; entities and aggregates carry behaviour as methods (e.g. `PriceHistory.price_flags(as_of)`). No public module-level functions.
- **usecases/**: one class per operation, named verb + noun (`SearchOffers`, `GetDeveloper`); ports come through `__init__`; the only public method is `execute(request) -> result`. The request is a frozen dataclass with a `parse(**raw)` classmethod (the argument contract shared by the CLI and MCP); the result is a frozen dataclass; hints and messages are methods of the result or private methods. Ports live in `usecases/ports.py`.
- **api/**: one adapter class per service resource (`OffersApi`, `DeveloperProfileApi`) implementing ports; DTOs are pydantic models with `to_model()`; backend parameters come from a query class (`OffersQuery(criteria).params()`); RSC pages are read by one class (`RscPage`).
- **consumers/mcp/**: one class per tool (`SearchOffersTool`) with name, description, schema and annotations, whose `__call__` parses the request, executes the use case and hands the result to the tool's presenter.
- **consumers/cli/**: Typer command functions (the framework's shape) that only parse, execute and render with the command's presenter.
- **Names:** `*Api`, `*Dto`, `*Query`, `*Request`, `*Result`, `*Tool`, `*McpPresenter`, `*CliPresenter`, `*View`; ports are named after their role (`OfferCatalog`, `Clock`).
- **File names say what is inside:** a module is named after its main class, never after the capability alone, so no file name repeats across layers (`models/developer_profile.py`, `usecases/get_developer.py`, `api/adapters/developer_profile_api.py`, `consumers/mcp/tools/get_developer_tool.py`). Shared plumbing keeps descriptive names (`api/http/transport.py`, `usecases/ports.py`).
- **Role folders and support folders are separate:**
  - `consumers/mcp/`: `server.py`, `tools/`, `prompts/` (MCP prompts, `*Prompt` classes, since 0.1.1), `presenters/`, `support/`;
  - `consumers/cli/`: `app.py`, `commands/`, `presenters/`, `support/`;
  - `api/`: `adapters/`, `dto/`, `queries/`, `http/`, `links.py`;
  - `usecases/`: one module per operation, `ports.py`, `support/`;
  - `models/`: one module per concept.
  Support folders hold capability-agnostic code; the one explicit exception is `usecases/support/investment_lookup.py` (`InvestmentLookup`), shared by `GetOffer` and `GetInvestment`.
- **Enforcement:** `tests/architecture/test_conventions.py` (AST: shapes, names, folders, no exceptions) and the D17 folder contracts of import-linter.

## D18. Public release (accepted 2026-10-13)

- **Licence:** MIT for the code. Data in samples and fixtures is not covered by it; `NOTICE` names its sources (deweloperuch.pl, and through it RCN, GUS and NBP).
- **U1:** the maintainer is contacting the authors of deweloperuch.pl about automated access to `/api/` and the preferred client identification. The User-Agent becomes an honest project identifier as part of resolving U1.
- **Repository content before publication:** internal working material (development handoffs, agent memory, prompts) is removed from the published tree; samples are reviewed for personal data (RCN unit identifiers get pseudonymised) and for content outside the project's scope.

---

## History

The first vertical slice (2026-10-10) covered `search_locations`, `search_offers` (the RSC channel, the main technical risk) and `get_offer` with `get_investment`. The live e2e suite replaced a manual smoke test; its first run found and fixed RSC parsing and the cache TTL. Later iterations added developers and investments, market statistics, RCN transactions, buildings, valuation, rankings and GUS/NBP statistics (13 MCP tools as of 2026-10-14).
