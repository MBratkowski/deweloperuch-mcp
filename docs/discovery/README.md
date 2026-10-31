# deweloperuch.pl: data layer map

Findings about how the service exposes its data, gathered for `deweloperuch-mcp`. Last full survey: **2026-10-09**, with additions through 2026-10-16 (Next.js build `KD_IOP6Grqba7xa86pGVG`, Next.js 15.1.9). **Redesign survey: 2026-10-30, with live checks of 2026-10-31 (round B2)** ("deweloperuch 2.0", deployed 2026-10-29): build `VDpA73sQ-GRMsEMdmIQtu`, Next.js 15.5.25, still webpack (not re-checked on 2026-10-31). It rests on a bundle scan (98 of at least 146 chunks, incomplete, T62), the saved HTML of 21 pages, the live e2e run of 2026-10-29, 19 probe requests of 2026-10-30 (two series, 12 and 7), 1 of the morning of 2026-10-31 and the 30 of round B2 on 2026-10-31 (the RSC payload with an empty `_rsc`, the answers for unknown entities, the list parameters, `map/offer-snapshot`). Section 6 summarises what changed; entries tagged `[P 2026-10-29]`, `[P 2026-10-30]` or `[P 2026-10-31]` in the other files were re-checked on 2.0, all others date from the 2026-10-09 survey.

Method: static analysis of all client JS chunks (114 files, including those lazy-loaded from the webpack runtime), decoding of page RSC payloads, and single requests to the endpoints (spacing of at least 1 s, in line with `Crawl-delay: 1`). No login and no circumvention of any protection. Live checks are rare and manual. On 2026-10-30 the RSC payload could not be fetched with a hashed `_rsc` (every such request is redirected, see [pages-rsc.md](pages-rsc.md)), so page props were decoded from the full HTML saved by the scanner; on 2026-10-31 an empty `_rsc` returned the payload (T63) and the props of 4 pages were checked against the saved HTML.

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

2.0 [P 2026-10-30]: channel A has 11 of its 34 paths unused by the client (4 answer 404, 2 still answer 200, 5 not requested) and 14 new ones; channel B redirects a request with a hashed `_rsc` and returns the payload for an empty one [P 2026-10-31]; channel C shrank to 4 actions, none of them a write action. Details in section 6.

### A. JSON API `/api/*` [P]

- Same-origin, `GET`, `application/json`, no session.
- CF cache: `s-maxage` from 300 s (offers, counters) to 86400 s (RCN statistics); `max-age=28800` for the browser. Some endpoints (`cities`, `location-search`, `sale-events`, `map/investments/visible`) and RSC pages have no `s-maxage`, only `max-age=28800` (pages: `private`) [P 2026-10-10]. 2.0 [P 2026-10-30]: the 11 JSON responses probed all send `public, max-age=28800, s-maxage=N, stale-while-revalidate=M` (N from 300 to 86400, M from 86400 to 604800), including `cities`, `sale-events` and `map/investments/visible`; the HTML 404 of a removed route has `private, max-age=28800, must-revalidate`. In a second series later the same day every response (JSON 200, JSON 404, HTML 404) carried `max-age=172800` instead, `s-maxage` unchanged [P 2026-10-30]; probably a CDN browser-TTL setting, not the application [W]. The client caps its TTL at 300 s (D2), so nothing changes in code.
- Parameters are always in the query string or path. No body or special headers are required.
- Errors: `400 {"error": "..."}` on a bad parameter (e.g. `avg-price-trend/building/<slug>` instead of an id). `valuation-pdf` explicitly handles `429` + `Retry-After`. 2.0: a 404 tells two cases apart by its media type [P 2026-10-30, [endpoints.md](endpoints.md) section 9]. An unknown entity on a live route is `404` + `application/json` + `{"error": "..."}` (unknown investment, RCN building, city); a route that no longer exists is `404` + `text/html`, the Next.js not-found page (36,628 B, build comment `VDpA73sQ_GRMsEMdmIQtu`, 4 routes), also for a request that asks for JSON. `sale-events` is the exception: an unknown id is `200` with `saleData: null`.
- Full catalog: [endpoints.md](endpoints.md).

