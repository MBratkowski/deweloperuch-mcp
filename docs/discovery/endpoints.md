# Catalog of JSON endpoints (`/api/*`) and server actions

All endpoints: `GET`, same-origin `https://deweloperuch.pl`, no session/cookies, `application/json` response. Status [P] means the endpoint was called and the response saved in `samples/api.<file>.json`. Parameters marked (UI) are sent by the client code; their effect was not always tested separately.

**2.0 redesign (deployed 2026-10-29, build `VDpA73sQ-GRMsEMdmIQtu`, Next.js 15.5.25).** The entries below come from the survey of 2026-10-09 (build `KD_IOP6Grqba7xa86pGVG`); an entry that was re-checked on the 2.0 service carries `[P 2026-10-29]` (live e2e run) or `[P 2026-10-30]` (probe, with a sample) in a `2.0` bullet. What changed:
- 4 paths answer 404: `offers/city-sales`, `monthly-transaction-stats`, `map/powiat-stats` and `investments/{investId}/sale-events` (the last one is replaced by the `ev` field of `map/investments/visible/{slug}`).
- 7 more of the 34 baseline paths are no longer referenced by the 2.0 client; of these, `avg-price-trend/city` and `avg-price-trend/building` still answer 200, the other 5 were not requested. Section 8 lists all 11.
- 14 new paths appear in the client (section 7), none requested yet; 5 existing paths gained fields or parameters (`cities`, `city-districts`, `investments`, `map/investments/visible`, `city-lookup`).
- An unknown route answers with the Next.js HTML 404 page (`text/html`, about 36 KB), not with the JSON `{"error": "..."}` of an application 404.
- Cache headers changed: all 11 JSON responses probed on 2026-10-30 send `public, max-age=28800, s-maxage=N, stale-while-revalidate=M` (N from 300 to 86400, see the entries); on 2026-10-09 several of these endpoints had `max-age=28800` only.
- Sections 7 and 8 are tables, not `` ### `GET /api/...` `` headings, on purpose: `tests/recon_scripts/test_probe_allowlist.py` pairs every such heading with `allowlist.API_PATHS`. Promoting a path from section 7 to a heading and to `API_PATHS` is one change.

Value conventions:
- `citySlug`: ASCII city slug (`warszawa`, `krakow`, `gdansk`, …); `polska` = whole country (only in page routing, not in the API)
- amounts in PLN, areas in m²
- `variant=transactions` switches dictionaries from offers to RCN transactions; `propertyType` for transactions: `flat` (default) | `house` | `both`

---

## 1. Locations and autocomplete

### `GET /api/popular-search-items` [P]
Starting suggestions of the search box.
- Query: `variant` (`transactions`), `propertyType` (`flat`|`house`; only with `variant=transactions`)
- Response: `{ cities: [{name, slug, woj, offerCount}], developers: [{name, slug, offerCount}], investments: [{name, slug, offerCount}] }`
- With `variant=transactions` the `offerCount` field means the **number of transactions**, not offers [P]. The field name does not change.
- Cache: `max-age=28800`. UI source: hero search box (chunks `1936`, `2438`).
- 2.0 [P z kodu 2026-10-30]: the client sends `variant=offers` (an explicit value) and `variant=transactions`, both with `propertyType=both` (chunks `5665`, `3836`, `741`; the start page passes the result as prop `initialPopular {offers, transactions}`). Neither `variant=offers` nor `propertyType=both` was requested, so the effect of both is [H] (T59).
- Sample: `api.popular.json`, `api.popular_tx.json`

### `GET /api/cities?q=&limit=` [P]
- Query: `q` (name fragment), `limit` (UI: 8), `variant`, `propertyType`
- Response: `{ cities: [name], cityMappings: [{city, city_slug, offerCount}], hasMore, total, page }`
- Also returns localities with 0 offers.
- Pagination [P 2026-10-10]: `page` works. `q=krak&limit=2` → `hasMore: true, total: 4, page: 1` (Kraków, Krakowiany); `&page=2` → `hasMore: false, total: 4, page: 2` (Krakulice, Krakuszowice). So `total` = number of all matching localities, `page` = number of the returned page (from 1), `hasMore` = there are further pages. Observation without a separate sample (the existing `api.cities_q` has `hasMore: false`).
- Cache-Control: `max-age=28800` (no `s-maxage`) [P 2026-10-10].
- 2.0 [P 2026-10-30, `api.cities_q.transactions`]: `q=krak&variant=transactions&limit=5` → 200, 434 B, same shape: `cities` (5 names), `cityMappings` (5 rows), `hasMore: true`, `total: 6`, `page: 1`. With `variant=transactions` `offerCount` is the number of transactions (Kraków 248,196) and localities without any are listed with 0 (Krakówek). The transaction dictionary is wider than the offers one: 6 matches for `krak` against 4 on 2026-10-09. The order is alphabetical with Polish collation (`ó` sorts as `o`: Kraków, Krakówek, Krakowiany, Krakówkowice, Krakulice), not by count. Whether `propertyType` changes `offerCount` (flats only, or flats and houses) was not tested [H] (T66).
- 2.0 Cache-Control [P 2026-10-30]: `public, max-age=28800, s-maxage=1800, stale-while-revalidate=86400`, `cf-cache-status: MISS` (was `max-age=28800` only).
- Sample: `api.cities_q.json`, `api.cities_q.transactions.json`

### `GET /api/city-lookup?city=<nazwa|slug>|slug=<slug>[&source=transactions]` [P]
- Normalizes a city name or slug to `{city, city_slug}`.
- 2.0 [P 2026-10-30, `api.city_lookup.slug_transactions`]: `slug=krakow&source=transactions` → 200, 39 B, `{"city": "Kraków", "city_slug": "krakow"}` (name from slug). Cache-Control `public, max-age=28800, s-maxage=86400, stale-while-revalidate=604800`, MISS.
- 2.0 [P z kodu 2026-10-30] (chunks `2432`, `6535`): the client sends `city=<name>` to get a slug and `slug=<slug>` (trimmed, lowercase) to get a name, each with `&source=transactions` for the transaction dictionary, and treats a falsy `city_slug` / `city` in the reply as "not found". The reply for an unknown name or slug was not requested [H].
- Sample: `api.city_lookup.json`, `api.city_lookup.slug_transactions.json`

