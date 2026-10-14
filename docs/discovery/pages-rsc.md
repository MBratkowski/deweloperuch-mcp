# SSR (RSC) pages as a data source

Search with filters, sorting and pagination, and most detail views, exist **only** as server-rendered pages. The data is in the props of client components in the RSC payload.

## How to fetch [P]

```
GET https://deweloperuch.pl<path>?<filters>&_rsc=<random token>
RSC: 1
→ 200 text/x-component
```

- Without `_rsc`, Cloudflare returns cached HTML because it ignores `Vary: RSC` [P].
- Alternative: full HTML and decoding `self.__next_f.push([1,"…"])`. Gives the same data but is ~10× larger (942 KB vs 98 KB) [P].
- Props sit in elements `["$","$L<id>",null,{…}]`. References `"$f:props:…"` / `"$8:props:…"` point to previously defined fragments, but the props with list data are inline [P].
- Flight format (rows `<id>:<tag><data>`) [P z kodu, chunk `1517-…js` ReactFlightClient from the scanner cache]:
  - rows with a length in BYTES, **no `\n` after the row**: `<id>:T<hexlen>,<text>`; binary tags `A O o U S s L l G g M m V` (with `T`) work the same way. The next row starts right after the data, so looking for rows only at the start of a line loses them;
  - rows terminated by `\n`: tags `A`–`Z` (incl. `E` error), `#`, `r`, `x`, and a model row without a tag (`<id>:<json>`);
  - hints `:HL…` have an empty id.
  - On the offer list the row with `initialData` comes right after two `T` rows with JSON-LD (`16:T5ed,…` WebPage, `19:T1a27,…` ItemList) [P 2026-10-10, fixture `tests/fixtures/rsc/warszawa_perPage10.rsc`]. Refuted: the old parser (`_JSON_ROW`, rows only at the start of a line) saw no `initialData` there, so `search_offers` did not work on the live service.
- Reference parser: [`src/deweloperuch_mcp/flight.py`](../../src/deweloperuch_mcp/flight.py): `rows()`, `component_props()`, `error_digests()` (RSC) and `flight()` for HTML. `find_json_after(text, "initialData")` stays for `probe --prop`; `recon/flight.py` only re-exports.
- Cache-Control of RSC pages: `private, max-age=28800, must-revalidate` (no `s-maxage`; `cf-cache-status` MISS or HIT with `age`) [P 2026-10-10, samples headers only, no separate sample].
- **Risk**: prop names (`initialData`, `serverPaginationData`, …) are a UI implementation detail and may change without warning [W]. The RSC adapter is isolated and covered by contract tests on samples.

## Common list rules [P]

- `page`: from 1. **Maximum 20 pages**: `page>20` returns page 20 (`pagination.page: 20`) [P].
- `perPage`: `10`, `25`, `50`, `100` accepted [P 2026-10-10: `perPage=25` → `pagination.perPage: 25`, 25 rows; refuted: hypothesis that only {10, 50, 100} are allowed]. `20` and `500` give the default 10 [P]. The full list of allowed values is not known: observed 10, 25, 50, 100 (accepted) and 20, 500 (→ 10) [P]; others [H] (full list: T29).
- Ceiling: **2,000 records per query**. `pagination.total` gives the full count (e.g. 13,324), but `totalPages` is truncated to 20 [P].
- `sortOrder` ∈ {`asc`, `desc`}.
- Ranges: `min-max` (e.g. `filterPrice=500000-700000`). No lower bound → `0-…`; no upper bound → UI sentinel values: price `99999999`, price/m² `999999`, area `9999` [P z kodu]. The server treats `filterPrice=0-99999999&filterSize=0-9999` as no filter: `pagination.total` = 13324 = result without filters (Warsaw) [P 2026-10-10]; the price/m² sentinel (`999999`) was not tested separately [W].
- Lists: comma-separated values (`filterRooms=2,3`).
- `{city}` = city slug or `polska` (whole country) [P].

---

## Asking prices

