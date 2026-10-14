# deweloperuch.pl: data layer map

Findings about how the service exposes its data, gathered for `deweloperuch-mcp`. Last full survey: **2026-10-09**, with additions through 2026-10-13. Next.js build `KD_IOP6Grqba7xa86pGVG`.

Method: static analysis of all client JS chunks (114 files, including those lazy-loaded from the webpack runtime), decoding of page RSC payloads, and single requests to the endpoints (spacing of at least 1 s, in line with `Crawl-delay: 1`). No login and no circumvention of any protection. Live checks are rare and manual.

## Reading order

| File | Covers |
|---|---|
| This README | Service architecture, access channels, data domains, key findings |
| [endpoints.md](endpoints.md) | Catalog of `/api/*` JSON endpoints and server actions |
| [pages-rsc.md](pages-rsc.md) | Server-rendered pages as a data source: filters, sorting, pagination, props |
| [entities.md](entities.md) | Entities, identifiers, relations, value dictionaries |
| [samples/](samples/) | Trimmed response samples (`api.*.json`, `page.*.json`) |
| [../capability-matrix.md](../capability-matrix.md) | What the CLI and MCP tools offer, with status |
| [../open-questions.md](../open-questions.md) | Open hypotheses and resolved checks |
| [../decisions.md](../decisions.md) | Architecture decisions |

## Certainty tags

| Tag | Meaning |
|---|---|
| `[P]`, `[P YYYY-MM-DD]` | Confirmed in a request or response (dated when added after the first survey) |
| `[P z kodu]` | Confirmed in the client code (JS bundle); for server behaviour treat as `[W]` |
| `[W]` | Inference from observations, no direct test |
| `[H]` | Hypothesis, tracked in [open-questions.md](../open-questions.md) |

## 1. Service architecture

| Element | Observation | Status |
|---|---|---|
| Framework | Next.js App Router (React Server Components), `x-powered-by: Next.js` | [P] |
| CDN | Cloudflare in front of the whole service, edge cache for HTML and `/api/*` | [P] |
| Client state | React Query (`queryKey`, `staleTime`), plain same-origin `fetch` | [P] |
| Session / auth | No cookies (`set-cookie` appears in no response), no tokens, no auth headers | [P] |
| Bot protection | Plain requests with a browser UA get through. Cloudflare Turnstile only in forms (reports) | [P] |
| `robots.txt` | `Disallow: /api/`, `/internal/`, `/cron/`; `Crawl-delay: 1` | [P] |
| Backend behind Next.js | SSR pages receive `initialApiParams` (`filterPrice`, `filterCitySlug`…), which suggests an internal API called server-side. The host does not leak to the client | [H] |

`robots.txt` excludes `/api/` for automated clients (see U1 in [open-questions.md](../open-questions.md)). The client makes the same requests as a browser and does so sparingly (cache, concurrency limit, no bulk crawling). Details in [decisions.md](../decisions.md).

## 2. Data access channels

The service has four channels with different stability and cost:

```
 A. JSON API           B. RSC payload          C. Server Actions     D. Static / CDN
 GET /api/*            GET <page>              POST + Next-Action    geojson, pmtiles
 34 paths              RSC: 1                  (response is RSC)
                       text/x-component
 ----------------------------------------------------------------------------------
 autocomplete,         lists with filters      valuation (also       county borders,
 statistics, maps,     and pagination,         has GET), price       map layers
 price history,        developer / investment  charts, competition
 valuation             / offer / address
                       details, GUS/NBP
 ----------------------------------------------------------------------------------
 stable JSON           moderately stable       unstable (IDs change  stable (files)
                       (depends on prop names) with each deploy)
```

### A. JSON API `/api/*` [P]

- Same-origin, `GET`, `application/json`, no session.
- CF cache: `s-maxage` from 300 s (offers, counters) to 86400 s (RCN statistics); `max-age=28800` for the browser. Some endpoints (`cities`, `location-search`, `sale-events`, `map/investments/visible`) and RSC pages have no `s-maxage`, only `max-age=28800` (pages: `private`) [P 2026-10-10].
- Parameters are always in the query string or path. No body or special headers are required.
- Errors: `400 {"error": "..."}` on a bad parameter (e.g. `avg-price-trend/building/<slug>` instead of an id). `valuation-pdf` explicitly handles `429` + `Retry-After`.
- Full catalog: [endpoints.md](endpoints.md).

### B. Page RSC payload (Server Components) [P]

Lists (flats, investments, developers, transactions, addresses) and detail pages have no JSON API of their own. The data is rendered on the server and passed as props of client components (`initialData`, `investments`, `sales`, `data`…). The UI changes filters, sorting and page through `router.push(?…)`, that is a new RSC request, not a `fetch` to the API.

- Request: `GET <page path>?<filters>&_rsc=<anything>` with the `RSC: 1` header → `content-type: text/x-component`, ~10× less data than HTML.
- The `_rsc` parameter is needed because Cloudflare ignores `Vary: RSC`: without it we get cached HTML [P].
- Format: rows `<id>:<json>` (up to `\n`) and `<id>:T<hexlen>,<text>` (length in bytes, no `\n`; binary tags work the same way); props are in elements `["$","$L<id>",null,{...props}]`. Unknown city: HTTP 200 + an `E` row with digest `NEXT_HTTP_ERROR_FALLBACK;404` [P 2026-10-10]. Details: [pages-rsc.md](pages-rsc.md). Reference parser: [`src/deweloperuch_mcp/flight.py`](../../src/deweloperuch_mcp/flight.py) (`rows`, `component_props`, `error_digests`; `recon/flight.py` re-exports it).
- Pagination has a hard limit of **20 pages** (`page=21` → returns page 20) [P]. `perPage` ∈ {10, 25, 50, 100} accepted (20 and 500 → 10) [P].
- Per-page details: [pages-rsc.md](pages-rsc.md).

