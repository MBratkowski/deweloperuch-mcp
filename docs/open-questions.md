# Gaps, hypotheses, things to check

Priority: **P1** blocks the vertical slice, **P2** needed before the full v1, **P3** nice-to-have.

## For the user to decide

| # | Question | Why it matters |
|---|---|---|
| U1 | (Until resolved, the interim D9 rule applies: live requests only with the user's consent.) **Policy on `robots.txt: Disallow: /api/`.** Our client calls the same endpoints as the browser, but robots excludes `/api/` for automated clients. Do we contact the authors (active on GitHub `deweloperuch`, X, TikTok) to obtain permission or official access? | Risk of being blocked, and ethics; affects how the client is identified (UA) |
| U2 | ~~Technology stack~~: **resolved 2026-10-09: Python** (decisions.md D8) | Repo foundation |
| U3 | ~~MCP operating mode~~: **resolved 2026-10-10: stdio only** (decisions.md D11) | Affects caching and rate limiting (shared vs per-user) |

## Technical

| # | P | What | Type | How to check |
|---|---|---|---|---|
| T1 | P1 | Resolving `sale_id` → investment. `sale-events` does not return the investment | luka | Check other channels (e.g. `fetchBatchPriceChartData`). Alternative: require `investment_slug` in `get_offer`, since we always have it from search results |
| T4 | P2 | `filterDistrict` in transactions does not narrow results strictly (results from outside Mokotów?) | [H] | Compare `stats.totalTransactions` with/without the filter, check addresses |
| T5 | P2 | Format of `filterLastTransactionDate` (quarters, "Before 2017") | [H] | Browser network traffic after setting the filter |
| T7 | P2 | Offer-report slug collisions (`D1.1.1.4` vs `D1.11.4`) and how the server resolves them | [W] | Find an investment with colliding names |
| T8 | P2 | **Geocoding address → lat/lng** for valuation. UI /wycena: where does it get coordinates? No external geocoder in the bundles | luka | Network traffic on /wycena after entering an address. Fallback: street lat/lng from `location-search` |
| T9 | P2 | Histogram bucket boundaries (`aligned: true`) | [W] | Read module `84462` in chunk `2438` |
| T10 | P2 | Period and base of `*_change` in `city-transaction-stats` / the county map; whether `avg_*` is a median | [H] | Compare with `monthly-transaction-stats` |
| T11 | P2 | Rate limiting: at what pace do CF/the app respond with 429/a block? Does an honest User-Agent (`deweloperuch-mcp/x.y`) get through? | [H] | Careful test of single requests with a different UA; **no load tests** |
| T13 | P3 | `announcement-stats`: meaning of `blue/green`, `value`; correct `region` for the whole of Poland | 🔴 | Content of the /statystyki/portale-ogloszeniowe page (legend, descriptions) in a browser |
| T14 | P3 | Semantics of the fields `filteredStats`, `citiesStats` (developer profile), `slices` (statistics) | [H] | Comparison with the UI |
| T15 | P3 | Not analyzed: `/kredyty`, calculators (probably no backend data) | — | — |
| T16 | P3 | Verifying traffic in a real browser (DevTools/HAR) as a completeness check of the static analysis, especially map and filter interactions | — | Chrome session with network recording |
| T17 | P3 | Whether `Next-Router-State-Tree` is required for server actions | [H] | Only if we ever use C |
| T29 | P3 | Full list of allowed `perPage` (observed: 10, 25, 50, 100 accepted; 20, 500 → 10) | [H] | A few values, e.g. 30, 75; after T2 |
| T30 | P3 | Actual key of `sortBy=last_event_date` (does not match the visible `last_event_date`; maybe `last_change_event_date`) and the untested `investment`, `last_amount_difference(_percent)`, `start_amount_difference` | [H] | One request per value, compare with list fields |
| T31 | P3 | `success: false` in `/api/sale-events`: when it occurs (an unknown ID gives `success: true, saleData: null`; bad/empty `saleId`?) | [H] | 1–2 requests with a bad `saleId` |
| T32 | P3 | `count` in `location-search` for `street` and `city` (is it the number of active offers; in transaction mode, transactions) | [H] | Compare with `total` of the `filterStreet=` list / `/api/cities offerCount` |
| T33 | P3 | Untested offer-list filter values: `filterPriceChange=increase,no_change` and csv, `filterStatus=active`, sentinel `filterPricePerM2=…-999999`, `filterDeveloper`, `filterProject`, `filterStreet`, `filterAnomalies`, `showArchivedInvestments` | [W] | Control requests comparing `total` |
| T34 | P2 | Response for `page` > `totalPages` with a known city (e.g. Kraków, `filterPrice=0-300000`, page M+1): an empty page, clamping to the last page (like `page>20` → 20) or `notFound()` (digest 404; MCP would then say "unknown city")? Test: `tests/e2e/test_live_mcp.py::test_offers_page_past_the_last_one` | [H] | 1 request, check `initialData` and `E` rows |
| T35 | P2 | Whether a district slug (e.g. `mokotow`) as `{city}` gives a 404 digest. Test: `test_offers_district_slug_as_city_is_an_unknown_city` | [H] | 1 request |
| T36 | P2 | Whether the digest `NEXT_HTTP_ERROR_FALLBACK;404` also appears on other RSC pages (investments, developers, details); confirmed only on the offer list | [H] | 1 request per page with an unknown slug |
| T37 | P3 | Whether raw RSC payloads should be a separate sample type in `docs/discovery/samples/` (today: `tests/fixtures/rsc/`, while samples are trimmed JSON with an envelope) | [H] | Decision after reviewing sample conventions (no requests) |

## Resolved

| # | Date | Result | Sample |
|---|---|---|---|
| T2 | 2026-10-10 | Refuted: `perPage=25` accepted (`pagination.perPage: 25`, 25 rows). The allowed set is not {10, 50, 100}; the full list opened as T29 | (no separate sample; result in `pages-rsc.md`) |
| T3 | 2026-10-10 | By default (no `sortBy`) and with an unknown value: ascending by `sale_id`, no error. Confirmed: `amount` (asc, desc), `price_per_sqm`, `size`, `name`, `start_amount_difference_percent`. `last_event_date` accepted, key unclear (T30). The rest [W] (T30) | `page.offers_list.sort_desc` |
| T6 | 2026-10-10 | `filterPriceChange=decrease` works (13324 → 2416, by change from the initial price); `filterStatus=archived` works (11415, all archived); `includeArchived=true` works (24739 = 13324 + 11415); `filterRooms` and `filterFloors` **do not work** on the offer list (total unchanged). Other values: T33 | (no separate sample; result in `pages-rsc.md`) |
| T12 | 2026-10-10 | `city-sales` contains no archived offers (`includeArchived` ignored, Sopot 6/6 `active`); `polska` → `400 Invalid citySlug` (does not work) | (observation without a sample; `api.city_sales_sopot`) |
| T18 (a) | 2026-10-10 | Unknown slug in `map/investments/visible/{slug}`: `404 {"error":"Investment not found"}` | (non-2xx, no sample) |
| T19 (b) | 2026-10-10 | Unknown city on the page `/ceny-ofertowe/{city}/mieszkania`: HTTP 200 RSC without `initialData`, with a `notFound` segment; the client must detect the missing prop | (no sample) |
| T20 (c) | 2026-10-10 | Slug alphabet: 166 of 168 slugs in the samples are `[a-z0-9-]`; 2 exceptions (`Metro-Art`, `Forrest`) only in the reports map, a different entity type. Level [W] (observation, not a server test) | `page.developer_abuse_map` |
| T21 (d) | 2026-10-10 | District `count` = number of active offers (Mokotów: 1562 = `total` from `filterDistrict`). For streets and cities: T32 | `api.location_search.kinds_limit20` |
| T22 (e) | 2026-10-10 | `limit` honored up to at least 20 (`q=mo&limit=20` → 20 results); `kind` ∈ {`city`, `district`, `street`}; no "more" flag; `q` with 1 character → empty list | `api.location_search.kinds_limit20` |
| T23 (f) | 2026-10-10 | `sortBy=amount&sortOrder=desc` works (descending from 7,820,948) | `page.offers_list.sort_desc` |
| T24 (g) | 2026-10-10 | Partially: unknown `saleId` → `200 {success: true, saleData: null, events: []}`; `success: false` not observed (T31) | (no sample) |
| T25 (h) | 2026-10-10 | Sentinels: `filterPrice=0-99999999&filterSize=0-9999` → total 13324 = result without filters. Price/m² (`999999`) untested (T33) | (no separate sample) |
| T26 (i) | 2026-10-10 | RSC pages: `private, max-age=28800, must-revalidate` (no `s-maxage`). `city-sales`: `public, max-age=28800, s-maxage=300, stale-while-revalidate=3600`. `cities`, `sale-events`, `map/investments/visible` (also 404): `max-age=28800` without `s-maxage`. `location-search`: `private, max-age=28800`. They require `DEFAULT_TTL` in the transport | — |
| T27 (j) | 2026-10-10 | `/api/cities`: `page` works; `total` = all matching, `page` = page number, `hasMore` = there are further pages (`limit=2`: page 1 → `hasMore: true`, page 2 → `false`, `total: 4`) | `api.cities_q` (without `hasMore: true`) |
| T28 (`OFFER_EVENT`) | 2026-10-10 | Every asking-price entry, not only the first price (offer 4397: 12 `OFFER_EVENT` events with varying amounts = `total_events`) | `api.sale_events.price_history` |

## Alternative / supplementary sources

| Source | What it gives | Limitations |
|---|---|---|
| `github.com/deweloperuch/rejestr-cen-nieruchomosci` | Raw RCN data (GML), **CC0 license**, 12 cities (Gdańsk, Gdynia, Katowice, Kraków, Łódź, Łomża, Lublin, Olsztyn, Sopot, Toruń, Warszawa, Wrocław) | Last push 2025-11-08, so the snapshot is older than the service (data up to 2026-08); the GML format needs a parser. Candidate for a second data source in the architecture |
| GUGiK / Geoportal (RCN) | `transactionId: "PL.PZGIK.…"` with 2026 download dates suggests the service is fed from the national RCN service | [H], not investigated; potential primary source |