### `/ceny-ofertowe/{city}/mieszkania`: offer list [P]
| Parameter | Values | Status |
|---|---|---|
| `sortBy` | `amount`, `price_per_sqm`, `size`, `name`, `start_amount_difference_percent` | [P 2026-10-10] `amount` (asc and desc, sample `page.offers_list.sort_desc`), `price_per_sqm`, `size`, `name`, `start_amount_difference_percent`: order matches the value |
| `sortBy` (cont.) | `last_event_date` | [P 2026-10-10] accepted, but the first `asc` rows are not ordered by the `last_event_date` visible in the list (e.g. 2026-10-03 before 2026-09-03); actual key unknown [H] |
| `sortBy` (cont.) | `investment`, `last_amount_difference`, `last_amount_difference_percent`, `start_amount_difference` | [W z kodu], not tested |
| `sortBy` default / unknown | absent or any text (`bogus`) | [P 2026-10-10] identical result: ascending by `sale_id` (database order); an unknown value is silently ignored, no error. Refuted: the default `sortBy` is not `amount` |
| `filterPrice`, `filterPricePerM2`, `filterSize` | `min-max` range | [P] (`filterPrice`, `filterSize`) |
| `filterDeveloper` | developer slug | [W] |
| `filterProject` | investment slug | [W] |
| `filterDistrict` | name (e.g. `Mokotów`, URL-encoded) | [P 2026-10-10] total 1562 = district `count` from `location-search` |
| `filterStreet` | name | [W] |
| `filterPriceChange` | csv of `decrease`, `increase`, `no_change` | [P 2026-10-10] `decrease`: total 13324 → 2416. Refers to the change relative to the initial price (`start_amount_difference*`), not the last event: rows with `last_event_type: PRICE_INCREASE` and negative `start_amount_difference_percent` pass. `increase`/`no_change`, csv values: [W] |
| `filterRooms`, `filterFloors` | csv | [P 2026-10-10] **no effect on the offer list**: `filterRooms=2` and `filterFloors=1` return total 13324 as without a filter (refuted: [W] that they narrow the offer list; offers have no rooms/floor fields). The filters work only in transactions |
| `filterStatus` | `archived` | [P 2026-10-10] `archived` → total 11415, all `status: archived`. `active` and other values not tested [H] |
| `filterAnomalies` | `false` = also show anomalies | [W] |
| `includeArchived` | `true` | [P 2026-10-10] total 13324 → 24739 (= 13324 active + 11415 archived) |
| `showArchivedInvestments` | `true` | [W] |

Props `initialData`:
```json
{ "data": [{ "sale_id", "name", "amount", "start_amount_difference", "start_amount_difference_percent",
             "last_amount_difference", "last_amount_difference_percent", "last_event_type", "total_events",
             "currency", "size", "status", "last_event_date", "last_change_event_date", "creation_date",
             "invest": { "invest_id", "name", "city", "city_slug", "slug",
                         "developer": { "developer_id", "name", "slug" } } }],
  "pagination": { "page", "perPage", "total", "totalPages" } }
```
Unknown city (`/ceny-ofertowe/nieistniejace-miasto/mieszkania`): HTTP **200** `text/x-component` without the `initialData` prop; the indicator is an `E` row with digest `NEXT_HTTP_ERROR_FALLBACK;404` (`{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}`) [P 2026-10-10, fixture `tests/fixtures/rsc/unknown_city_perPage10.rsc`]. Refuted: the `notFound` segment as the indicator (`notFound` is a layout prop on every page). The client must recognize the digest (`error_digests()`), not the HTTP status or the mere absence of `initialData`.
Sample: `page.offers_list.json`, `page.offers_list.filtered.json`, `page.offers_list.sort_desc.json`
`last_event_type` also takes `NEW_OFFER` (an offer without price changes, `total_events: 1`) [P 2026-10-10, `page.offers_list.sort_desc`].

### `/ceny-ofertowe/{city}/inwestycje`: investment list [P]
- `sortBy`: `name`, `active_offers`, `avg_amount`, `avg_size`, `avg_price_sqm` [P], `sum_changes`
- Props: `investments[]` (`invest_id, name, slug, city, city_slug, street, status, avg_amount, avg_size, avg_price_sqm, active_offers, total_offers, sum_start_amount_difference_plus/minus, developer{…}`), `serverPaginationData {currentPage, perPage, totalCount, totalPages, startItem, endItem}`, `initialSortBy`, `initialSortOrder`, `includeArchived`
- Sample: `page.investments_list.json`

### `/ceny-ofertowe/{city}/deweloperzy`: developer list [P]
- `sortBy`: `name`, `projectCount` [P], `totalSales`, `cityCount`, `avgSize`, `avgPrice`, `avgPricePerM2`, `sum_changes`
- Props: `developers[]` (`developer_id, name, slug, projectCount, totalSales, totalOffersCount, cities, cityCount, avgSize, avgPrice, avgPricePerM2, sum_start_amount_difference_plus/minus`), `serverPaginationData`, `filterCity`, `filterName`
- Sample: `page.developers_list.json`

