# Catalog of JSON endpoints (`/api/*`) and server actions

All endpoints: `GET`, same-origin `https://deweloperuch.pl`, no session/cookies, `application/json` response. Status [P] means the endpoint was called and the response saved in `samples/api.<file>.json`. Parameters marked (UI) are sent by the client code; their effect was not always tested separately.

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
- Sample: `api.popular.json`, `api.popular_tx.json`

### `GET /api/cities?q=&limit=` [P]
- Query: `q` (name fragment), `limit` (UI: 8), `variant`, `propertyType`
- Response: `{ cities: [name], cityMappings: [{city, city_slug, offerCount}], hasMore, total, page }`
- Also returns localities with 0 offers.
- Pagination [P 2026-10-10]: `page` works. `q=krak&limit=2` → `hasMore: true, total: 4, page: 1` (Kraków, Krakowiany); `&page=2` → `hasMore: false, total: 4, page: 2` (Krakulice, Krakuszowice). So `total` = number of all matching localities, `page` = number of the returned page (from 1), `hasMore` = there are further pages. Observation without a separate sample (the existing `api.cities_q` has `hasMore: false`).
- Cache-Control: `max-age=28800` (no `s-maxage`) [P 2026-10-10].
- Sample: `api.cities_q.json`

### `GET /api/city-lookup?city=<nazwa|slug>[&source=transactions]` [P]
- Normalizes a city name or slug to `{city, city_slug}`.
- Sample: `api.city_lookup.json`

### `GET /api/location-search?q=&limit=` [P]
- Query: `q`, `limit` (UI: 6), `variant`, `propertyType`
- Response: `{ suggestions: [{kind, city, citySlug, district, street?, count, lat, lng}] }`
- `kind` ∈ {`city`, `district`, `street`} [P 2026-10-10, `api.location_search.kinds_limit20`]. `city` entries have only `kind, city, citySlug?, count, lat, lng` (no `district`/`street`; `district` is sometimes omitted for streets outside districts as well).
- `count`: for a district it is the number of active offers: `count` of Mokotów = 1562 = `pagination.total` of the `filterDistrict=Mokotów` list [P 2026-10-10]. For streets and cities (and in transaction mode) still [W].
- `limit` is honored at least up to 20 (`q=mo&limit=20` → 20 results, mixed kinds, order not by `count`); upper cap unknown. No "more available" flag; a full page does not prove there is more [W]. `q=a` (1 character) → empty list [P 2026-10-10].
- Cache-Control: `private, max-age=28800` [P 2026-10-10].
- Sample: `api.location_search.json`, `api.location_search.kinds_limit20.json`

### `GET /api/city-districts?citySlug=` [P]
- Query: `citySlug`, `variant`, `propertyType`
- Response: `{ districts: [{name, count}] }`, sorted descending by `count`
- Sample: `api.city_districts.json`

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
- Sample: `api.building_outline.json`

---

## 2. Developer offers (asking prices)

### `GET /api/developers?q=&limit=` [P]
- Query: `q`, `limit` (UI: 5) and search context: `city`, `minPrice`, `maxPrice`, `minSize`, `maxSize` (UI)
- Response: `{ developers: [{name, slug, offerCount}], hasMore, total, page }`
- Sample: `api.developers_q.json`

### `GET /api/investments?q=&limit=` [P]
- As above. Response: `{ investments: [{name, slug, offerCount}], hasMore, total, page }`
- Sample: `api.investments_q.json`

### `GET /api/offers/city-sales/{citySlug}` [P]
- **Dump of all active offers in a city** in compact form.
- Response: `{ citySlug, investments: [{id, slug, developerSlug, status}], sales: [{id, investId, amount, size, priceSqm, status}] }`
- Warsaw: 278 investments, 13,351 offers, 1.3 MB [P]. All `status: active` [P].
- Kraków: 7325 active sales, 143 investments, 67 developers, no null `amount`/`size`/`priceSqm`; the offers list in the same minute reported total 7307 (the dump has 18 more; cause [W], maybe anomalies hidden on the list); `priceSqm` = `amount`/`size` within 0.01 [P 2026-10-13, fixtures `tests/fixtures/api/city_sales_sopot.json`, `city_sales_krakow.json`]. Used internally for aggregates only (D15).
- Archived ones do not appear: `?includeArchived=true` is ignored (Sopot: 6 offers, all `active`, identical with and without the parameter) [P 2026-10-10, no separate sample]. `polska` **does not work**: `HTTP 400 {"error":"Invalid citySlug"}` (refuted: hypothesis that it works; `polska` exists only in page routing) [P 2026-10-10].
- Cache-Control: `public, max-age=28800, s-maxage=300, stale-while-revalidate=3600` [P 2026-10-10]. Used in the layouts of offer lists (`ceny-ofertowe/[city]/mieszkania|inwestycje`).
- Sample: `api.city_sales_sopot.json`

