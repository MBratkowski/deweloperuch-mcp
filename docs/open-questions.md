# Open questions

Hypotheses and gaps in the knowledge of the service, plus the checks already resolved. Certainty tags are explained in [discovery/README.md](discovery/README.md). Live checks are rare and manual, made sparingly and read-only.

Priority: **P1** blocks a core capability, **P2** needed for a complete v1, **P3** nice-to-have.

## Policy and decisions

| # | Question | Why it matters |
|---|---|---|
| U1 | ~~Policy on `robots.txt: Disallow: /api/`~~: **resolved 2026-10-14** — the service authors agreed to the project's use of the service, with no conditions. The client keeps its polite rules (read-only, at most 1 request per second, cache, STOP) and identifies itself honestly (`deweloperuch-mcp/<version> (+repository URL)`); see [decisions.md](decisions.md) D9 and D18 | — |
| U2 | ~~Technology stack~~: **resolved 2026-10-09: Python** (decisions.md D8) | Repo foundation |
| U3 | ~~MCP operating mode~~: **resolved 2026-10-10: stdio only** (decisions.md D11) | Affects caching and rate limiting (shared vs per-user) |

## Technical

| # | P | What | Type | How to check |
|---|---|---|---|---|
| T1 | P1 | Resolving `sale_id` → investment. `sale-events` does not return the investment | gap | Check other channels (e.g. `fetchBatchPriceChartData`). Alternative: require `investment_slug` in `get_offer`, since we always have it from search results |
| T4 | P2 | `filterDistrict` in transactions does not narrow results strictly (results from outside Mokotów?) | [H] | Compare `stats.totalTransactions` with/without the filter, check addresses |
| T5 | P2 | Format of `filterLastTransactionDate` (quarters, "Before 2017") | [H] | Browser network traffic after setting the filter |
| T7 | P2 | Offer-report slug collisions (`D1.1.1.4` vs `D1.11.4`) and how the server resolves them | [W] | Find an investment with colliding names |
| T8 | P2 | **Geocoding address → lat/lng** for valuation. UI /wycena: where does it get coordinates? No external geocoder in the bundles | gap | Network traffic on /wycena after entering an address. Fallback: street lat/lng from `location-search` |
| T9 | P2 | Histogram bucket boundaries (`aligned: true`) | [W] | Read module `84462` in chunk `2438` |
| T10 | P2 | Period and base of `*_change` in `city-transaction-stats` / the county map; whether `avg_*` is a median | [H] | Compare with `monthly-transaction-stats` |
| T11 | P2 | Rate limiting: at what pace do CF/the app respond with 429/a block? Does an honest User-Agent (`deweloperuch-mcp/x.y`) get through? | [H] | Careful test of single requests with a different UA; **no load tests** |
| T13 | P3 | `announcement-stats`: meaning of `blue/green`, `value`; correct `region` for the whole of Poland | gap | Content of the /statystyki/portale-ogloszeniowe page (legend, descriptions) in a browser |
| T14 | P3 | Semantics of `slices` (statistics) and of `priceIncreaseCount`/`priceDecreaseCount` in `filteredStats` (0 while the sums are non-zero, unreliable). `filteredStats`/`citiesStats` otherwise settled [P 2026-10-13], see `pages-rsc.md` | [H] | Comparison with the UI |
| T15 | P3 | Not analyzed: `/kredyty`, calculators (probably no backend data) | — | — |
| T16 | P3 | Verifying traffic in a real browser (DevTools/HAR) as a completeness check of the static analysis, especially map and filter interactions | — | Chrome session with network recording |
| T17 | P3 | Whether `Next-Router-State-Tree` is required for server actions | [H] | Only if we ever use C |
| T29 | P3 | Full list of allowed `perPage` (observed: 10, 25, 50, 100 accepted; 20, 500 → 10) | [H] | A few values, e.g. 30, 75 |
| T30 | P3 | Actual key of `sortBy=last_event_date` (does not match the visible `last_event_date`; maybe `last_change_event_date`) and the untested `investment`, `last_amount_difference(_percent)`, `start_amount_difference` | [H] | One request per value, compare with list fields |
| T31 | P3 | `success: false` in `/api/sale-events`: when it occurs (an unknown ID gives `success: true, saleData: null`; bad/empty `saleId`?) | [H] | 1–2 requests with a bad `saleId` |
| T32 | P3 | `count` in `location-search` for `street` and `city` (is it the number of active offers; in transaction mode, transactions) | [H] | Compare with `total` of the `filterStreet=` list / `/api/cities offerCount` |
| T33 | P3 | Untested offer-list filter values: `filterPriceChange=increase,no_change` and csv, `filterStatus=active`, sentinel `filterPricePerM2=…-999999`, `filterDeveloper`, `filterProject`, `filterStreet`, `filterAnomalies`, `showArchivedInvestments` | [W] | Control requests comparing `total` |
| T34 | P2 | Response for `page` > `totalPages` with a known city (e.g. Kraków, `filterPrice=0-300000`, page M+1): an empty page, clamping to the last page (like `page>20` → 20) or `notFound()` (digest 404; MCP would then say "unknown city")? Test: `tests/e2e/test_live_mcp.py::test_offers_page_past_the_last_one` | [H] | 1 request, check `initialData` and `E` rows |
| T35 | P2 | Whether a district slug (e.g. `mokotow`) as `{city}` gives a 404 digest. Test: `test_offers_district_slug_as_city_is_an_unknown_city` | [H] | 1 request |
| T36 | P2 | Whether the digest `NEXT_HTTP_ERROR_FALLBACK;404` also appears on other RSC pages (investments, details); confirmed on the offer list; the developer page answers 200 without it [P 2026-10-13] | [H] | 1 request per page with an unknown slug |
| T37 | P3 | Whether raw RSC payloads should become a separate sample type in `docs/discovery/samples/` (today they live in `tests/fixtures/rsc/`, while samples are trimmed JSON with an envelope) | [H] | Editorial decision, no requests |
| T38 | P2 | Unknown `citySlug` in `offers/city-sales`, `map/investments`, `monthly-transaction-stats` and `avg-price-trend/city`: 400, 404 or empty? | [H] | 1 request per endpoint |
| T39 | P3 | Developer page with an unknown city but a valid developer: empty list, 200 "not found" or 404? | [H] | 1 request |
| T40 | P2 | Meaning of `excluded` and `isSamePrimaryInvestment` in valuation transactions; do `stats` include excluded ones? | [H] | Find a valuation with `excluded=true`, compare `stats.count` |
| T41 | P3 | How does `standalone-valuation` use fractional `area`? A request for 41.37 m² was accepted, but its estimate matched 41 m² at one point (details below). The general rounding or truncation rule is unknown. | [P] observation; [H] general rule | Further targeted checks only when needed; the client currently warns and preserves the service's figures |
| T42 | P3 | What does `address` change in `standalone-valuation` (results with/without it for the same lat/lng)? | [H] | 2 requests |
| T43 | P2 | Completeness of `map/investments` without `includeArchived`: are investments with no active offers missing? | [H] | Compare with the `inwestycje` list `totalCount` for a city |
| T44 | P2 | Counting window of `map/powiat-stats` `transaction_count` (351,314 for Warsaw vs ~1.0-1.3k/month); related to T10 | [H] | Compare with the sum of `monthly-transaction-stats` |
| T45 | P1 | Market and classification scope of `monthly-transaction-stats` and `avg-price-trend/city`: are primary-market transactions and non-`transakcja` classes (`udzial`, `anomalia_*`, `hurt`, `rzadowa`, `egzekucja`, `bonifikata`) counted? `latestSummary` on the statistics page (Warsaw, 2026-03) had `secondary_count` = `transaction_count` = 1036, `unknown_count` 0 [P 2026-10-09, `page.stats_transactions`]; the same month in `monthly-transaction-stats` is 1,390 on 2026-10-15 (later capture, so partly T46) | [H] | Compare `latestSummary` with the same month of `monthly-transaction-stats` in one series; read the statistics page bundle for the market/classification filter ([P] from code); compare with `transaction-count?city=` with and without `classifications` |
| T46 | P1 | Revision horizon of RCN months: how far back counts still change. Warsaw 2026-04: 29 on 2026-10-13 [P 2026-10-13, CLI] -> 987 on 2026-10-15 [P 2026-10-15, `tests/fixtures/api/monthly_tx_warszawa_20261015.json`]. Same capture: 2026-03 1,390 (1,036 in `latestSummary` on 2026-10-09), 2026-05 22, 2026-06 0 (every measure 0), 2026-07 35 with `med_price_sqm` 33,176 (about twice the months before); 2026-08/09 absent. Quarterly tail [P 2026-10-16, `avg_trend_city_warszawa_20261016.json`]: 2026-Q1 3,721, 2026-Q2 1,034, 2026-Q3 37. Karpacz [P 2026-10-16, `monthly_tx_karpacz_20261016.json`] ends at 2025-12 with no later rows | [W] | `monthly-transaction-stats?citySlug=warszawa` saved as variants on 3 dates a few weeks apart; derive a rule for the "last reliable month" |
| T48 | P2 | Over which classes a building's `avg_amount`/`avg_size`/`avg_price_sqm`/`transactions` (`map/transactions/visible`) and valuation `stats` are computed. Building `cisna` [P 2026-10-15, `tx_visible_cisna_20261015.json`]: 5 `transakcja`, 1 `udzial`, 1 `egzekucja` transactions in 6 units; the counter 5 and the `avg_*` match the 5 regular `transakcja` transactions (`avg_price_sqm` 3,809.76 = summed price / summed area). It does not tell (a) all `transakcja` transactions from (b) units whose last classification (`last_transaction_classification`) is `transakcja` | [H] | A building where a unit has a `transakcja` followed by a later non-`transakcja` event (or the reverse); recompute the means per class set |
| T49 | P2 | Valuation with a small pool: minimum `stats.count` for an estimate, other `radiusLevel` values, widening up to `radiusCeilingM` and `periodMonths`. Cisna (49.2167, 22.3333, 50 m2) [P 2026-10-15, `standalone_val_cisna_20261015.json`]: estimate 202,000 from `stats.count` 2 (2,302 and 5,778 PLN/m2), `radiusKm` 1 = `radiusCeilingM` 1000, `radiusLevel` `okolica`, `periodMonths` 24. The dense-area samples have `sasiedztwo` with `radiusKm` 0.2 | [H] | 2-3 rural points with `probe.py --save`; compare `radiusLevel`, `radiusKm`, `stats.count` |
| T50 | P3 | Valuation with no transactions within the ceiling radius: `estimatedValue` null, 0 or non-2xx? (the golden `valuation_without_an_estimate` assumes null, never observed) | [H] | 1 request at a point with no flats nearby |
| T51 | P3 | Valuation at a point inside the 49.0-54.9 N / 14.1-24.2 E box but outside Poland (e.g. Lviv 49.84/24.03, Kaliningrad 54.71/20.51) | [H] | 1 request |