### `GET /api/location-search?q=&limit=` [P]
- Query: `q`, `limit` (UI: 6), `variant`, `propertyType`
- Response: `{ suggestions: [{kind, city, citySlug, district, street?, count, lat, lng}] }`
- `kind` ∈ {`city`, `district`, `street`} [P 2026-10-10, `api.location_search.kinds_limit20`]. `city` entries have only `kind, city, citySlug?, count, lat, lng` (no `district`/`street`; `district` is sometimes omitted for streets outside districts as well).
- `count`: for a district it is the number of active offers: `count` of Mokotów = 1562 = `pagination.total` of the `filterDistrict=Mokotów` list [P 2026-10-10]. For streets and cities (and in transaction mode) still [W].
- `limit` is honored at least up to 20 (`q=mo&limit=20` → 20 results, mixed kinds, order not by `count`); upper cap unknown. No "more available" flag; a full page does not prove there is more [W]. `q=a` (1 character) → empty list [P 2026-10-10].
- Cache-Control: `private, max-age=28800` [P 2026-10-10].
- 2.0 [P 2026-10-29, live e2e]: still answers 200 for the `search_locations` queries (cities, districts, streets with Polish letters); the shape was not re-sampled.
- Sample: `api.location_search.json`, `api.location_search.kinds_limit20.json`