### `GET /api/map/offer-snapshot/{citySlug}` [P 2026-10-30]
- The 2.0 successor of `/api/offers/city-sales/{citySlug}` (which answers 404 for every city since 2026-10-29): every active offer of a city, compact. Used by `get_market_statistics` for aggregates only (D15).
- Response: `{ citySlug, asOf: "YYYY-MM-DD", investments: [{id, slug, name, street, lat, lng, district, developerId, developer, developerSlug}], sales: [[id, investId, status, amount, priceSqm, size, startAmountDifference]] }`.
- Wrocław [P 2026-10-30]: 261,340 B, 110 investments, 5,836 rows; status 0 in every row; `priceSqm` = `amount`/`size` in every row; medians 14,600 PLN/m² and 50.04 m², Develia 818 offers, the same as the summary of `/statystyki/wroclaw/oferty`.
- Unknown city: `HTTP 404 {"error":"Unknown city"}` (JSON) [P 2026-10-30, `nieistniejace-miasto`].
- Cache-Control: `public, max-age=172800, s-maxage=3600, stale-while-revalidate=86400` [P 2026-10-30].
- Sample: `api.offer_snapshot_wroclaw.json`

### `GET /api/map/investments?…` [P]
- Investments with aggregates for the map.
- Query (UI): `citySlug`, `developer` (slug), `project` (investment slug), `price`, `size`, `pricePerM2` (`min-max` ranges), `rooms`, `floor`, `priceChange` (`decrease,increase,no_change`), `includeArchived=true`
- Response: `[{invest_id, latitude, longitude, name, slug, city, city_slug, street, district, status, avg_amount, avg_size, avg_price_sqm, avg_*_archived, avg_*_total, active_offers, total_offers, developer: {developer_id, name, slug}}]`
- Sample: `api.map_investments_sopot.json`

### `GET /api/map/investments/visible/{investmentSlug}` [P]
- **Full investment with all offers** (active and archived).
- Response: investment (`invest_id, developer_id, city, city_slug, street, latitude, longitude, year_construction, name, slug, status, currency, avg_*`, `active_offers, total_offers`) + `developer {developer_id, name, description, website, slug}` + `sale: [{sale_id, invest_id, name, type, status, amount, currency, size, start_amount_difference, start_amount_difference_percent, last_event_date, last_change_event_date, creation_date}]`
- Amounts in `sale[]` are strings, and lat/lng are strings [P].
- Identified by slug alone, no city [P].
- Unknown slug: `HTTP 404 {"error":"Investment not found"}` [P 2026-10-10, no sample because non-2xx]. Cache-Control `max-age=28800` for the 404 as well.
- Sample: `api.map_inv_visible.json`

### `GET /api/investments/{investId}/sale-events` [P]
- Price event history of **all offers of an investment**: `{ "<sale_id>": [{sale_event_id, event_type, event_data, amount, event_date, source}] }`
- Slow on cache MISS (~3 s). Sample: `api.inv_sale_events.json`

### `GET /api/sale-events?saleId=` [P]
- History of a single offer: `{ success, saleData: {name, amount, size, currency}, events: [...] }`
- Unknown `saleId` (e.g. 999999999): `HTTP 200 {"success": true, "saleData": null, "events": []}` [P 2026-10-10, no sample]. `success: false` was not observed (none of the inputs used triggered it); its meaning is still [H]. A missing offer is recognized by `saleData: null`.
- Events ascending by `event_date`. `OFFER_EVENT` is **every asking-price entry**, not only the first price: offer 4397 has 12 `OFFER_EVENT` events with 12 different/recurring amounts (1,000,000 → 994,006 → 927,706 → … → 994,012), the count = `total_events` from the list; the first has `source: ANNOUCMENT`, the following `ANNOUCMENT_PR` [P 2026-10-10, `api.sale_events.price_history`]. A price change is a new `OFFER_EVENT` with a new amount.
- Cache-Control: `max-age=28800` (no `s-maxage`) [P 2026-10-10].
- Sample: `api.sale_events.json`, `api.sale_events.price_history.json`

