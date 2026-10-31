# deweloperuch.pl: data layer map

Findings about how the service exposes its data, gathered for `deweloperuch-mcp`. Last full survey: **2026-10-09**, with additions through 2026-10-16 (Next.js build `KD_IOP6Grqba7xa86pGVG`, Next.js 15.1.9). **Redesign survey: 2026-10-30** ("deweloperuch 2.0", deployed 2026-10-29): build `VDpA73sQ-GRMsEMdmIQtu`, Next.js 15.5.25, still webpack. It rests on a bundle scan (98 of at least 146 chunks, incomplete, T62), the saved HTML of 21 pages, the live e2e run of 2026-10-29 and 12 probe requests of 2026-10-30. Section 6 summarises what changed; entries tagged `[P 2026-10-29]` or `[P 2026-10-30]` in the other files were re-checked on 2.0, all others date from the 2026-10-09 survey.

Method: static analysis of all client JS chunks (114 files, including those lazy-loaded from the webpack runtime), decoding of page RSC payloads, and single requests to the endpoints (spacing of at least 1 s, in line with `Crawl-delay: 1`). No login and no circumvention of any protection. Live checks are rare and manual. On 2026-10-30 the RSC payload could not be fetched (every RSC request is redirected, see [pages-rsc.md](pages-rsc.md)), so page props were decoded from the full HTML saved by the scanner.

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
| Framework | Next.js App Router (React Server Components), `x-powered-by: Next.js`; 15.1.9 until 2026-10-09, 15.5.25 since the 2.0 deploy, webpack both times | [P], 15.5.25 [P 2026-10-30] |
| CDN | Cloudflare in front of the whole service, edge cache for HTML and `/api/*` | [P] |
| Client state | React Query (`queryKey`, `staleTime`), plain same-origin `fetch` | [P] |
| Session / auth | No cookies (`set-cookie` appears in no response), no tokens, no auth headers | [P] |
| Bot protection | Plain requests get through (the project's honest UA too, D18). Cloudflare Turnstile was only in the report forms, which the 2.0 build removed (their pages answer 410) | [P], Turnstile gone [P 2026-10-30] |
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

2.0 [P 2026-10-30]: channel A has 11 of its 34 paths unused by the client (4 answer 404, 2 still answer 200, 5 not requested) and 14 new ones; channel B returns no payload for the old request shape (redirects); channel C shrank to 4 actions, none of them a write action. Details in section 6.

### A. JSON API `/api/*` [P]

- Same-origin, `GET`, `application/json`, no session.
- CF cache: `s-maxage` from 300 s (offers, counters) to 86400 s (RCN statistics); `max-age=28800` for the browser. Some endpoints (`cities`, `location-search`, `sale-events`, `map/investments/visible`) and RSC pages have no `s-maxage`, only `max-age=28800` (pages: `private`) [P 2026-10-10]. 2.0 [P 2026-10-30]: the 11 JSON responses probed all send `public, max-age=28800, s-maxage=N, stale-while-revalidate=M` (N from 300 to 86400, M from 86400 to 604800), including `cities`, `sale-events` and `map/investments/visible`; the HTML 404 of a removed route has `private, max-age=28800, must-revalidate`.
- Parameters are always in the query string or path. No body or special headers are required.
- Errors: `400 {"error": "..."}` on a bad parameter (e.g. `avg-price-trend/building/<slug>` instead of an id). `valuation-pdf` explicitly handles `429` + `Retry-After`. 2.0: a route that no longer exists answers `404` with the Next.js HTML not-found page (about 36 KB, `text/html`), not JSON [P 2026-10-30, `investments/{id}/sale-events`].
- Full catalog: [endpoints.md](endpoints.md).

### B. Page RSC payload (Server Components) [P]

Lists (flats, investments, developers, transactions, addresses) and detail pages have no JSON API of their own. The data is rendered on the server and passed as props of client components (`initialData`, `investments`, `sales`, `data`…). The UI changes filters, sorting and page through `router.push(?…)`, that is a new RSC request, not a `fetch` to the API.

- Request: `GET <page path>?<filters>&_rsc` (an empty `_rsc`; since the redesign of 2026-10-29 any other value gets a 307 to that URL) with the `RSC: 1` header → `content-type: text/x-component`, ~10× less data than HTML.
- The `_rsc` parameter is needed because Cloudflare ignores `Vary: RSC`: without it we get cached HTML [P].
- Format: rows `<id>:<json>` (up to `\n`) and `<id>:T<hexlen>,<text>` (length in bytes, no `\n`; binary tags work the same way); props are in elements `["$","$L<id>",null,{...props}]`. Unknown city: HTTP 200 + an `E` row with digest `NEXT_HTTP_ERROR_FALLBACK;404` [P 2026-10-10]. Details: [pages-rsc.md](pages-rsc.md). Reference parser: [`src/deweloperuch_mcp/flight.py`](../../src/deweloperuch_mcp/flight.py) (`rows`, `component_props`, `error_digests`; `recon/flight.py` re-exports it).
- Pagination has a hard limit of **20 pages** (`page=21` → returns page 20) [P]. `perPage` ∈ {10, 25, 50, 100} accepted (20 and 500 → 10) [P]. 2.0: the default is 25 per page and `totalPages` is still capped at 20 [P 2026-10-30, saved pages]; the other limits are untested.
- **2.0: every RSC request is redirected** (`308` when the query has `page=1`, otherwise `307` to the same URL with an empty `_rsc`), so no RSC payload of the 2.0 service has been seen yet; most page props were renamed (T57, T63). Details: [pages-rsc.md](pages-rsc.md).
- Per-page details: [pages-rsc.md](pages-rsc.md).

### C. Next.js Server Actions [P]

`POST <page>` with headers `Next-Action: <id>`, `Accept: text/x-component`, body = JSON array of arguments. The response is RSC (`0:{…}` / `1:<result>`). The action ID is a hash that **changes with every deploy** [W]. It can be read from the JS chunks (the export name is explicit: `createServerReference("<id>",…,"fetchStandaloneValuation")`), see [`recon/scan_bundles.py`](../../recon/scan_bundles.py) (a read-only scanner of the public JS chunks).

| Action | Type | Notes (2026-10-09) | In the 2.0 client (2026-10-30) |
|---|---|---|---|
| `fetchStandaloneValuation` | read | Result identical to `GET /api/standalone-valuation` [P], so we use GET | not found |
| `reverseGeocodeAddress` | read | lat/lng → address | not found; `reverseGeocodeForClient` (chunk `6535`) is new and probably its successor [W] |
| `fetchBatchPriceChartData` | read | price charts for a list of `sale_id`; probably duplicates `/api/sale-events` [H] | not found; the client uses `sale-sparklines?ids=` |
| `fetchCompetitorInvestment`, `searchCompetitorInvestments` | read | unit report, comparison with competition | kept (chunk `2712`) |
| `fetchDevelopers`, `fetchInvestments`, `fetchDeveloperAbuse` | read | "report a developer" form | not found (the form is gone, its pages answer 410) |
| `createSaleRcnReport`, `createInvestmentAction` | **write** + Turnstile | exist in the client; never used by this project | not found (the form is gone) |
| `fetchOfferPriceSqmSeriesFiltered` | read (by its name) | - | new (chunk `1519`); not requested |

[P z kodu 2026-10-30]: 4 actions in the 97 chunks that were read (of at least 146); the scan is incomplete (T62), so an absent name may still live in an unread chunk. The call shape is unchanged.

### D. Static resources / CDN [P in code, not downloaded]

- `/geo/powiaty.geojson`: county borders, `properties.id` = `powiat_rcn_id` [W].
- `https://cdn.deweloperuch.pl/warstwa/powodz/…`: flood risk layer (tiles).
- `https://cdn.deweloperuch.pl/warstwa/airbnb/airbnb-points.pmtiles`: Airbnb points (PMTiles).
- Map base: `tiles.openfreemap.org/styles/liberty`.
- 2.0 [P z kodu 2026-10-30]: raster orthophoto tiles come from the app itself, `/api/map/orto/1/{z}/{x}/{y}` (512 px, zoom 8–18), and investment thumbnails from `/api/map/thumb/{investId}?v=…`; both are binary and listed in [endpoints.md](endpoints.md) section 7. `/api/map/powiat-sales/{powiatId}` is still used by the client (the dump of D5).

## 3. Data domains (summary)

| Domain | Primary source | Main channels |
|---|---|---|
| **Developer offers** (asking prices, change history) | developer sites / listings (`source: ANNOUCMENT`, `ANNOUCMENT_PR`, `scraper_pr`) | B (lists, details), A (`map/*`, `offers/city-sales`, `sale-events`, counters, distributions) |
| **RCN transactions** (transaction prices) | Real Estate Price Register / GUGiK (`transactionId: "PL.PZGIK.…"`) | B (lists, addresses), A (`map/powiat-*`, `map/transactions/visible`, statistics) |
| **Market statistics** | aggregates from RCN and offers | A (`monthly-transaction-stats` 404 since 2.0, `powiat-price-trend`, `avg-price-trend`, `city-transaction-stats`, distributions), B (`/statystyki/{location}/transakcje` and `/oferty` since 2.0; before `/statystyki/ceny-transakcyjne/...`) |
| **Government statistics** | GUS (flats completed/started, demographics, unemployment, wages), NBP (asking/transaction prices, primary/secondary market) | B only (`/statystyki/{loc}/dane-rzadowe` since 2.0; `/statystyki/statystyki-rzadowe/{loc}` before, now a 308) |
| **Listing portals** | daily "blue/green × sell/rent" series | A (`announcement-stats`) |
| **Valuation** | comparative, based on RCN within a radius | A (`standalone-valuation`), B (unit/investment report) |
| **Locations** | dictionaries of cities/districts/streets, counties | A (`cities`, `location-search`, `city-districts`, `investment-streets`, `city-lookup`, `map/city-powiats`) |
| **Violation reports** (price transparency) | crowdsourcing | B (`/zglos-dewelopera/mapa-zgloszen`); **gone since 2.0** (410) |
| Calculators / loans | client-side computation | out of scope |

Entity and ID model: [entities.md](entities.md).

## 4. Key findings for the project

1. **There is no single API for everything.** Search with filters and pagination exists only as RSC pages. The JSON API covers autocomplete, maps, statistics and history.
2. **Search via RSC has a ceiling of 20 × perPage(100) = 2000 results** per query [P]. Larger sets have to be narrowed with filters or fetched in bulk through the JSON API (e.g. `offers/city-sales/{city}`: 1.3 MB for Warsaw, 13,351 offers; CF cache 5 min; **404 since the 2.0 deploy**).
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
- existing samples are never overwritten; a new observation becomes a new variant;
- the trimming also applies to fixed-size tuples: each 4-element `ev` row of `api.map_inv_visible.v2` shows its 4th item as `"... (1 more, 4 total)"`; read the full shape in [endpoints.md](endpoints.md).

Raw, untrimmed responses used by tests live in `tests/fixtures/` (see the README files there).

## 6. Redesign of 2026-10-29 ("deweloperuch 2.0"), survey of 2026-10-30

| Area | What changed | Where |
|---|---|---|
| Build | `KD_IOP6Grqba7xa86pGVG` → `VDpA73sQ-GRMsEMdmIQtu`; Next.js 15.1.9 → 15.5.25; still webpack | this file |
| RSC requests | every `RSC: 1` request with a token is redirected (`308` with `page=1`, otherwise `307` to an empty `_rsc`); no payload seen yet | [pages-rsc.md](pages-rsc.md), T63 |
| Page routes | `/statystyki/…` restructured to `/statystyki/{location}/{section}`; `/ceny-ofertowe/polska/mieszkania` → `/ceny-ofertowe/polska/miasta`; the report pages answer 410 | [pages-rsc.md](pages-rsc.md), T55, T61 |
| Page props | `initialData`, `data`, `filteredStats`, `sortedLocations`, `tocItems`, `rawTransactions` and others are gone; lists use `sales`, `serverInvestments`, `transactions`, `addresses` with `serverPaginationData` or `serverPagination`; 25 rows by default | [pages-rsc.md](pages-rsc.md), T57 |
| JSON API, removed | `offers/city-sales`, `monthly-transaction-stats`, `map/powiat-stats`, `investments/{id}/sale-events` answer 404; 7 more paths are no longer used by the client (2 still answer 200) | [endpoints.md](endpoints.md) section 8, T58 |
| JSON API, new | 14 paths (statistics, sparklines, thumbnails, tiles, a transaction dump) and new parameters; none requested yet | [endpoints.md](endpoints.md) section 7, T59 |
| JSON API, changed | `visible/{slug}` carries `ev` (the price history of every offer) and `floor`; `city-districts` has `slug`; `investments` has `city`, `district`, `powiatId`, `archived`; `cities`, `city-lookup` accept `variant`/`source` and `slug` | [endpoints.md](endpoints.md) sections 1-2 |
| Cache | `s-maxage` and `stale-while-revalidate` on the JSON responses probed | section 2 A |
| Server actions | 4 found, none a write action; the report form and Turnstile are gone | section 2 C, T60 |
| Tools | `search_offers`, `get_developer`, `get_government_statistics`, `get_market_statistics`, `get_transaction_statistics` (months), `rank_locations` (counties) and `get_investment` (history) are broken; `search_locations`, `search_investments`, `search_developers`, `get_building` and `estimate_property_value` passed the live e2e run of 2026-10-29; `get_offer` and `get_investment` (without history) have not been run end to end (their e2e tests errored in fixtures that depend on `search_offers`) | [../capability-matrix.md](../capability-matrix.md) |