### C. Next.js Server Actions [P]

`POST <page>` with headers `Next-Action: <id>`, `Accept: text/x-component`, body = JSON array of arguments. The response is RSC (`0:{…}` / `1:<result>`). The action ID is a hash that **changes with every deploy** [W]. It can be read from the JS chunks (the export name is explicit: `createServerReference("<id>",…,"fetchStandaloneValuation")`), see [`recon/scan_bundles.py`](../../recon/scan_bundles.py) (a read-only scanner of the public JS chunks).

| Action | Type | Notes |
|---|---|---|
| `fetchStandaloneValuation` | read | Result identical to `GET /api/standalone-valuation` [P], so we use GET |
| `reverseGeocodeAddress` | read | lat/lng → address |
| `fetchBatchPriceChartData` | read | price charts for a list of `sale_id`; probably duplicates `/api/sale-events` [H] |
| `fetchCompetitorInvestment`, `searchCompetitorInvestments` | read | unit report, comparison with competition |
| `fetchDevelopers`, `fetchInvestments`, `fetchDeveloperAbuse` | read | "report a developer" form |
| `createSaleRcnReport`, `createInvestmentAction` | **write** + Turnstile | exist in the client; never used by this project |

### D. Static resources / CDN [P in code, not downloaded]

- `/geo/powiaty.geojson`: county borders, `properties.id` = `powiat_rcn_id` [W].
- `https://cdn.deweloperuch.pl/warstwa/powodz/…`: flood risk layer (tiles).
- `https://cdn.deweloperuch.pl/warstwa/airbnb/airbnb-points.pmtiles`: Airbnb points (PMTiles).
- Map base: `tiles.openfreemap.org/styles/liberty`.

## 3. Data domains (summary)

| Domain | Primary source | Main channels |
|---|---|---|
| **Developer offers** (asking prices, change history) | developer sites / listings (`source: ANNOUCMENT`, `ANNOUCMENT_PR`, `scraper_pr`) | B (lists, details), A (`map/*`, `offers/city-sales`, `sale-events`, counters, distributions) |
| **RCN transactions** (transaction prices) | Real Estate Price Register / GUGiK (`transactionId: "PL.PZGIK.…"`) | B (lists, addresses), A (`map/powiat-*`, `map/transactions/visible`, statistics) |
| **Market statistics** | aggregates from RCN and offers | A (`monthly-transaction-stats`, `powiat-price-trend`, `avg-price-trend`, `city-transaction-stats`, distributions), B (`/statystyki/...`) |
| **Government statistics** | GUS (flats completed/started, demographics, unemployment, wages), NBP (asking/transaction prices, primary/secondary market) | B only (`/statystyki/statystyki-rzadowe/{loc}`) |
| **Listing portals** | daily "blue/green × sell/rent" series | A (`announcement-stats`) |
| **Valuation** | comparative, based on RCN within a radius | A (`standalone-valuation`), B (unit/investment report) |
| **Locations** | dictionaries of cities/districts/streets, counties | A (`cities`, `location-search`, `city-districts`, `investment-streets`, `city-lookup`, `map/city-powiats`) |
| **Violation reports** (price transparency) | crowdsourcing | B (`/zglos-dewelopera/mapa-zgloszen`) |
| Calculators / loans | client-side computation | out of scope |

Entity and ID model: [entities.md](entities.md).

## 4. Key findings for the project

1. **There is no single API for everything.** Search with filters and pagination exists only as RSC pages. The JSON API covers autocomplete, maps, statistics and history.
2. **Search via RSC has a ceiling of 20 × perPage(100) = 2000 results** per query [P]. Larger sets have to be narrowed with filters or fetched in bulk through the JSON API (e.g. `offers/city-sales/{city}`: 1.3 MB for Warsaw, 13,351 offers; CF cache 5 min).
3. **Transaction data per county is huge.** `map/powiat-sales/{id}` for Sopot is 1.6 MB with 6,636 transactions; for Warsaw an estimated ~80 MB [W]. Not suitable for passing to a model. Better to use RCN lists with filters.
4. **Valuation has a stable GET** (`/api/standalone-valuation`), so we do not need the server action.
5. **The investment slug is effectively a global ID.** The investment page ignores the city and developer segments in the URL [P], and `map/investments/visible/{slug}` takes the slug alone [P].
6. **Backend naming is misleading**: in RCN, "invest" means a building/address (`invest_rcn_id`) and "sale" means a unit. The domain should rename this (Building/Unit/Transaction).
7. **Numeric types are inconsistent**: amounts sometimes as `number`, sometimes as `string` (`"amount": "994012"`). Dates are sometimes `YYYY-MM-DD`, sometimes ISO with `T00:00:00.000Z`. The DTO→domain layer has to normalize this.

## 5. Sample format

Samples in [samples/](samples/) are saved by `python3 recon/probe.py … --save` as `api.<name>[.<variant>].json` or `page.<name>[.<variant>].json`:

- an envelope with `_request` (the request), `_captured` (the date) and the data: `response` (JSON API), `props` or `_prop` + `value` (RSC page);
- arrays trimmed to 3 elements followed by the string `"... (N more, M total)"`; maps with numeric keys and more than 40 keys trimmed to 2 keys plus `"...": "N more keys"`;
- personal data (e.g. `additionalInfo`, `email`, `phone`, `telefon`) replaced with `"[usunięte]"`;
- existing samples are never overwritten; a new observation becomes a new variant.

Raw, untrimmed responses used by tests live in `tests/fixtures/` (see the README files there).