### `/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`: developer profile [P]
- Props: `data {developer, investments[], filteredStats, allCities, allCitiesWithSlugs, citiesStats, allInvestmentNames}`, `sale[]` (lightweight offer list), `data[]` (daily price-change axis: `discountCount, increaseCount, discountValue, increaseValue, cumulative*`)
- Sample: `page.developer.json`
- `{city}` filters the investments to that city; `polska` gives all cities (ATAL: 42 investments, 6587 `sale` rows, ~1.96 MB) [P 2026-10-13, raw fixtures `tests/fixtures/rsc/developer_atal_warszawa.rsc`, `developer_atal_polska.rsc`, consistency tests in the suite].
- Consistency in both fixtures [P 2026-10-13]: `filteredStats.totalProjects` = number of investments; `totalSales` = Σ `active_offers` = active rows in `sale`; Σ `total_offers` = len(`sale`); `totalCities` = number of cities of the investments; `averagePrice` = round(mean price of active offers); `averageSize` = mean area of active offers (±0.01); `avgAmountPerM2` = round(mean of investments' `avg_price_sqm` weighted by `active_offers`); per investment `total_offers`/`active_offers`/`avg_amount`/`avg_size` agree with `sale`. `citiesStats` is identical on the city page and the `polska` page (14 rows) and consistent with the investments; the Warsaw row equals the Warsaw page's `filteredStats`.
- `priceIncreaseCount`/`priceDecreaseCount` are 0 while the sums are non-zero: unreliable, not used (they stay unknown) [P 2026-10-13].
- Unknown developer (`/ceny-ofertowe/warszawa/deweloperzy/nieistniejacy-deweloper`): HTTP 200, **no** `NEXT_HTTP_ERROR_FALLBACK;404` digest (unlike the offer list); h1 "Deweloper nie znaleziony", title "Deweloper nie znaleziony | Deweloperuch" [P 2026-10-13, fixture `developer_unknown_warszawa.rsc`]. The client must detect this by the missing data / title.

### `/ceny-ofertowe/{*}/deweloperzy/{*}/{investmentSlug}`: investment [P]
- **The `{city}` and `{developer}` segments are ignored**. `/ceny-ofertowe/warszawa/deweloperzy/dom-development/nowy-targowek-vi` returns the ATAL investment [P].
- Props: `investments[1]`, `sales[]` (all, including archived), `stats`, `data[]` (price-change axis)
- Contains the same as `GET /api/map/investments/visible/{slug}` plus the change axis. The JSON API is preferred.
- Sample: `page.investment.json`

### `…/{investmentSlug}/raport-mieszkania-{slug(nazwa)}`: offer report [P]
- Slug = `slugify(sale.name)`: Polish characters → ASCII, lowercase, remove everything except `[a-z0-9\s-]`, spaces → `-` [P z kodu]. `D1.1.1.4` → `d1114`. **Collisions possible** (`D1.11.4` also gives `d1114`) [W].
- Props: `property {name, investmentName, developer, address, area, offerPrice, offerPricePerSqm, latitude, longitude}`, `priceHistory[{amount, creation_date}]`, `competitors[]` (offers of similar area nearby: `investmentName, developer, distance, investSlug, developerSlug, sales[{saleId, area, price, pricePerSqm, sizeMatch}]`), `investmentSales[]`, `data` (**RCN valuation** in the `standalone-valuation` format)
- Sample: `page.offer_report.json`

### `…/{investmentSlug}/raport-inwestycji`: investment report [P]
- Like the offer report, but `property` describes the investment average.

### `/ceny-ofertowe/{city}/mapa` [P]
- Props: `initialInvestments[]` (as `/api/map/investments`). The rest through the JSON API.

---

## Transaction prices (RCN)

### `/ceny-transakcyjne/{city}/mieszkania` and `/domy`: transaction list [P]
| Parameter | Values | Status |
|---|---|---|
| `sortBy` | `creation_date` (default, desc), `amount` [P]; others [H] | |
| `filterPrice`, `filterPricePerM2`, `filterSize` | `min-max` range | `filterPrice` [P] |
| `filterRooms` | csv | [P] |
| `filterFloor` / `filterFloors` | csv | [W] |
| `filterDistrict`, `filterStreet` | name | `filterDistrict` accepted [P], but the results do not look strictly limited to the district [H] |
| `filterPowiat` | csv of `powiat_rcn_id` | [W] |
| `filterPolygon` | ? (drawn area) | [H] |
| `filterFlipped` | `true` | [W] |
| `filterClassification` | none = `transakcja`; `anomalie`, `wszystkie` | [W] |
| `filterLastTransactionDate` | quarter (`AQ()` in chunk `2438`) | format [H] |

Props `initialData {data, pagination, stats}` + `initialApiParams` (server-side echo of the filters, useful for verification):
```json
{ "sale_rcn_id", "name": "<EGiB unit id>", "amount", "amount_sqm", "floor", "floor_number", "rooms", "rooms_number",
  "type", "currency", "size", "size_building_area", "size_plot_area", "creation_date",
  "start_amount_difference(_percent)", "last_amount_difference(_percent)", "last_event_date", "total_events",
  "is_flipped", "last_transaction_classification",
  "invest": { "invest_rcn_id", "name", "city", "city_slug", "slug", "source_rcn": { "source_rcn_id", "name" } } }
stats: { averagePrice, averageSize, avgAmountPerM2, minPricePerSqm, maxPricePerSqm, pricePerSqmRange,
         totalTransactions, minPrice, maxPrice, minSize, maxSize }
```
`stats` refers to the **whole filtered set**, not only the page [W], so aggregates are available without paginating.
Sample: `page.transactions_list.json`, `page.transactions_list.params.json`

### `/ceny-transakcyjne/{city}/adresy`: building list [P]
- `sortBy`: `name`, `transactions` (default), `avg_size`, `avg_price_sqm`, `avg_amount`
- Element: `{kind: "flat"|"house", invest_rcn_id, name, street, city, city_slug, avg_amount, avg_size, avg_price_sqm, transactions, slug, building_area, plot_area, source_rcn}`

### `/ceny-transakcyjne/{city}/adresy/{investRcnSlug}` and `/domy/{investRcnSlug}`: building/house [P]
- Props: `investment {invest_id (= invest_rcn_id), latitude, longitude, name, slug, city, city_slug, street, avg_*, active_offers (= number of units)}`, `sales[]` with `events[]` (full `sale_event_rcn` with `additionalData`)
- Houses additionally have `size_usable`, `size_building`, `size_plot` [P]
- `GET /api/map/transactions/visible/{slug}` gives the same, and it is preferred.
- Sample: `page.address.json`, `page.house.json`

### `/ceny-transakcyjne/polska/miasta`: city ranking [P]
- Props: `cities[]` (as `/api/city-transaction-stats`), `teaserCharts[]` (monthly series for top cities)
- Linked only, never fetched by the package, as is `/ceny-transakcyjne/{city}/adresy/{slug}` [P 2026-10-13].

---

## Statistics

### `/statystyki/ceny-transakcyjne/{mieszkania|domy}/{city}` [P]
- Props: `rawTransactions[]` is **all of a city's transactions in short form** (Warsaw: 128,912 rows, HTML 12.9 MB): `{m: "YYYY-MM", s: area, a: amount, ps: price/m², c: classification, rn: rooms, fn: floor}`. Range 2017-01 → current month.
- `latestSummary` (last full month), `slices` (y/y and q/q by cross-sections: area, rooms, …), `topCities`
- URL filters (`filterPrice`, `filterSize`, `filterRooms`, …) are handled client-side on `rawTransactions` [W].
- Too heavy for direct use. Aggregates are better taken from `/api/monthly-transaction-stats`.
- The package only links to this page (a bulk-dump page, see D5 in [decisions.md](../decisions.md)); it is never fetched [P 2026-10-13].

### `/statystyki/ceny-transakcyjne/{type}/{city}/mapa` [P]
- Props: `powiats[]`: `{powiat_rcn_id, powiat_name, transaction_count, med_price_sqm, med_size, med_amount, transaction_count_change, price_sqm_change, amount_change}` (period: last quarter vs previous? [H])

### `/statystyki/statystyki-rzadowe/{location}`: GUS + NBP [P]
- **The only channel** for this data (no JSON API).
- `location`: 69 locations: cities and the aggregates `polska`, `7-miast`, `10-miast`, `9-miast`, `6-miast-bez-warszawy` (prop `sortedLocations` mapped to `gus.teryt` and `nbp.dbName`)
- Sections (`tocItems`): `gus-mieszkania` (quarterly and monthly: completed/started by construction form), `gus-formy-budownictwa`, `gus-srednia-powierzchnia` (yearly), `gus-demografia` (births, deaths, natural change), `gus-wiek` (5-year cohorts F/M), `gus-bezrobocie` (monthly rate), `gus-wynagrodzenia`, `nbp` (quarterly: `pierwotnyOfertowa`, `pierwotnyTransakcyjna`, `wtornyOfertowa`, `wtornyTransakcyjna`)
- Several props are named `data`; they have to be told apart by shape or position in the tree [P]. A fragile spot.
- Cache headers [P 2026-10-13, `polska`]: `private, max-age=28800, must-revalidate`; `cf-cache-status: HIT`; `age: 69574` (above `max-age`). The client caches such replies for 300 s (see D2 in [decisions.md](../decisions.md)).
- Sample: `page.stats_gov.json`

### `/statystyki/portale-ogloszeniowe/{type}/{region}` [P]
- Data loaded client-side from `/api/announcement-stats`. The page contains only a skeleton and the region list.

---

## Other

### `/zglos-dewelopera/mapa-zgloszen` [P]
- Props: `developerAbuseData[]` (105): `{developer_abuse_id, name, slug, developer, website, latitude, longitude, violations[], additionalInfo}`, that is reports of violations of the price transparency act.
- No sample is kept: the reports are user-submitted texts naming companies.