### `GET /api/offer-count?…` [P]
- Number of offers matching the filters: `{ count }`
- Query: `city`, `minSize`, `maxSize`, `minPrice`, `maxPrice`, `minPricePerM2`, `maxPricePerM2`, `developer`, `investment`, `includeArchived=true`, `priceChanges` (csv), `filterAnomalies=false`
- `offer-count?city=warszawa` → 13,324, while `price-distribution.total` → 13,351. The difference probably comes from anomalies being filtered out by default [H].
- Sample: `api.offer_count.json`

### `GET /api/price-distribution?mode=amount|perM2&…` [P] / `GET /api/size-distribution?…` [P]
- Histogram: `{ buckets, min, max, distribution: [int], total, mode?, aligned }`
- Query: as for `offer-count` (without `priceChanges`/`filterAnomalies`) + `mode`
- Bucket boundaries are not returned. They have to be reconstructed from `min`, `max`, `buckets`, `aligned` (logic in chunk `2438`, module `84462`). The last bucket is "and more" [H].
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

### `GET /api/map/powiat-stats[?type=house|both]` [P]
- All counties (380 on 2026-10-15; 369 in the sample) with aggregates for the whole period: `[{powiat_rcn_id, nazwa, transaction_count, avg_price_sqm, avg_size, avg_amount}]`
- Sample: `api.powiat_stats.json`
- [P 2026-10-15] `tests/fixtures/api/powiat_stats_20261015.json`: 380 powiats (369 in the sample of 2026-10-09; refuted: the list was thought incomplete, T52 resolved), no `avg_*` equal to 0, the fewest transactions is 17.

### `GET /api/map/powiat-investments/{powiatId}[?type=house]` [P]
- RCN buildings in a county with aggregates: `{powiatId, powiatName, investments: [{id, lat, lng, name, slug, city, citySlug, street, district, avgAmount, avgSize, avgPriceSqm, transactions, lastEventDate}]}`
- Sopot: 1,404 buildings, 419 KB.

### `GET /api/map/powiat-sales/{powiatId}[?type=house]` [P]
- **Dump of all transactions in a county**: `{powiatId, powiatName, investments: [...], sales: [{id, investId, priceSqm, amount, size, rooms, floor, type, lastEventDate, isFlipped, classification}]}`
- Sopot: 6,636 transactions, 1.6 MB. Warsaw an estimated ~80 MB [W]. **Do not use in MCP**.

### `GET /api/map/transactions/visible/{investRcnSlug}[?type=house]` [P]
- **RCN building with full transaction history**: `{invest_rcn_id, name, city, city_slug, street, slug, latitude, longitude, avg_amount, avg_size, avg_price_sqm, transactions, source_rcn, sale: [{sale_rcn_id, name, amount, amount_sqm, floor, floor_number, rooms, rooms_number, type, currency, size, start_amount_difference(_percent), total_events, creation_date, last_event_date, is_flipped, last_transaction_classification, sale_event_rcn: [{sale_event_rcn_id, amount, amount_sqm, currency, buyerType, sellerType, classification, transactionType, marketType, participation, creation_date, additionalData: {raw RCN record}}]}]}`
- 189 KB for a building with 86 units. Sample: `api.tx_visible.json`
- [P 2026-10-15] `tests/fixtures/api/tx_visible_cisna_20261015.json` (building 152198, `cisna`): `name` and `street` are empty strings (a village without streets); units with an empty `floor` have `floor_number` 0 (so 0 is not a ground floor there). 6 units, 7 transactions: 5 `transakcja`, 1 `udzial` (participation 1/2), 1 `egzekucja`. The counter `transactions` (5), `avg_amount` (274,600) and `avg_size` (72.08) are the means of the 5 `transakcja` transactions, `avg_price_sqm` (3,809.76) is their summed price over their summed area. Whether this is "all `transakcja` transactions" or "units whose last classification is `transakcja`" is open (T48) [H].

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
- Sample: `api.monthly_tx.json`