**T41 observation, 2026-10-16 ([issue #6](https://github.com/MBratkowski/deweloperuch-mcp/issues/6)).** At `lat=50.10841762`, `lng=20.04339151`, requests for `area=41.37` and `area=41` both returned `estimated_value=558666`, `price_per_m2=13626` and `comparables_total=11`. The total equals `13626 × 41`, but this pair alone does not establish how other fractional areas are handled. The Python query serializes the decimal area correctly, and the DTO preserves the service's values. The output's `area_m2` is the requested area (rounded to 0.01 m²); the service does not confirm an effective area. The client retains the upstream total without recomputing it and includes a fractional-area caution in `hint` for CLI and MCP results.

## Resolved

| # | Date | Result | Sample |
|---|---|---|---|
| T2 | 2026-10-10 | Refuted: `perPage=25` accepted (`pagination.perPage: 25`, 25 rows). The allowed set is not {10, 50, 100}; the full list opened as T29 | none (see `pages-rsc.md`) |
| T3 | 2026-10-10 | By default (no `sortBy`) and with an unknown value: ascending by `sale_id`, no error. Confirmed: `amount` (asc, desc), `price_per_sqm`, `size`, `name`, `start_amount_difference_percent`. `last_event_date` accepted, key unclear (T30). The rest [W] (T30) | `page.offers_list.sort_desc` |
| T6 | 2026-10-10 | `filterPriceChange=decrease` works (13324 → 2416, by change from the initial price); `filterStatus=archived` works (11415, all archived); `includeArchived=true` works (24739 = 13324 + 11415); `filterRooms` and `filterFloors` **do not work** on the offer list (total unchanged). Other values: T33 | none (see `pages-rsc.md`) |
| T12 | 2026-10-10 | `city-sales` contains no archived offers (`includeArchived` ignored, Sopot 6/6 `active`); `polska` → `400 Invalid citySlug` (does not work) | `api.city_sales_sopot` |
| T18 (a) | 2026-10-10 | Unknown slug in `map/investments/visible/{slug}`: `404 {"error":"Investment not found"}` | none (non-2xx) |
| T19 (b) | 2026-10-10 | Unknown city on the page `/ceny-ofertowe/{city}/mieszkania`: HTTP 200 RSC without `initialData`, with a `notFound` segment; the client must detect the missing prop | none |
| T20 (c) | 2026-10-10 | Slug alphabet: 166 of 168 slugs in the samples are `[a-z0-9-]`; 2 exceptions (`Metro-Art`, `Forrest`) only in the reports map, a different entity type. Level [W] (observation, not a server test) | (reports-map sample not kept) |
| T21 (d) | 2026-10-10 | District `count` = number of active offers (Mokotów: 1562 = `total` from `filterDistrict`). For streets and cities: T32 | `api.location_search.kinds_limit20` |
| T22 (e) | 2026-10-10 | `limit` honored up to at least 20 (`q=mo&limit=20` → 20 results); `kind` ∈ {`city`, `district`, `street`}; no "more" flag; `q` with 1 character → empty list | `api.location_search.kinds_limit20` |
| T23 (f) | 2026-10-10 | `sortBy=amount&sortOrder=desc` works (descending from 7,820,948) | `page.offers_list.sort_desc` |
| T24 (g) | 2026-10-10 | Partially: unknown `saleId` → `200 {success: true, saleData: null, events: []}`; `success: false` not observed (T31) | none |
| T25 (h) | 2026-10-10 | Sentinels: `filterPrice=0-99999999&filterSize=0-9999` → total 13324 = result without filters. Price/m² (`999999`) untested (T33) | none |
| T26 (i) | 2026-10-10 | RSC pages: `private, max-age=28800, must-revalidate` (no `s-maxage`). `city-sales`: `public, max-age=28800, s-maxage=300, stale-while-revalidate=3600`. `cities`, `sale-events`, `map/investments/visible` (also 404): `max-age=28800` without `s-maxage`. `location-search`: `private, max-age=28800`. The transport needs a default TTL for these | — |
| T27 (j) | 2026-10-10 | `/api/cities`: `page` works; `total` = all matching, `page` = page number, `hasMore` = there are further pages (`limit=2`: page 1 → `hasMore: true`, page 2 → `false`, `total: 4`) | `api.cities_q` (without `hasMore: true`) |
| T28 (`OFFER_EVENT`) | 2026-10-10 | Every asking-price entry, not only the first price (offer 4397: 12 `OFFER_EVENT` events with varying amounts = `total_events`) | `api.sale_events.price_history` |
| T47 | 2026-10-15 | Settled for the observed case: in `city-transaction-stats` exactly one of 2,529 places (`Ignatki-osiedle`, 8 transactions, `price_sqm_change` -100) has `avg_price_sqm`, `avg_size` and `avg_amount` all 0, i.e. no value; `map/powiat-stats` (380 powiats) has none. Whether other zero rows appear later is a monitoring note, not an open question | `tests/fixtures/api/city_tx_stats_20261015.json`, `powiat_stats_20261015.json` |
| T52 | 2026-10-15 | `map/powiat-stats` now lists 380 powiats (369 in the 2026-10-09 sample), the number of Polish powiats; the fewest transactions is 17 | `tests/fixtures/api/powiat_stats_20261015.json` |

## Alternative and supplementary sources

| Source | What it gives | Limitations |
|---|---|---|
| `github.com/deweloperuch/rejestr-cen-nieruchomosci` | Raw RCN data (GML), **CC0 license**, 12 cities (Gdańsk, Gdynia, Katowice, Kraków, Łódź, Łomża, Lublin, Olsztyn, Sopot, Toruń, Warszawa, Wrocław) | Last push 2025-11-08, so the snapshot is older than the service (data up to 2026-08); the GML format needs a parser. Candidate for a second data source |
| GUGiK / Geoportal (RCN) | `transactionId: "PL.PZGIK.…"` with 2026 download dates suggests the service is fed from the national RCN service | [H], not investigated; potential primary source |