### `GET /api/city-districts?citySlug=` [P]
- Query: `citySlug`, `variant`, `propertyType`
- Response: `{ districts: [{name, count}] }`, sorted descending by `count`
- 2.0 [P 2026-10-30, `api.city_districts.transactions`]: `citySlug=krakow&variant=transactions` → 200, 1,118 B: `{districts: [{name, slug, count}]}`, 18 districts sorted descending by `count` (Prądnik Biały `pradnik-bialy` 31,851, Podgórze 27,247, Dębniki 25,617 … Wzgórza Krzesławickie `wzgorza-krzeslawickie` 2,740). **New field `slug`** (ASCII, `[a-z0-9-]`, e.g. `lagiewniki-borek-falecki`), absent from the 2026-10-09 sample `api.city_districts`; so a district can now be identified by a slug, not only by its name. The 18 counts sum to 228,754 while `cities?variant=transactions` gives 248,196 for the city, so the scope of `count` is unverified [H].
- 2.0 Cache-Control [P 2026-10-30]: `public, max-age=28800, s-maxage=300, stale-while-revalidate=86400`, `cf-cache-status: HIT`, `age: 59250`.
- 2.0 [P z kodu 2026-10-30] (chunks `5665`, `3836`): the client also calls `citySlug=all&variant=<offers|transactions>` and reads `districtsByCity` (a map of every city's districts, cached 6 h in the client). Not requested; its size is unknown, so treat it as a possible dump until it is measured (T67).
- Sample: `api.city_districts.json`, `api.city_districts.transactions.json`

### `GET /api/investment-streets?q=&limit=&citySlug=` [P]
- Streets with investments (in transaction mode: with RCN buildings [W]).
- Query: `q` (≥2 characters, otherwise no filter), `limit` (UI: 10), `citySlug`, `variant`, `propertyType`
- Response: `{ results: [{name, fullName, citySym, cityName, citySlug, investmentCount}], cityCenter: {lat, lng} }`
- Substring matching (`q=pu` returns "Kacpury 11") [P]
- Sample: `api.investment_streets.json`

### `GET /api/map/city-powiats/{citySlug}` [P]
- Maps a city to RCN counties: `{ powiatIds: [int], primaryPowiatId: int }` (Warsaw → 302, Sopot → 208)
- Cache 24 h. Sample: `api.city_powiats_waw.json`

### `GET /api/building-outline?lat=&lng=[&street=]` [P]
- Building outline: `{ polygon: GeoJSON Polygon }`. Source (OSM?) [H]. Cache 30 days.
- 2.0 [P z kodu 2026-10-30]: not referenced by the 2.0 client (section 8); not requested, live status unknown (T58).
- Sample: `api.building_outline.json`

---

## 2. Developer offers (asking prices)

### `GET /api/developers?q=&limit=` [P]
- Query: `q`, `limit` (UI: 5) and search context: `city`, `minPrice`, `maxPrice`, `minSize`, `maxSize` (UI)
- Response: `{ developers: [{name, slug, offerCount}], hasMore, total, page }`
- 2.0 [P 2026-10-30, `api.developers_q.city`]: `q=atal&city=krakow&limit=5` → 200, 103 B, same shape: one developer, ATAL S.A. (`atal`), `offerCount` 705, `hasMore: false`, `total: 1`, `page: 1`. `city` takes a city slug. For the same developer `offerCount` was 4,265 without `city` on 2026-10-09 (`api.developers_q`, another build and date), so `city` probably scopes the count to that city [W]; a same-day request without `city` was not made (T64).
- 2.0 Cache-Control [P 2026-10-30]: `public, max-age=28800, s-maxage=1800, stale-while-revalidate=86400`, `cf-cache-status: MISS`.
- Sample: `api.developers_q.json`, `api.developers_q.city.json`

### `GET /api/investments?q=&limit=` [P]
- As above. Response: `{ investments: [{name, slug, offerCount}], hasMore, total, page }`
- 2.0 [P 2026-10-30]: every row gained `city`, `city_slug`, `district` (string or `null`) and `powiatId` (integer or `null`; `null` in both samples). `api.investments_q.nowy_targ` (the query of the 2026-10-09 sample, `q=nowy%20targ&limit=5`) → 200, 203 B: one row, Nowy Targówek VI (Warszawa, district Targówek, `offerCount` 21 against 27 on 2026-10-09), `total: 1`. The 2026-10-09 sample also listed Apartamenty Nowy Targ with `offerCount` 0; the 2.0 response does not, so investments without active offers are probably hidden by default [W] (they may also have been removed; T65).
- 2.0 `includeArchived=true` [P 2026-10-30, `api.investments_q.city_archived`]: `q=browar&city=gliwice&includeArchived=true&limit=5` → 200, 213 B: one row (Browar HUGO SCOBEL, `browar-hugo-scobel`, Gliwice, `offerCount` 5) with one more key, `archived: false`. Without the parameter the rows have no `archived` key (the `nowy_targ` sample). Not compared: the same query without `city` or without `includeArchived`, so the effect of `city` (narrowing) and whether `archived: true` rows appear remain open (T65).
- 2.0 Cache-Control [P 2026-10-30]: `public, max-age=28800, s-maxage=1800, stale-while-revalidate=86400`, `cf-cache-status: MISS`.
- Sample: `api.investments_q.json`, `api.investments_q.nowy_targ.json`, `api.investments_q.city_archived.json`

### `GET /api/offers/city-sales/{citySlug}` [P]
- **Dump of all active offers in a city** in compact form.
- Response: `{ citySlug, investments: [{id, slug, developerSlug, status}], sales: [{id, investId, amount, size, priceSqm, status}] }`
- Warsaw: 278 investments, 13,351 offers, 1.3 MB [P]. All `status: active` [P].
- Kraków: 7325 active sales, 143 investments, 67 developers, no null `amount`/`size`/`priceSqm`; the offers list in the same minute reported total 7307 (the dump has 18 more; cause [W], maybe anomalies hidden on the list); `priceSqm` = `amount`/`size` within 0.01 [P 2026-10-13, fixtures `tests/fixtures/api/city_sales_sopot.json`, `city_sales_krakow.json`]. Used internally for aggregates only (D15).
- Archived ones do not appear: `?includeArchived=true` is ignored (Sopot: 6 offers, all `active`, identical with and without the parameter) [P 2026-10-10, no separate sample]. `polska` **does not work**: `HTTP 400 {"error":"Invalid citySlug"}` (refuted: hypothesis that it works; `polska` exists only in page routing) [P 2026-10-10].
- Cache-Control: `public, max-age=28800, s-maxage=300, stale-while-revalidate=3600` [P 2026-10-10]. Used in the layouts of offer lists (`ceny-ofertowe/[city]/mieszkania|inwestycje`).
- **2.0: HTTP 404** [P 2026-10-29, live e2e of the package client: a valid city and an unknown city both give 404, so the route is gone]; absent from all 97 chunks of the 2.0 client read by the scan (section 8). `get_market_statistics` is broken.
- Sample: `api.city_sales_sopot.json`

### `GET /api/map/investments?…` [P]
- Investments with aggregates for the map.
- Query (UI): `citySlug`, `developer` (slug), `project` (investment slug), `price`, `size`, `pricePerM2` (`min-max` ranges), `rooms`, `floor`, `priceChange` (`decrease,increase,no_change`), `includeArchived=true`
- Response: `[{invest_id, latitude, longitude, name, slug, city, city_slug, street, district, status, avg_amount, avg_size, avg_price_sqm, avg_*_archived, avg_*_total, active_offers, total_offers, developer: {developer_id, name, slug}}]`
- 2.0 [P 2026-10-29, live e2e]: `?citySlug=` still answers 200; the shape was not re-sampled.
- Sample: `api.map_investments_sopot.json`

### `GET /api/map/investments/visible/{investmentSlug}` [P]
- **Full investment with all offers** (active and archived).
- Response: investment (`invest_id, developer_id, city, city_slug, street, latitude, longitude, year_construction, name, slug, status, currency, avg_*`, `active_offers, total_offers`) + `developer {developer_id, name, description, website, slug}` + `sale: [{sale_id, invest_id, name, type, status, amount, currency, size, start_amount_difference, start_amount_difference_percent, last_event_date, last_change_event_date, creation_date}]`
- Amounts in `sale[]` are strings, and lat/lng are strings [P].
- Identified by slug alone, no city [P].
- Unknown slug: `HTTP 404 {"error":"Investment not found"}` [P 2026-10-10, no sample because non-2xx]. Cache-Control `max-age=28800` for the 404 as well. 2.0: still 404 for an unknown slug [P 2026-10-29, live e2e].
- **2.0 shape [P 2026-10-30, `api.map_inv_visible.v2` and `api.map_inv_visible.no_v`]**, slug `nowy-czechow` (investment 447, Lublin, 80 active of 127 offers), 200, 50,338 B: the top level has a new key `description` (string, `""` here) after `currency`; every `sale[]` row has two new keys after `creation_date`: `floor` (string; `""` on all 47 archived rows and a floor number as text on all 80 active rows) and `ev` (the price events, below). All other keys and types are as listed above (`sale_id` and `invest_id` integers, `amount`, `size`, `start_amount_difference(_percent)` strings).
- `ev` is the offer's price history in compact form: an array of 4-element arrays `[date "YYYY-MM-DD", amount (integer), event type index, source index]`, ascending by date (346 events in the 127 offers, 2 to 7 per offer). Decoding [P z kodu, module `80026` in chunks `6994` and `4010`]: type 0 `OFFER_EVENT`, 1 `ARCHIVED_EVENT`, 2 `RESTORED_EVENT`; source 0 `ANNOUCMENT_PR`, 1 `ANNOUCMENT`, 2 `ANNOUCMENT_OD`, 3 `DANEGOVPL`, 4 `archive_stale_sales`, 5 `""`. [P 2026-10-30] Offer 33103 (7 events): the decoded `ev` equals `/api/sale-events?saleId=33103` event for event (date, amount, type, source; `api.sale_events.v2`). Indexes seen in this investment: types 0, 1, 2 and sources 0, 1, 4, 5; indexes 2 and 3 (sources `ANNOUCMENT_OD`, `DANEGOVPL`) appear only in the code. Across all 127 offers: the first event's amount = `amount` − `start_amount_difference`, the last event's amount = `amount`, an active offer ends with `[…, 0, 0]` (an `OFFER_EVENT` from `ANNOUCMENT_PR`), an archived one with an `ARCHIVED_EVENT` (`[…, 1, 4]` in 16 offers, `[…, 1, 5]` in 31). `ev` carries no `sale_event_id` and no `event_data`; the client numbers the events 0, 1, … itself (chunk `6994`). The sample keeps 3 elements per array (sample convention), so each `ev` row shows its 4th item as `"... (1 more, 4 total)"`.
- `?v=2` [P 2026-10-30]: the 2.0 client sends `?v=2` for the offer detail (chunk `6994`) and nothing on the map page. A request with and one without `?v=2` return the same body (127 offers, 50,338 B, every field equal, `ev` and `floor` in both). So the version marker changes nothing for this slug [W: probably a cache-busting marker], and the package's adapter, which sends no `v`, already receives `ev`.
- 2.0 Cache-Control [P 2026-10-30]: `public, max-age=28800, s-maxage=3600, stale-while-revalidate=86400`, `cf-cache-status: HIT` (`age` 12,153 with `?v=2`, 58,980 without it: separate cache entries).
- Sample: `api.map_inv_visible.json`, `api.map_inv_visible.v2.json`, `api.map_inv_visible.no_v.json`

### `GET /api/investments/{investId}/sale-events` [P]
- Price event history of **all offers of an investment**: `{ "<sale_id>": [{sale_event_id, event_type, event_data, amount, event_date, source}] }`
- Slow on cache MISS (~3 s). Sample: `api.inv_sale_events.json`
- **2.0: HTTP 404, HTML** [P 2026-10-30, `/api/investments/447/sale-events`, a valid `invest_id` taken from `map/investments/visible/nowy-czechow`]: `text/html`, 36,628 B (the Next.js not-found page; its build comment is `VDpA73sQ_GRMsEMdmIQtu`), `cache-control: private, max-age=28800, must-revalidate`, `cf-cache-status: MISS`; no sample (non-2xx). The body is an HTML page, not the JSON `{"error": ...}` of an application 404, so the route handler is gone, not just this id [W]. The 2.0 client does not call it either: it builds the same map from the `ev` field of `map/investments/visible/{slug}` ([P z kodu], chunk `6994`: `{"<sale_id>": [{sale_event_id: <index>, event_type, event_data: "", amount (string), event_date, source}]}`). `get_investment` with `include_history` is broken.

### `GET /api/sale-events?saleId=` [P]
- History of a single offer: `{ success, saleData: {name, amount, size, currency}, events: [...] }`
- Unknown `saleId` (e.g. 999999999): `HTTP 200 {"success": true, "saleData": null, "events": []}` [P 2026-10-10, no sample]. `success: false` was not observed (none of the inputs used triggered it); its meaning is still [H]. A missing offer is recognized by `saleData: null`.
- Events ascending by `event_date`. `OFFER_EVENT` is **every asking-price entry**, not only the first price: offer 4397 has 12 `OFFER_EVENT` events with 12 different/recurring amounts (1,000,000 → 994,006 → 927,706 → … → 994,012), the count = `total_events` from the list; the first has `source: ANNOUCMENT`, the following `ANNOUCMENT_PR` [P 2026-10-10, `api.sale_events.price_history`]. A price change is a new `OFFER_EVENT` with a new amount.
- Cache-Control: `max-age=28800` (no `s-maxage`) [P 2026-10-10].
- 2.0 [P 2026-10-30, `api.sale_events.v2`]: `saleId=33103` (a restored offer of `nowy-czechow`) → 200, 1,268 B, the same shape: `success: true`, `saleData {name: "B.203", amount, size, currency}`, `events` (7: five `OFFER_EVENT`, one `ARCHIVED_EVENT`, one `RESTORED_EVENT`). `event_data` is the JSON text `{"source":"scraper_pr"}` on `ANNOUCMENT_PR` offer events and `""` otherwise; the `ARCHIVED_EVENT` has `source: ""` and the `RESTORED_EVENT` `source: ANNOUCMENT_PR`. The 2.0 client still calls this route for the price chart (chunk `5721`) and keeps as price points only events with an amount above 0 whose source is `ANNOUCMENT`, `ANNOUCMENT_PR` or `ANNOUCMENT_OD`, plus the `ARCHIVED_EVENT` markers; it drops `RESTORED_EVENT` and collapses consecutive equal amounts [P z kodu].
- 2.0 Cache-Control [P 2026-10-30]: `public, max-age=28800, s-maxage=3600, stale-while-revalidate=86400`, `cf-cache-status: MISS` (was `max-age=28800` only).
- Sample: `api.sale_events.json`, `api.sale_events.price_history.json`, `api.sale_events.v2.json`

### `GET /api/offer-count?…` [P]
- Number of offers matching the filters: `{ count }`
- Query: `city`, `minSize`, `maxSize`, `minPrice`, `maxPrice`, `minPricePerM2`, `maxPricePerM2`, `developer`, `investment`, `includeArchived=true`, `priceChanges` (csv), `filterAnomalies=false`
- `offer-count?city=warszawa` → 13,324, while `price-distribution.total` → 13,351. The difference probably comes from anomalies being filtered out by default [H].
- Sample: `api.offer_count.json`

### `GET /api/price-distribution?mode=amount|perM2&…` [P] / `GET /api/size-distribution?…` [P]
- Histogram: `{ buckets, min, max, distribution: [int], total, mode?, aligned }`
- Query: as for `offer-count` (without `priceChanges`/`filterAnomalies`) + `mode`
- Bucket boundaries are not returned. They have to be reconstructed from `min`, `max`, `buckets`, `aligned` (logic in chunk `2438`, module `84462`). The last bucket is "and more" [H].
- 2.0 [P z kodu 2026-10-30]: `size-distribution` is one of the 11 baseline paths absent from the 2.0 client (section 8); `price-distribution` and `offer-count` are still referenced. None of the three was requested live.
- Sample: `api.price_dist_amount.json`, `api.size_dist.json`

### `GET /api/valuation-pdf?investSlug=&saleId=&city=` [code, not called]
- Generates an "opinion" PDF for an offer. Explicit rate limit: `429` + `Retry-After`. Heavy operation, outside the MVP.

---

## 3. RCN transactions (transaction prices)

### `GET /api/transaction-count?…` [P]
- `{ count }`. Query: `city`, `minSize`, `maxSize`, `minPrice`, `maxPrice`, `minPricePerM2`, `maxPricePerM2`, `rooms` (csv), `floors` (csv), `investRcnId`, `powiatRcnIds` (csv), `filterPolygon`, `classifications`, `filterFlipped=true`, `propertyType` (`house`|`both`; none = flats)
- Sample: `api.tx_count.json`

### `GET /api/transaction-price-distribution?mode=…` [P] / `GET /api/transaction-size-distribution?…` [P]
- Histograms as for offers. Can be slow on MISS (2–5 s).
- 2.0 [P z kodu 2026-10-30]: `transaction-size-distribution` is absent from the 2.0 client (section 8); `transaction-price-distribution` and `transaction-count` are still referenced. Not requested live.

### `GET /api/map/powiat-stats[?type=house|both]` [P]
- All counties (380 on 2026-10-15; 369 in the sample) with aggregates for the whole period: `[{powiat_rcn_id, nazwa, transaction_count, avg_price_sqm, avg_size, avg_amount}]`
- Sample: `api.powiat_stats.json`
- [P 2026-10-15] `tests/fixtures/api/powiat_stats_20261015.json`: 380 powiats (369 in the sample of 2026-10-09; refuted: the list was thought incomplete, T52 resolved), no `avg_*` equal to 0, the fewest transactions is 17.
- **2.0: HTTP 404** [P 2026-10-29, live e2e of the package client]; absent from the 2.0 client (section 8). `rank_locations` over counties is broken. A candidate replacement is `/api/statystyki/powiat-map-stats` (section 7), whose shape is unknown [H] (T59).

### `GET /api/map/powiat-investments/{powiatId}[?type=house]` [P]
- RCN buildings in a county with aggregates: `{powiatId, powiatName, investments: [{id, lat, lng, name, slug, city, citySlug, street, district, avgAmount, avgSize, avgPriceSqm, transactions, lastEventDate}]}`
- Sopot: 1,404 buildings, 419 KB.
- 2.0 [P z kodu 2026-10-30]: absent from the 2.0 client (section 8); not requested, live status unknown (T58).

### `GET /api/map/powiat-sales/{powiatId}[?type=house]` [P]
- **Dump of all transactions in a county**: `{powiatId, powiatName, investments: [...], sales: [{id, investId, priceSqm, amount, size, rooms, floor, type, lastEventDate, isFlipped, classification}]}`
- Sopot: 6,636 transactions, 1.6 MB. Warsaw an estimated ~80 MB [W]. **Do not use in MCP**.
- 2.0 [P z kodu 2026-10-30]: still referenced by the 2.0 client (the statistics page chunk and the `ceny-transakcyjne/[city]/mapa` and `adresy` page chunks); not requested.

### `GET /api/map/transactions/visible/{investRcnSlug}[?type=house]` [P]
- **RCN building with full transaction history**: `{invest_rcn_id, name, city, city_slug, street, slug, latitude, longitude, avg_amount, avg_size, avg_price_sqm, transactions, source_rcn, sale: [{sale_rcn_id, name, amount, amount_sqm, floor, floor_number, rooms, rooms_number, type, currency, size, start_amount_difference(_percent), total_events, creation_date, last_event_date, is_flipped, last_transaction_classification, sale_event_rcn: [{sale_event_rcn_id, amount, amount_sqm, currency, buyerType, sellerType, classification, transactionType, marketType, participation, creation_date, additionalData: {raw RCN record}}]}]}`
- 189 KB for a building with 86 units. Sample: `api.tx_visible.json`
- [P 2026-10-15] `tests/fixtures/api/tx_visible_cisna_20261015.json` (building 152198, `cisna`): `name` and `street` are empty strings (a village without streets); units with an empty `floor` have `floor_number` 0 (so 0 is not a ground floor there). 6 units, 7 transactions: 5 `transakcja`, 1 `udzial` (participation 1/2), 1 `egzekucja`. The counter `transactions` (5), `avg_amount` (274,600) and `avg_size` (72.08) are the means of the 5 `transakcja` transactions, `avg_price_sqm` (3,809.76) is their summed price over their summed area. Whether this is "all `transakcja` transactions" or "units whose last classification is `transakcja`" is open (T48) [H].
- 2.0 [P 2026-10-29, live e2e]: still answers 200 (`get_building` tests passed); the shape was not re-sampled.

### `GET /api/sale-events-rcn/batch?ids=<sale_rcn_id,…>` [P]
- Unit price history: `{ "<id>": [{amount, creation_date}] }`
- Sample: `api.rcn_batch.json`

---

## 4. Statistics

### `GET /api/monthly-transaction-stats?propertyType=&citySlug=|powiatRcnId=|street=` [P]
- Monthly transaction aggregates: `{ scope: {label}, data: [{month, transaction_count, med_price_sqm, avg_price_sqm, med_size, avg_size, med_amount, avg_amount}] }`
- `propertyType`: `mieszkania` [P], `domy` [H]
- The latest months have few transactions (RCN feed lag): `2026-07` has 2 transactions [P]
- Months without transactions (2026-05, 2026-06, Warsaw) return all fields 0 (count, median/avg price per m², median area, median price); 2026-04 had 29 transactions (the RCN lag). The client treats 0 as missing [P 2026-10-13, live e2e run].
- [P 2026-10-15] `tests/fixtures/api/monthly_tx_warszawa_20261015.json`: 67 months 2021-01..2026-07, `scope.label` `city`. Tail: 2026-03 1,390, 2026-04 987 (29 on 2026-10-13), 2026-05 22, 2026-06 0 (every measure 0), 2026-07 35 with `med_price_sqm` 33,176 (about twice the months before); 2026-08 and 2026-09 are absent. Revision horizon: T46 [W].
- [P 2026-10-16] `tests/fixtures/api/monthly_tx_karpacz_20261016.json`: a small town has 60 months 2021-01..2025-12, i.e. no rows after the last month with data; median 1 transaction a month, 26 months with 0 (every measure 0), at most 7.
- **2.0: HTTP 404** [P 2026-10-29, live e2e: `?propertyType=mieszkania&citySlug=warszawa`]; absent from the 2.0 client (section 8). `get_transaction_statistics` over months is broken. The monthly series now sits in the statistics page props (`view.monthly`, 118 rows for Warsaw, on `/statystyki/{city}/transakcje`, see [pages-rsc.md](pages-rsc.md)).
- Sample: `api.monthly_tx.json`

### `GET /api/statystyki/powiat-price-trend?powiatId=` [P]
- Quarterly: `[{quarter, med_price_sqm, trimmed_avg_price_sqm, avg_35_60_price_sqm, transaction_count}]`
- 2.0 [P z kodu 2026-10-30]: absent from the 2.0 client (section 8); not requested, live status unknown (T58).
- Sample: `api.powiat_trend_208.json`

### `GET /api/avg-price-trend/city/{citySlug}[?type=house[&metric=plot]]` [P]
- Quarterly: `{ data: [{period, avgPriceSqm, count}], scope: "city", scopeName }`
- [P 2026-10-16] `tests/fixtures/api/avg_trend_city_warszawa_20261016.json`: `scope` `city`, `scopeName` null, 39 quarters 2017-Q1..2026-Q3. Tail: 2025-Q3 3,902, 2025-Q4 3,605, 2026-Q1 3,721, 2026-Q2 1,034, 2026-Q3 37 with `avgPriceSqm` 33,176 (the same outlier as monthly 2026-07). Each quarter's `count` is about 2% above the sum of its months in `monthly-transaction-stats` (2026-Q1 3,721 vs 3,643) [P]; the cause is unknown [H].
- **2.0: still served, though the 2.0 client no longer calls it** [P 2026-10-30, `api.avg_trend_city.krakow`, `api.avg_trend_city.house_plot`]. `krakow` → 200, 2,180 B: `{data, scope: "city", scopeName: null}`, 40 contiguous quarters 2017-Q1 (6,002 PLN/m², 1,036 transactions) .. 2026-Q3 (15,027; 1,431) and 2026-Q4 (16,184; 4 transactions, the quarter in progress on 2026-10-30). `type=house&metric=plot` → 200, 1,932 B, the same envelope, 37 quarters 2017-Q1 (1,342; 23) .. 2026-Q2 (2,559; 53), with 2021-Q3 absent (a quarter without data is left out, not zero-filled), at least 1 transaction a quarter; 2026-Q3 and 2026-Q4 are not there yet, so the house series lags the flat one by two quarters. Cache-Control `public, max-age=28800, s-maxage=86400, stale-while-revalidate=604800` (`HIT`, `age` 21,101, for flats; `EXPIRED` for the house series).
- **`avgPriceSqm` is a median, not a mean** [P 2026-10-30, comparison of two responses of Warsaw]: against the 2.0 statistics page `/statystyki/warszawa/transakcje` (saved scan page, prop `priceChange.points[]` `{period, n, medSqm, avgSqm, …}`) and the fixture `tests/fixtures/api/avg_trend_city_warszawa_20261016.json`, in the 36 quarters 2017-Q1..2025-Q4 where both counts agree `avgPriceSqm` lies within 2.41 PLN/m² of `medSqm` (identical after rounding in 27), while the closest `avgSqm` is 165 PLN/m² away. Refuted: the reading of `avgPriceSqm` as a mean, which `city_trend_dto.py` still makes ([W] in its comment) and `building_trend_dto.py` makes for the building trend (the building endpoint was not compared).
- The last three Warsaw quarters differ between the fixture (2026-10-16: 2026-Q1 3,721, Q2 1,034, Q3 37) and the 2.0 page (2026-10-30: 3,150, 6, 0), while the page's own monthly series (`view.monthly`) sums to 3,641, 1,008 and 35 and agrees with the monthly fixture of 2026-10-15 within 2: the endpoint's recent quarters may no longer match the figures the 2.0 page shows (T46).
- Sample: `api.avg_trend_city.json`, `api.avg_trend_city.krakow.json`, `api.avg_trend_city.house_plot.json`

### `GET /api/avg-price-trend/building/{investRcnId}[?type=house[&metric=plot]]` [P]
- Trend for the building's neighborhood: `{ data: [...], radiusKm: 1 }`. Requires a **numeric** `invest_rcn_id`; a slug gives `400 {"error":"Valid investRcnId is required"}` [P].
- Sample: `api.avg_trend_building.json`
- [P 2026-10-15] `tests/fixtures/api/avg_trend_building_152198_20261015.json`: building 152198 (Cisna) gives 200 `{"data":[],"radiusKm":0}`, so a building with no neighbourhood trend is an empty `data` and a radius of 0, not an error.
- **2.0: still served, though absent from the 2.0 client** [P 2026-10-29, live e2e: 200 for building 1354 and for 152198; `get_building` tests passed]. Section 8.

### `GET /api/city-transaction-stats` [P]
- City ranking (2,448): `[{city, city_slug, transaction_count, avg_price_sqm, avg_size, avg_amount, transaction_count_change, price_sqm_change, avg_size_change, amount_change}]`
- The aggregation period and the base of `*_change` are unknown [H]. `avg_price_sqm`=16413 for Warsaw is nearly equal to the median 16414 from the statistics map, so the field may contain a median despite its name [H].
- Warsaw `transaction_count` 3606 here vs 351,314 in `map/powiat-stats` (powiat 302); monthly stats give ~1.0-1.3k per month, so the city figure looks like about a quarter and the powiat figure like the whole RCN history; the powiat price seems to come from a different window than its count [W 2026-10-13] (T10 stays open).
- 548 KB, cache 24 h. Sample: `api.city_tx_stats.json`
- 2.0 [P 2026-10-29, live e2e]: still answers 200 (the city ranking tests of `rank_locations` passed) and the 2.0 client still calls it (chunk `741`). The 2.0 ranking page `/ceny-transakcyjne/polska/miasta` carries rows of the same fields as prop `cities` (Warsaw there: `transaction_count` 386,990, `avg_price_sqm` 16,413, `transaction_count_change` null, `price_sqm_change` -2.9) [P 2026-10-30, saved scan page].
- [P 2026-10-15] `tests/fixtures/api/city_tx_stats_20261015.json`: 2,529 places (2,448 in the earlier sample). `avg_price_sqm` and `avg_amount` are always integers, `avg_size` is fractional in 2,234 rows. Exactly one row (`Ignatki-osiedle`, 8 transactions) has `avg_price_sqm`, `avg_size` and `avg_amount` all 0: a zero means no value (T47 resolved); no `null`, empty or negative `avg_*`. 1,628 places have at most 2 transactions, 258 at least 20, 108 at least 50, so a price ranking needs a minimum count.

### `GET /api/announcement-stats?region=&propertyType=` [P]
- Daily series from listing portals: `{ blueRent, blueSell, greenRent, greenSell: [{date: "<epoch ms as string>", value}] }`
- `region`: city slug (e.g. `warszawa`), `top-6` [W from links]. `polska` returns empty arrays [P].
- `propertyType`: `mieszkania` [P], `domy`, `dzialki` [W, mapped to "plots" in the UI]
- Meaning of "blue/green" (two portals?) and `value` (number of listings? median price?) [H]
- 2.0 [P z kodu 2026-10-30]: still referenced by the 2.0 client (chunk `1519` and the old page chunk `app/statystyki/portale-ogloszeniowe/[property_type]/[region]`); the page moved to `/statystyki/{location}/portale-ogloszeniowe` (308 for `polska`, see [pages-rsc.md](pages-rsc.md)). Not requested.
- Sample: `api.ann_waw.json`

---

## 5. Valuation

### `GET /api/standalone-valuation?area=&lat=&lng=[&address=]` [P]
- Comparative valuation based on RCN transactions within a radius.
- Response: `{ estimatedValue, estimatedPricePerSqm, latitude, longitude, area, generatedAt, radiusKm, periodMonths, radiusLevel, areaElasticity, trendMonthlyPct, buildingTransactionCount, stats: {averagePricePerSqm, medianPricePerSqm, minPricePerSqm, maxPricePerSqm, count}, transactions: [{address, unitNumber, area, pricePerSqm, totalPrice, date, floor, distance, latitude, longitude, marketType, isSamePrimaryInvestment, saleRcnId, investRcnSlug, investRcnCitySlug, excluded}], buildings: [...], estimationContext: {pool, …}, radiusPool: [...], radiusCeilingM }`
- 180 KB, mostly `radiusPool` (279 entries). To MCP we pass only the result and the top comparables.
- `radiusLevel`: `sasiedztwo` and `okolica` [P 2026-10-15]; other levels [H]
- [P 2026-10-15] `radiusCeilingM` is 1000 in all three captures (`tests/fixtures/api/standalone_val_cisna_20261015.json`, `api.standalone_val`, `page.offer_report`); its meaning (the widest radius the service will try) is [W]. `radiusLevel` values seen: `sasiedztwo` (`radiusKm` 0.2, dense areas) and `okolica` (Cisna, 49.2167/22.3333, 50 m2: `radiusKm` 1 = the ceiling, `periodMonths` 24, `stats.count` 2, estimate 202,000 from 2,302 and 5,778 PLN/m2, both `excluded: false`, both in building `cisna` with an empty `address`). Small-pool behaviour: T49.
- The server action `fetchStandaloneValuation` gives an identical result [P]
- `distance` is rounded to the nearest 50 m (rawDistance 42 -> 50; 93.5 and 119.8 -> 100; 152 and 165 -> 150); `stats.count` == number of `transactions` == `estimationContext.pool` (9/9/9 and 26/26/26); no transaction with `excluded=true` in the samples [P 2026-10-13, samples `api.standalone_val` and `page.offer_report`].
- 2.0 [P 2026-10-29, live e2e]: still answers 200 (the valuation tests of `estimate_property_value` passed); the shape was not re-sampled. The investment report page `…/{investmentSlug}/raport-inwestycji` still embeds the same structure as its prop `data` (`transactions`, `stats`, `estimatedValue`, `radiusKm`, `radiusLevel`, `buildings`, `estimationContext`) [P 2026-10-30, saved scan page].
- Sample: `api.standalone_val.json`

---

## 6. Server actions (call shape)

Server actions are listed for completeness. The project does not call them (read data is available through `GET`); write actions (`createSaleRcnReport`, `createInvestmentAction`, anything behind Turnstile) exist in the client and are never used.

2.0 [P z kodu 2026-10-30] (scan of 98 of at least 146 chunks, 4 actions found; the call shape `createServerReference(id, callServer, void 0, findSourceMapURL, "name")` is unchanged):
- Kept: `fetchCompetitorInvestment`, `searchCompetitorInvestments` (chunk `2712`).
- New: `fetchOfferPriceSqmSeriesFiltered` (chunk `1519`), `reverseGeocodeForClient` (chunk `6535`, probably the successor of `reverseGeocodeAddress` [W]).
- Not found in the 97 new chunks that were read (8 of the 10 baseline names): `createInvestmentAction`, `createSaleRcnReport` (both write actions; the report form is gone, its pages answer 410), `fetchDeveloperAbuse`, `fetchDevelopers`, `fetchInvestments`, `fetchStandaloneValuation`, `fetchBatchPriceChartData`, `reverseGeocodeAddress`. The scan is incomplete (48 chunks unread: 38 lazy ones and 10 `@tytul` route chunks), so a name may still live in an unread chunk (T62).
- No tool calls a server action (D1); nothing here was requested.

```
POST /<any page, e.g. /wycena>
Accept: text/x-component
Content-Type: text/plain;charset=UTF-8
Next-Action: <40+ hex characters, taken from the JS chunks>
Next-Router-State-Tree: <URL-encoded router tree JSON>   # sent by the UI; whether required: [H]
Body: [ {arguments} ]

-> 200 text/x-component
0:{"a":"$@1","f":"","b":"<buildId>"}
1:<JSON result>
```

Action IDs change with each deploy; `recon/scan_bundles.py` lists the current ones for the current build (`VDpA73sQ-GRMsEMdmIQtu` since 2026-10-29; `KD_IOP6Grqba7xa86pGVG` before).

---

## 7. New paths in the 2.0 client (not requested, not on the allowlist)

Found by the bundle scan of 2026-10-30 [P z kodu]. All are plain GET requests (`fetch` calls, or image and tile URLs) used to render pages. "read" = a GET that returns data; "dump (D5)" = by its name a bulk transaction dump, which the package never requests. None of them was requested live, so the shapes below are what the client code reads, not what the server sends. To enable a probe, the coder adds the path to `allowlist.API_PATHS` (or `DUMP_PATHS`) and promotes it to a `` ### `GET /api/...` `` heading above in the same change (T59).

| Path | Client evidence | Call shape and what the client reads | Class |
|---|---|---|---|
| `/api/city-search-counts` | chunks `5665`, `3836` (search box) | no query; JSON; client cache 30 min | read |
| `/api/map/tx-cities` | chunk `9796`, statistics page chunk | no query; JSON "tx city index" (query key `tx-city-index`), client cache 30 min; size unknown | read (whole-country index) |
| `/api/invest-offer-sparklines?ids=<id,id,…>` | chunk `3216` | csv of investment ids; JSON object keyed by id, each value an array of `[date, value]` pairs | read |
| `/api/sale-sparklines?ids=<id,id,…>` | chunks `4010`, `6335`, `app/start` | csv of sale ids, at most 48 per request (client batches); JSON object keyed by id, each value an array of `[date, amount, event type index]` triples (the index of `ev`, see `map/investments/visible`) | read |
| `/api/map/offer-lifecycle/{x}` | statistics page chunk | `x` comes from the page filters and looks like a location slug rather than an id [W]; client cache 6 h | read |
| `/api/map/offer-snapshot/{location}` | statistics page chunk | `location` is the page's location slug, not requested for `polska`; client cache 6 h | read |
| `/api/statystyki/city-change-stats` | statistics page chunk | no query; reads `quarterStart` and `cities[]` (rows with an `o` flag) | read |
| `/api/statystyki/powiat-map-stats` | statistics page chunk | no query; reads `quarterStart` and `own` | read (candidate replacement of `map/powiat-stats` [H]) |
| `/api/transaction-price-scale?<filters>` | statistics page chunk | the query string is built from the page filters | read |
| `/api/statystyki/raw-transactions?typ=<mieszkania\|domy>[&powiat=<id>][&miasto=<slug>][&dzielnica=<name>]` | chunk `6760` (module `65688`); the transactions page passes the URL as prop `rawUrl` | client validation: `typ` mieszkania or domy; `powiat` 1–999999; `miasto` `[a-z0-9-]{1,80}`; `dzielnica` 1–80 characters and only with `miasto`; `miasto` or `powiat` required. Example from the page: `typ=mieszkania&powiat=302&miasto=warszawa` [P 2026-10-30, saved scan page] | **dump (D5)** by name: every transaction of the city, replacing the old `rawTransactions` prop |
| `/api/statystyki/str/polska` | chunk `1519` | no query; client cache 1 h. `str` is probably short-term rental: statistics pages list a `najem-krotkoterminowy` section per district [W] | read |
| `/api/statystyki/str/powiat/{powiatId}` | chunk `1519` | a powiat id (an integer [W]); reads `p` (array) and `snapshots` (array) | read |
| `/api/map/thumb/{investId}?v=<3\|7\|9>[&size=lg][&src=<source>]` | chunks `3216`, `4021`, `app/start` | image URL (`v=7` investments, `v=9` with `&src=`, `v=3&size=lg`); binary | read (image, not for the allowlist) |
| `/api/map/orto/1/{z}/{x}/{y}` | chunk `8893` | tile URL template: 512 px tiles, zoom 8–18, bounds 14.07, 48.98, 24.16, 54.86; binary | read (map tiles, not for the allowlist) |

New query shapes on known paths:
- `GET /api/city-districts?citySlug=all&variant=<offers|transactions>` → `districtsByCity` [P z kodu]; not requested (T67).
- `GET /api/popular-search-items?variant=<offers|transactions>&propertyType=both` [P z kodu]; not requested (T59).
- Settled live on 2026-10-30: `map/investments/visible/{slug}?v=2` (a no-op, `ev` also without it), `city-lookup?slug=` (name from slug), `cities?variant=transactions`, `city-districts?…&variant=transactions` (districts have a `slug`), `investments?…&city=&includeArchived=true`, `developers?…&city=`, `avg-price-trend/city/{slug}?type=house&metric=plot`: see the entries above.

---

## 8. Removed or not used by the 2.0 client

The 34 baseline paths of 2026-10-09 against the 97 chunks of the 2.0 build that the scan of 2026-10-30 read (98 of at least 146; the 48 unread are 38 lazy chunks and 10 `@tytul` route chunks, so a path may still live in one of them, T62): 11 are not referenced any more, each string is still in the old chunks and no shape of it appears in the new ones [P 2026-10-30, scan and grep]. "Absent from the client" is not "removed from the server": two of the 11 still answer 200.

| Path | Live status | Tool affected |
|---|---|---|
| `/api/offers/city-sales/{citySlug}` | **404** [P 2026-10-29, live e2e; a valid and an unknown city] | `get_market_statistics` |
| `/api/monthly-transaction-stats` | **404** [P 2026-10-29, live e2e; `propertyType=mieszkania&citySlug=warszawa`] | `get_transaction_statistics` (months) |
| `/api/map/powiat-stats` | **404** [P 2026-10-29, live e2e] | `rank_locations` (powiats) |
| `/api/investments/{investId}/sale-events` | **404, HTML page** [P 2026-10-30, `invest_id` 447] | `get_investment` (`include_history`) |
| `/api/avg-price-trend/city/{citySlug}` | **200** [P 2026-10-30, `krakow`; `type=house&metric=plot`] | `get_transaction_statistics` (quarters) |
| `/api/avg-price-trend/building/{investRcnId}` | **200** [P 2026-10-29, live e2e; 1354 and 152198] | `get_building` (neighbourhood trend) |
| `/api/building-outline` | not requested | none |
| `/api/map/powiat-investments/{powiatId}` | not requested | none |
| `/api/statystyki/powiat-price-trend` | not requested | none |
| `/api/size-distribution` | not requested | none |
| `/api/transaction-size-distribution` | not requested | none |

What replaced them in the 2.0 client [P z kodu 2026-10-30]: the offer price history is the `ev` field of `map/investments/visible/{slug}`; offer-market aggregates, monthly transaction series and county statistics now come from the page props of `/statystyki/{location}/…` (see [pages-rsc.md](pages-rsc.md)) and from the new `/api/statystyki/*` and `/api/map/tx-cities` paths of section 7. Whether those replacements fit the tools' needs is open (T59).