### `GET /api/statystyki/powiat-price-trend?powiatId=` [P]
- Quarterly: `[{quarter, med_price_sqm, trimmed_avg_price_sqm, avg_35_60_price_sqm, transaction_count}]`
- Sample: `api.powiat_trend_208.json`

### `GET /api/avg-price-trend/city/{citySlug}[?type=house[&metric=plot]]` [P]
- Quarterly: `{ data: [{period, avgPriceSqm, count}], scope: "city", scopeName }`
- Sample: `api.avg_trend_city.json`
- [P 2026-10-16] `tests/fixtures/api/avg_trend_city_warszawa_20261016.json`: `scope` `city`, `scopeName` null, 39 quarters 2017-Q1..2026-Q3. Tail: 2025-Q3 3,902, 2025-Q4 3,605, 2026-Q1 3,721, 2026-Q2 1,034, 2026-Q3 37 with `avgPriceSqm` 33,176 (the same outlier as monthly 2026-07). Each quarter's `count` is about 2% above the sum of its months in `monthly-transaction-stats` (2026-Q1 3,721 vs 3,643) [P]; the cause is unknown [H].

### `GET /api/avg-price-trend/building/{investRcnId}[?type=house[&metric=plot]]` [P]
- Trend for the building's neighborhood: `{ data: [...], radiusKm: 1 }`. Requires a **numeric** `invest_rcn_id`; a slug gives `400 {"error":"Valid investRcnId is required"}` [P].
- Sample: `api.avg_trend_building.json`
- [P 2026-10-15] `tests/fixtures/api/avg_trend_building_152198_20261015.json`: building 152198 (Cisna) gives 200 `{"data":[],"radiusKm":0}`, so a building with no neighbourhood trend is an empty `data` and a radius of 0, not an error.

### `GET /api/city-transaction-stats` [P]
- City ranking (2,448): `[{city, city_slug, transaction_count, avg_price_sqm, avg_size, avg_amount, transaction_count_change, price_sqm_change, avg_size_change, amount_change}]`
- The aggregation period and the base of `*_change` are unknown [H]. `avg_price_sqm`=16413 for Warsaw is nearly equal to the median 16414 from the statistics map, so the field may contain a median despite its name [H].
- Warsaw `transaction_count` 3606 here vs 351,314 in `map/powiat-stats` (powiat 302); monthly stats give ~1.0-1.3k per month, so the city figure looks like about a quarter and the powiat figure like the whole RCN history; the powiat price seems to come from a different window than its count [W 2026-10-13] (T10 stays open).
- 548 KB, cache 24 h. Sample: `api.city_tx_stats.json`
- [P 2026-10-15] `tests/fixtures/api/city_tx_stats_20261015.json`: 2,529 places (2,448 in the earlier sample). `avg_price_sqm` and `avg_amount` are always integers, `avg_size` is fractional in 2,234 rows. Exactly one row (`Ignatki-osiedle`, 8 transactions) has `avg_price_sqm`, `avg_size` and `avg_amount` all 0: a zero means no value (T47 resolved); no `null`, empty or negative `avg_*`. 1,628 places have at most 2 transactions, 258 at least 20, 108 at least 50, so a price ranking needs a minimum count.

### `GET /api/announcement-stats?region=&propertyType=` [P]
- Daily series from listing portals: `{ blueRent, blueSell, greenRent, greenSell: [{date: "<epoch ms as string>", value}] }`
- `region`: city slug (e.g. `warszawa`), `top-6` [W from links]. `polska` returns empty arrays [P].
- `propertyType`: `mieszkania` [P], `domy`, `dzialki` [W, mapped to "plots" in the UI]
- Meaning of "blue/green" (two portals?) and `value` (number of listings? median price?) [H]
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
- Sample: `api.standalone_val.json`

---

## 6. Server actions (call shape)

Server actions are listed for completeness. The project does not call them (read data is available through `GET`); write actions (`createSaleRcnReport`, `createInvestmentAction`, anything behind Turnstile) exist in the client and are never used.

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

Action IDs change with each deploy; `recon/scan_bundles.py` lists the current ones for the current build (`KD_IOP6Grqba7xa86pGVG`).