### B. Page RSC payload (Server Components) [P]

Lists (flats, investments, developers, transactions, addresses) and detail pages have no JSON API of their own. The data is rendered on the server and passed as props of client components (`initialData`, `investments`, `sales`, `data`…). The UI changes filters, sorting and page through `router.push(?…)`, that is a new RSC request, not a `fetch` to the API.

- Request: `GET <page path>?<filters>&_rsc=` (an **empty** `_rsc`, last) with the `RSC: 1` header → `content-type: text/x-component`, 1.6 to 3.8 times less data than the HTML [P 2026-10-31] (~10× on 1.0).
- The `_rsc` parameter is needed because Cloudflare ignores `Vary: RSC`: without it we get cached HTML [P] (1.0). On 2.0 a hashed or invented value is redirected to the empty one (`307`, or `308` with `page=1`) [P 2026-10-29], and the empty value returns the payload [P 2026-10-31, T63]; why it is empty: [pages-rsc.md](pages-rsc.md) "How to fetch".
- Format: rows `<id>:<json>` (up to `\n`) and `<id>:T<hexlen>,<text>` (length in bytes, no `\n`; binary tags work the same way); props are in elements `["$","$L<id>",null,{...props}]`. Unknown city: HTTP 200 + an `E` row with digest `NEXT_HTTP_ERROR_FALLBACK;404` [P 2026-10-10]; 2.0 [P 2026-10-31]: the same for an unknown city, district and developer, but an unknown location on the statistics pages is an HTTP **404** with `text/x-component` ([endpoints.md](endpoints.md) section 9). Details: [pages-rsc.md](pages-rsc.md). Reference parser: [`src/deweloperuch_mcp/flight.py`](../../src/deweloperuch_mcp/flight.py) (`rows`, `component_props`, `error_digests`; `recon/flight.py` re-exports it).
- Pagination has a hard limit of **20 pages** (`page=21` → returns page 20) [P]. `perPage` ∈ {10, 25, 50, 100} accepted (20 and 500 → 10) [P]. 2.0: the default is 25 per page and `totalPages` is still capped at 20; `perPage=10` and `100` and `page=2` work [P 2026-10-31]; the other values are untested (T29).
- **2.0: the props of most pages were renamed** (T57): the offer list has `sales` and `serverPaginationData`, the developer page `hero` (with the developer's name, id and investments), the statistics pages `view`, `latestSummary`, `blocks`, `data`; the district offer list is a route (`/ceny-ofertowe/{city}/{district}/mieszkania`), `filterDistrict` no longer works. Details: [pages-rsc.md](pages-rsc.md).
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
- the trimming also applies to fixed-size tuples: each 4-element `ev` row of `api.map_inv_visible.v2` shows its 4th item as `"... (1 more, 4 total)"`; read the full shape in [endpoints.md](endpoints.md). Two consequences found on 2026-10-31: the 7-element sales tuples of `api.offer_snapshot.sopot` keep only their first 3 items (no amount, area or price per m²), and a page prop that is a React element `["$", "$L<id>", null, {props}]` (4 items) keeps everything but its props (`page.developer.v2_hero` holds no data). For a sample with data, ask for a prop inside the element (`--prop investments`) and take the shapes of tuples from [endpoints.md](endpoints.md).

Raw, untrimmed responses used by tests live in `tests/fixtures/` (see the README files there).

## 6. Redesign of 2026-10-29 ("deweloperuch 2.0"), survey of 2026-10-30

| Area | What changed | Where |
|---|---|---|
| Build | `KD_IOP6Grqba7xa86pGVG` → `VDpA73sQ-GRMsEMdmIQtu`; Next.js 15.1.9 → 15.5.25; still webpack | this file |
| RSC requests | a request with a hashed `_rsc` is redirected (`308` with `page=1`, otherwise `307` to an empty `_rsc`) [P 2026-10-29]; **the empty `_rsc` returns the payload** (`200 text/x-component`, 27 to 62 % of the HTML) [P 2026-10-31] | [pages-rsc.md](pages-rsc.md), T63 (resolved) |
| Page routes | `/statystyki/…` restructured to `/statystyki/{location}/{section}`; `/ceny-ofertowe/polska/mieszkania` → `/ceny-ofertowe/polska/miasta`; the report pages answer 410. Three routes are promoted to headings and in `PAGE_ROUTES` since 2026-10-31, and all three were requested: `/statystyki/{location}/transakcje`, `/statystyki/{location}/dane-rzadowe`, `/ceny-ofertowe/{city}/{district}/mieszkania` (T70 resolved) | [pages-rsc.md](pages-rsc.md), T55, T61 |
| Page props | `initialData`, `data`, `filteredStats`, `sortedLocations`, `tocItems`, `rawTransactions` and others are gone; lists use `sales`, `serverInvestments`, `transactions`, `addresses` with `serverPaginationData` or `serverPagination`; 25 rows by default. The RSC payload has these props on the 4 pages compared (offers list, developer page, `dane-rzadowe`, `transakcje`) [P 2026-10-31]; the developer's name and id sit in the element of the prop `hero`; `filterDistrict` no longer works, the district list is a route | [pages-rsc.md](pages-rsc.md), T57, T73 |
| JSON API, removed | `offers/city-sales`, `monthly-transaction-stats`, `map/powiat-stats`, `investments/{id}/sale-events` answer 404 with the Next.js HTML not-found page (the same 36,628 B on all four [P 2026-10-30]); 7 more paths are no longer used by the client (2 still answer 200) | [endpoints.md](endpoints.md) sections 8 and 9, T58 |
| JSON API, 404 rule | an unknown entity on a live route is `404` + `application/json` + `{"error": …}` (investment, RCN building, city); a removed route is `404` + `text/html`; `sale-events` answers an unknown id with `200` and `saleData: null` [P 2026-10-30]. Pages: an unknown city, district or developer is a `200` with the 404 digest, an unknown location on the two statistics pages is a `404` with `text/x-component` [P 2026-10-31] | [endpoints.md](endpoints.md) section 9 |
| JSON API, new | 14 paths (statistics, sparklines, thumbnails, tiles, a transaction dump) and new parameters. Two are promoted to headings and in `API_PATHS` since 2026-10-31: `map/offer-snapshot/{citySlug}` (D20; requested, a list of the city's active offers as positional tuples, 532,198 B for Warszawa, T69 resolved) and `statystyki/raw-transactions` (a D5 dump, never requested) | [endpoints.md](endpoints.md) sections 2, 3 and 7, T59 |
| JSON API, changed | `visible/{slug}` carries `ev` (the price history of every offer) and `floor`; `city-districts` has `slug`; `investments` has `city`, `district`, `powiatId`, `archived`; `cities`, `city-lookup` accept `variant`/`source` and `slug` | [endpoints.md](endpoints.md) sections 1-2 |
| Cache | `s-maxage` and `stale-while-revalidate` on the JSON responses probed | section 2 A |
| Server actions | 4 found, none a write action; the report form and Turnstile are gone | section 2 C, T60 |
| Tools | `search_offers`, `get_developer`, `get_government_statistics`, `get_market_statistics`, `get_transaction_statistics` (months), `rank_locations` (counties) and `get_investment` (history) are broken; `search_locations`, `search_investments`, `search_developers`, `get_building` and `estimate_property_value` passed the live e2e run of 2026-10-29; `get_offer` and `get_investment` (without history) have not been run end to end (their e2e tests errored in fixtures that depend on `search_offers`) | [../capability-matrix.md](../capability-matrix.md) |
