# SSR (RSC) pages as a data source

Search with filters, sorting and pagination, and most detail views, exist **only** as server-rendered pages. The data is in the props of client components in the RSC payload.

## 2.0 redesign (deployed 2026-10-29): read this first

Every section after this one describes the survey of 2026-10-09 (build `KD_IOP6Grqba7xa86pGVG`). The service now runs build `VDpA73sQ-GRMsEMdmIQtu` (Next.js 15.5.25, still webpack). An old entry that was re-checked carries `[P 2026-10-29]` (live e2e run of the package client) or `[P 2026-10-30]` (the saved HTML of the bundle scan, read offline with `flight.py`, no extra request). The old headings stay as they are because `tests/recon_scripts/test_probe_allowlist.py` pairs them with `allowlist.PAGE_ROUTES`; the 2.0 routes are in the tables below, which that test ignores. Promoting a 2.0 route to a heading and to `PAGE_ROUTES` is one change (T61).

### RSC requests are redirected

Live e2e run of the package client on 2026-10-29 [P 2026-10-29, `tests/e2e/`]: `GET <path>?<filters>&_rsc=<token>` with `RSC: 1` gets no payload.
- With `page=1` in the query: `308` to the same URL without `page=1` and without `_rsc` (the canonical form), e.g. `/ceny-ofertowe/krakow/mieszkania?page=1&perPage=10&_rsc=0db79c39` → `/ceny-ofertowe/krakow/mieszkania?perPage=10`.
- Otherwise (for example `page=2`, a developer page, an unknown developer): `307` to the same URL with an empty `_rsc`, e.g. `…/mieszkania?page=2&perPage=10&_rsc=4d5af205` → `…/mieszkania?page=2&perPage=10&_rsc` (the e2e log prints the target without `=`).
- The package client does not follow redirects, and `probe.py page` refuses a hand-written `_rsc` and does not follow redirects either, so **no RSC payload of the 2.0 service has been seen**. Whether the same URL with an empty `_rsc` returns `text/x-component`, and with which props, is open (T63) [H].
- The 2.0 props below therefore come from the full HTML of the pages (`self.__next_f`), which the bundle scan saved; whether the `RSC: 1` payload has the same props is untested (T57).

### Route changes

| Old route | 2.0 | Evidence |
|---|---|---|
| `/ceny-ofertowe/polska/mieszkania` | `/ceny-ofertowe/polska/miasta` (offers per city, 25 per page) | 308 [P 2026-10-29, e2e] |
| `/statystyki/statystyki-rzadowe/{location}` | `/statystyki/{location}/dane-rzadowe` | 308 [P 2026-10-29, e2e; also for an unknown location] |
| `/statystyki/ceny-transakcyjne/mieszkania/{city}/mapa` | `/statystyki/{city}/transakcje` | 308 for `warszawa` [P 2026-10-29, scanner; `cache-control: public, max-age=28800, s-maxage=86400`, `cf-cache-status: HIT`] |
| `/statystyki/ceny-transakcyjne/{mieszkania\|domy}/{city}` (the page with `rawTransactions`) | not requested; probably also `/statystyki/{city}/transakcje` [H] | T55 (a) |
| `/statystyki/portale-ogloszeniowe/{type}/{region}` | `/statystyki/{region}/portale-ogloszeniowe` | 308 for `mieszkania/polska` [P 2026-10-30, scanner] |
| `/zglos-dewelopera`, `/zglos-dewelopera/mapa-zgloszen` | none | **410**, 1,388 B HTML, `s-maxage=604800` [P 2026-10-30, scanner]: the report form and the reports map are gone |

### Pages that answered 200 on 2026-10-30

[P 2026-10-30, scanner, full HTML]. In bold, routes that are not among the headings below.

| Route | HTML bytes |
|---|---|
| `/` | 364,626 |
| **`/ceny-ofertowe/polska/miasta`** | 154,030 |
| `/ceny-ofertowe/warszawa/mieszkania` | 273,652 |
| `/ceny-ofertowe/warszawa/inwestycje` | 294,966 |
| `/ceny-ofertowe/warszawa/deweloperzy` | 172,709 |
| `/ceny-ofertowe/warszawa/deweloperzy/atal` | 323,264 |
| `/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi` | 439,083 |
| `/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi/raport-inwestycji` | 273,771 |
| `/ceny-ofertowe/warszawa/mapa` | 76,920 |
| `/ceny-transakcyjne/polska/miasta` | 143,216 |
| `/ceny-transakcyjne/warszawa/mieszkania` | 273,937 |
| `/ceny-transakcyjne/warszawa/domy` | 246,636 |
| `/ceny-transakcyjne/warszawa/adresy` | 167,359 |
| `/ceny-transakcyjne/warszawa/adresy/aleja-krakowska-279-warszawa` | 180,884 |
| **`/ceny-transakcyjne/warszawa/mapa`** | 82,882 |
| `/statystyki` | 115,251 |
| **`/statystyki/warszawa/transakcje`** | 354,377 |
| **`/statystyki/warszawa/dane-rzadowe`** | 608,055 |
| **`/statystyki/polska/oferty`** | 324,753 |
| `/wycena` | 104,130 |
| `/kalkulator-oszczedzania` | 97,637 |

The statistics section is `/statystyki/{location}/{section}` with `location` a city slug, `polska` or an aggregate (`7-miast`, `10-miast`, `6-miast-bez-warszawy`), and `section` one of `transakcje`, `oferty`, `dane-rzadowe`, `portale-ogloszeniowe` (known only as the target of a 308, not requested) [P 2026-10-30, links in the saved pages]. All of it is served by one catch-all route chunk (`app/(powierzchnie)/statystyki/[...path]`).

Linked from the props, **not requested** (status unknown): district pages `/ceny-ofertowe/{city}/{district}/{mieszkania|inwestycje|deweloperzy|mapa}`, `/ceny-transakcyjne/{city}/{district}/{mieszkania|domy|adresy|mapa}` and `/statystyki/{city}/{district}/{transakcje|oferty|najem-krotkoterminowy}` (the district is an ASCII slug such as `bemowo`, listed in the props `items`, `districts`, `statsDistrictPages`), the pages of the offers ranking `/statystyki/polska/oferty/strona/{n}` (`pageHrefs`, 14 pages), and `/kalkulator-kredytu-hipotecznego`, `/kalkulator-refinansowania-kredytu`, `/kredyty`, `/o-nas`.

### Props of the 2.0 pages

[P 2026-10-30, saved scan HTML read with `flight.py`; component props only, layout props (`notFound`, `tytul`, `gtmId`, …) left out; Warsaw unless stated]. "Gone" means the name is absent from the flight data of the page.

| Page | 2.0 props | Gone |
|---|---|---|
| `/ceny-ofertowe/{city}/mieszkania` | `sales` (25 rows: `sale_id, name, amount, start_amount_difference(_percent), last_amount_difference(_percent), last_event_type, total_events, currency, size, status, last_event_date, last_change_event_date, creation_date, invest {invest_id, name, city, city_slug, slug, district, street, developer {developer_id, name, slug}}`), `serverPaginationData {currentPage, perPage, totalCount, totalPages, startItem, endItem}` (1, 25, 10,885, 20, 1, 25), `citySlug`, `cityName`, `cityLabel`, `items` (18 district links), `surface` | `initialData {data, pagination}`, `initialApiParams` |
| `/ceny-ofertowe/{city}/inwestycje` | `serverInvestments` (25 rows of 31 keys: the old `investments[]` keys plus `developer_id`, `district`, `year_construction`, `description`, `website`, `min_amount`, `min_price_sqm`, `avg_*_archived`, `avg_*_total`, `sale`), `serverPagination {page, total}` (1, 250), `citySlug`, `cityName`, `cityLabel`, `items`, `surface` | `investments`, `serverPaginationData`, `initialSortBy`, `initialSortOrder`, `includeArchived` |
| `/ceny-ofertowe/{city}/deweloperzy` | `developers` (25 rows, the same fields as before), `serverPaginationData` (page 1 of 4, 89 developers), `initialSortBy` (`totalSales`), `initialSortOrder` (`desc`), `dataType` (`offers`), `developerCities`, `cityLocatives`, `archivedOnlySlugs`, `citySlug`, `cityName`, `cityLabel`, `items`, `surface` | `filterCity`, `filterName` (as props) |
| `/ceny-ofertowe/{city}/deweloperzy/{developerSlug}` | `developer` (null on the ATAL page), `developerSlug`, `developerName`, `developerId`, `hero`, `tabs`, `investments` (4 rows: `invest_id, name, slug, city, city_slug, street, status, active_offers, total_offers, avg_amount, avg_size, avg_price_sqm, min_amount, min_price_sqm, latitude, longitude, sum_start_amount_difference_minus/plus`), `timeline {rows (65 daily rows: discountCount, increaseCount, discountValue, increaseValue, date, cumulative*), rebased {3m, 6m, 1y}}`, `spec`, `sparseBySize`, `breadcrumbs`, `info`, `citySlug`, `today` | `data {developer, investments, filteredStats, allCities, allCitiesWithSlugs, citiesStats, allInvestmentNames}`, `sale[]`, `data[]` (the price-change axis is now `timeline.rows`) |
| `/ceny-ofertowe/{*}/deweloperzy/{*}/{investmentSlug}` | `seed {detail, archiveMode, archivedIds}` where `detail` has the shape of `GET /api/map/investments/visible/{slug}` (with `description`, and per offer `floor` and `ev`) but only the active offers (21), while `archivedIds` lists the 54 archived ones; `soldPoints` (54 rows `{date, priceSqm, price, size, sizeClass, name, saleId}`), `average` and `median` (47 rows `{date, value, bySize[4]}`), `rows` (similar investments), `spec`, `sparseBySize`, `hero`, `tabs`, `breadcrumbs`, `info`, `powiatId`, `yearConstruction`, `summary`, `title` | `investments[1]`, `sales[]`, `stats`, `data[]` |
| `…/{investmentSlug}/raport-inwestycji` | `data` (valuation in the `standalone-valuation` shape), `property`, `competitors` (32), `investmentSales` (75: `saleId, name, price, size, status`), `investSlug`, `developerSlug`, `city`, `isAverageView`, `includePrimaryMarket`, `investmentName`, `options`, `items` | none (same main props as before) |
| `/ceny-ofertowe/{city}/mapa` | `citySlug`, `cityName`, `cityLabel`, `items`, `surface` only | `initialInvestments`: the page carries no data, the map chunk calls the JSON API itself [P z kodu] |
| **`/ceny-ofertowe/polska/miasta`** | `cities` (25 rows: `city, city_slug, powiat_id, lat, lng, offer_count, invest_count, developer_count, avg_price_sqm, avg_amount, avg_size, price_drop_share, min_amount, href, grodzki, region`), `serverPaginationData` | (new page) |
| `/ceny-transakcyjne/{city}/mieszkania`, `/domy` | `transactions` (25 rows, the fields of the old `initialData.data` incl. `invest`), `serverPaginationData` (1, 25, 353,785 transactions of flats in Warsaw, 20 pages), `variant` (`flat` or `house`), `citySlug`, `cityName`, `cityLabel`, `items`, `surface` | `initialData {data, pagination, stats}`, `initialApiParams`: no aggregate of the filtered set (`averagePrice`, `avgAmountPerM2`, `totalTransactions`) is in the page any more |
| `/ceny-transakcyjne/{city}/adresy` | `addresses` (25 rows: `kind, invest_rcn_id, name, street, city, city_slug, avg_amount, avg_size, avg_price_sqm` as strings, `transactions`, `last_event_date`, `slug, building_area, plot_area, source_rcn`), `serverPaginationData` | none known |
| `/ceny-transakcyjne/{city}/adresy/{investRcnSlug}` | `investment`, `sales` (with `events`, `hasMatchingEvent`), `investRcnId`, `latitude`, `longitude`, `spec`, `hero`, `tabs`, `address`, `addressPath`, `mapUrl` | none (`investment`, `sales` as before) |
| `/ceny-transakcyjne/polska/miasta` | `cities` (25 rows as `/api/city-transaction-stats`), `serverPaginationData`, `grodzkieBySlug` (66 entries `{powiatId, wojewodztwo}`) | `teaserCharts` |
| **`/ceny-transakcyjne/{city}/mapa`** | layout props only (`citySlug`, `cityName`, `cityLabel`, `items`, `surface`) | (new page; data via the JSON API) |
| **`/statystyki/{location}/transakcje`** | `view {monthly (118 rows 2017-01..2026-10: month, transaction_count, secondary_count, unknown_count, med/avg_price_sqm, med/avg_size, med/avg_amount), anchor, quarterly {current, prev, yearAgo}, priceChange, slices {quarterlyAnchor, yoyView, qoqView}, segmentSeries, brackets}`, `priceChange {quarter, points (39 rows: period, n, medSqm, avgSqm, medPrice, avgPrice, medSize, avgSize)}`, `latestSummary {month, transaction_count, secondary_count, unknown_count, med/avg_price_sqm, …}`, `blocks {ld, oferty, rcn, portale, gus, nbp, rcnSections, txRefQuarter, txDistrictQuarters, txDistrictWindow}`, `rawUrl` (`/api/statystyki/raw-transactions?typ=mieszkania&powiat=302&miasto=warszawa`), `cityDescription {voivodeship, totalTransactions}`, `heading`, `districts`, `identity`, `statsDistrictPages {oferty, transakcje, najem-krotkoterminowy}`, `metric`, `propertyType`, `locative` | `rawTransactions`, `powiats`, `topCities`: the page is **not** a D5 dump, the dump is the API path in `rawUrl` |
| **`/statystyki/{location}/dane-rzadowe`** | `blocks {ld, oferty, rcn, portale, gus, nbp, govSections}`, several `data` (told apart by shape: 87 quarterly construction rows `{quarter, oddane*, rozpoczete*}`; 21 age-cohort rows `{year, cohorts, totalKobiety, totalMezczyzni}`; 80 NBP rows `{quarter, pierwotnyOfertowa, pierwotnyTransakcyjna, wtornyOfertowa, wtornyTransakcyjna}`), `monthlyData` (260 monthly construction rows), several `spec` chart specs (`id, title, granularity, unit, datasets, …`), `locativePhrase`, `anchorId`, `info`, `citySlug`, `cityName` | `sortedLocations`, `tocItems` |
| **`/statystyki/{location}/oferty`** (`polska`) | `blocks {…, offerNational, offerStats {view, districtHrefs, places}}`, `series {polska, top7, reszta, warszawa, krakow, …: 22–36 monthly points each}`, `ranking {aggregates, rows (10), total 140, page, totalPages 14, pageHrefs}`, `table {month, label, qoqLabel, yoyLabel, rows}`, `text` | (new page) |
| `/` | `initialPopular {offers, transactions}`, `rows` (8 rows of per-city price-drop lists: `citySlug, title, href, sortQuery, rangeLabel, items`) | n/a |

How the new props map to tools [P 2026-10-30]: `search_offers` reads `sales` and `serverPaginationData` instead of `initialData`; the default is 25 rows per page (10 before) and the 20-page cap is still there (`totalPages` 20 for 10,885 offers); `get_developer` would have to read `developerName`, `developerId`, `investments` and `timeline`; the old totals `filteredStats` and `citiesStats` have no replacement among the props, so they would be computed from `investments`; `get_government_statistics` would have to read `data`, `monthlyData`, `spec` and `blocks` instead of `sortedLocations` and `tocItems`.

## How to fetch [P]

```
GET https://deweloperuch.pl<path>?<filters>&_rsc
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
- **Risk**: prop names (`initialData`, `serverPaginationData`, …) are a UI implementation detail and may change without warning [W]. The RSC adapter is isolated and covered by contract tests on samples. **It happened on 2026-10-29**: the 2.0 build renamed or dropped the props of most pages (see the 2.0 section above) and redirects every RSC request as described there. This section describes the format as of 2026-10-09; the request shape (`RSC: 1`, `_rsc`) no longer returns a payload (T63).

## Common list rules [P]

- 2.0 [P 2026-10-30, saved scan pages]: the default page size is 25 (10 before) and `totalPages` is still capped at 20 (10,885 offers in Warsaw → 20 pages; 353,785 transactions of flats → 20 pages). Not re-tested on 2.0: `page>20`, the `perPage` set, the filter parameters and sorting below, because no RSC request returns a payload (T63).
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
2.0 [P 2026-10-30, saved scan page]: **`initialData` is gone**; the rows are the prop `sales` and the paging is `serverPaginationData {currentPage, perPage, totalCount, totalPages, startItem, endItem}` (Warsaw: 25 rows, 10,885 offers, 20 pages). `sales[].invest` has two more keys, `district` and `street`. `search_offers` is broken by this and by the redirects (T57, T63).

### `/ceny-ofertowe/{city}/inwestycje`: investment list [P]
- `sortBy`: `name`, `active_offers`, `avg_amount`, `avg_size`, `avg_price_sqm` [P], `sum_changes`
- Props: `investments[]` (`invest_id, name, slug, city, city_slug, street, status, avg_amount, avg_size, avg_price_sqm, active_offers, total_offers, sum_start_amount_difference_plus/minus, developer{…}`), `serverPaginationData {currentPage, perPage, totalCount, totalPages, startItem, endItem}`, `initialSortBy`, `initialSortOrder`, `includeArchived`
- Sample: `page.investments_list.json`
- 2.0 [P 2026-10-30, saved scan page]: the rows are the prop `serverInvestments` and the paging is `serverPagination {page, total}` (page 1, 250 investments); `investments`, `serverPaginationData`, `initialSortBy`, `initialSortOrder` and `includeArchived` are gone.

### `/ceny-ofertowe/{city}/deweloperzy`: developer list [P]
- `sortBy`: `name`, `projectCount` [P], `totalSales`, `cityCount`, `avgSize`, `avgPrice`, `avgPricePerM2`, `sum_changes`
- Props: `developers[]` (`developer_id, name, slug, projectCount, totalSales, totalOffersCount, cities, cityCount, avgSize, avgPrice, avgPricePerM2, sum_start_amount_difference_plus/minus`), `serverPaginationData`, `filterCity`, `filterName`
- Sample: `page.developers_list.json`
- 2.0 [P 2026-10-30, saved scan page]: `developers`, `serverPaginationData` (89 developers, 25 per page), `initialSortBy` (`totalSales`) and `initialSortOrder` are still props; new: `dataType` (`offers`), `developerCities`, `cityLocatives`, `archivedOnlySlugs`; `filterCity` and `filterName` are not among the props any more.

### `/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`: developer profile [P]
- Props: `data {developer, investments[], filteredStats, allCities, allCitiesWithSlugs, citiesStats, allInvestmentNames}`, `sale[]` (lightweight offer list), `data[]` (daily price-change axis: `discountCount, increaseCount, discountValue, increaseValue, cumulative*`)
- Sample: `page.developer.json`
- 2.0 [P 2026-10-30, saved scan page]: **the props above are gone** (`data`, `filteredStats`, `citiesStats`, `sale[]`). The page has `developer` (null), `developerSlug`, `developerName`, `developerId`, `hero`, `tabs`, `investments`, `timeline`, `spec`, `sparseBySize`; see the 2.0 section. `get_developer` is broken by this and by the redirects (T57, T63).
- `{city}` filters the investments to that city; `polska` gives all cities (ATAL: 42 investments, 6587 `sale` rows, ~1.96 MB) [P 2026-10-13, raw fixtures `tests/fixtures/rsc/developer_atal_warszawa.rsc`, `developer_atal_polska.rsc`, consistency tests in the suite].
- Consistency in both fixtures [P 2026-10-13]: `filteredStats.totalProjects` = number of investments; `totalSales` = Σ `active_offers` = active rows in `sale`; Σ `total_offers` = len(`sale`); `totalCities` = number of cities of the investments; `averagePrice` = round(mean price of active offers); `averageSize` = mean area of active offers (±0.01); `avgAmountPerM2` = round(mean of investments' `avg_price_sqm` weighted by `active_offers`); per investment `total_offers`/`active_offers`/`avg_amount`/`avg_size` agree with `sale`. `citiesStats` is identical on the city page and the `polska` page (14 rows) and consistent with the investments; the Warsaw row equals the Warsaw page's `filteredStats`.
- `priceIncreaseCount`/`priceDecreaseCount` are 0 while the sums are non-zero: unreliable, not used (they stay unknown) [P 2026-10-13].
- A developer without active offers in that city gets 0 for every average: `filteredStats` is `{totalProjects: 0, totalSales: 0, totalCities: 0, averagePrice: 0, averageSize: 0, avgAmountPerM2: 0}` and `investments` is empty [P 2026-10-20, live: `/ceny-ofertowe/bialystok/deweloperzy/atal`; the same for `murapol` in `olsztyn` and `develia` in `lublin`]. A 0 is no value, not a price.
- Unknown developer (`/ceny-ofertowe/warszawa/deweloperzy/nieistniejacy-deweloper`): HTTP 200, **no** `NEXT_HTTP_ERROR_FALLBACK;404` digest (unlike the offer list); h1 "Deweloper nie znaleziony", title "Deweloper nie znaleziony | Deweloperuch" [P 2026-10-13, fixture `developer_unknown_warszawa.rsc`]. The client must detect this by the missing data / title.

### `/ceny-ofertowe/{*}/deweloperzy/{*}/{investmentSlug}`: investment [P]
- **The `{city}` and `{developer}` segments are ignored**. `/ceny-ofertowe/warszawa/deweloperzy/dom-development/nowy-targowek-vi` returns the ATAL investment [P].
- Props: `investments[1]`, `sales[]` (all, including archived), `stats`, `data[]` (price-change axis)
- Contains the same as `GET /api/map/investments/visible/{slug}` plus the change axis. The JSON API is preferred.
- Sample: `page.investment.json`
- 2.0 [P 2026-10-30, saved scan page]: the props above are gone; the page has `seed.detail` (the shape of `GET /api/map/investments/visible/{slug}`, active offers only) with `archivedIds`, plus `soldPoints`, `average`, `median`; see the 2.0 section.

### `…/{investmentSlug}/raport-mieszkania-{slug(nazwa)}`: offer report [P]
- Slug = `slugify(sale.name)`: Polish characters → ASCII, lowercase, remove everything except `[a-z0-9\s-]`, spaces → `-` [P z kodu]. `D1.1.1.4` → `d1114`. **Collisions possible** (`D1.11.4` also gives `d1114`) [W].
- Props: `property {name, investmentName, developer, address, area, offerPrice, offerPricePerSqm, latitude, longitude}`, `priceHistory[{amount, creation_date}]`, `competitors[]` (offers of similar area nearby: `investmentName, developer, distance, investSlug, developerSlug, sales[{saleId, area, price, pricePerSqm, sizeMatch}]`), `investmentSales[]`, `data` (**RCN valuation** in the `standalone-valuation` format)
- Sample: `page.offer_report.json`
- 2.0: the offer report page was not among the pages the scan fetched, so its props are unchanged only as far as the investment report (below) shows [W].

### `…/{investmentSlug}/raport-inwestycji`: investment report [P]
- Like the offer report, but `property` describes the investment average.
- 2.0 [P 2026-10-30, saved scan page]: still 200 with `data`, `property`, `competitors`, `investmentSales` (see the 2.0 section).

### `/ceny-ofertowe/{city}/mapa` [P]
- Props: `initialInvestments[]` (as `/api/map/investments`). The rest through the JSON API.
- 2.0 [P 2026-10-30, saved scan page]: `initialInvestments` is gone; the page has only the layout props.

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
2.0 [P 2026-10-30, saved scan page]: **`initialData` and `initialApiParams` are gone**; the rows are the prop `transactions`, the paging `serverPaginationData` (Warsaw flats: 25 rows, 353,785 transactions, 20 pages) and `variant` (`flat` or `house`). The aggregate `stats` of the whole filtered set (`averagePrice`, `avgAmountPerM2`, `totalTransactions`, …) is not in the page any more, so the "aggregates without paginating" remark above no longer holds on 2.0.

### `/ceny-transakcyjne/{city}/adresy`: building list [P]
- `sortBy`: `name`, `transactions` (default), `avg_size`, `avg_price_sqm`, `avg_amount`
- 2.0 [P 2026-10-30, saved scan page]: prop `addresses` (25 rows; `avg_amount`, `avg_size` and `avg_price_sqm` are strings; new `last_event_date`) and `serverPaginationData`.
- Element: `{kind: "flat"|"house", invest_rcn_id, name, street, city, city_slug, avg_amount, avg_size, avg_price_sqm, transactions, slug, building_area, plot_area, source_rcn}`

### `/ceny-transakcyjne/{city}/adresy/{investRcnSlug}` and `/domy/{investRcnSlug}`: building/house [P]
- Props: `investment {invest_id (= invest_rcn_id), latitude, longitude, name, slug, city, city_slug, street, avg_*, active_offers (= number of units)}`, `sales[]` with `events[]` (full `sale_event_rcn` with `additionalData`)
- Houses additionally have `size_usable`, `size_building`, `size_plot` [P]
- `GET /api/map/transactions/visible/{slug}` gives the same, and it is preferred.
- Sample: `page.address.json`, `page.house.json`
- 2.0 [P 2026-10-30, saved scan page]: the names `investment` and `sales` (with `events`) are unchanged; new `investRcnId`, `hasMatchingEvent`, `spec`, `hero`, `tabs`.

### `/ceny-transakcyjne/polska/miasta`: city ranking [P]
- Props: `cities[]` (as `/api/city-transaction-stats`), `teaserCharts[]` (monthly series for top cities)
- Linked only, never fetched by the package, as is `/ceny-transakcyjne/{city}/adresy/{slug}` [P 2026-10-13].
- 2.0 [P 2026-10-30, saved scan page]: `cities`, `serverPaginationData` and the new `grodzkieBySlug`; `teaserCharts` is gone.

---

## Statistics

### `/statystyki/ceny-transakcyjne/{mieszkania|domy}/{city}` [P]
- Props: `rawTransactions[]` is **all of a city's transactions in short form** (Warsaw: 128,912 rows, HTML 12.9 MB): `{m: "YYYY-MM", s: area, a: amount, ps: price/m², c: classification, rn: rooms, fn: floor}`. Range 2017-01 → current month.
- `latestSummary` (last full month), `slices` (y/y and q/q by cross-sections: area, rooms, …), `topCities`
- URL filters (`filterPrice`, `filterSize`, `filterRooms`, …) are handled client-side on `rawTransactions` [W].
- Too heavy for direct use. Aggregates are better taken from `/api/monthly-transaction-stats`.
- The package only links to this page (a bulk-dump page, see D5 in [decisions.md](../decisions.md)); it is never fetched [P 2026-10-13].
- 2.0: **the route has changed**. The statistics now live at `/statystyki/{city}/transakcje`, whose props carry no `rawTransactions` (the dump is the API path `/api/statystyki/raw-transactions?typ=…&powiat=…&miasto=…`, passed as the prop `rawUrl`) [P 2026-10-30, saved scan page]. Whether this old URL redirects is not known (T55 a); `latestSummary` and `slices` moved to the new page.

### `/statystyki/ceny-transakcyjne/{type}/{city}/mapa` [P]
- Props: `powiats[]`: `{powiat_rcn_id, powiat_name, transaction_count, med_price_sqm, med_size, med_amount, transaction_count_change, price_sqm_change, amount_change}` (period: last quarter vs previous? [H])
- 2.0: **308** to `/statystyki/{city}/transakcje` [P 2026-10-29, scanner]; that page has no `powiats` prop [P 2026-10-30, saved scan page]. The county map data probably comes from the new `/api/statystyki/powiat-map-stats` [H] (T59).

### `/statystyki/statystyki-rzadowe/{location}`: GUS + NBP [P]
- **The only channel** for this data (no JSON API).
- `location`: 69 locations: cities and the aggregates `polska`, `7-miast`, `10-miast`, `9-miast`, `6-miast-bez-warszawy` (prop `sortedLocations` mapped to `gus.teryt` and `nbp.dbName`)
- Sections (`tocItems`): `gus-mieszkania` (quarterly and monthly: completed/started by construction form), `gus-formy-budownictwa`, `gus-srednia-powierzchnia` (yearly), `gus-demografia` (births, deaths, natural change), `gus-wiek` (5-year cohorts F/M), `gus-bezrobocie` (monthly rate), `gus-wynagrodzenia`, `nbp` (quarterly: `pierwotnyOfertowa`, `pierwotnyTransakcyjna`, `wtornyOfertowa`, `wtornyTransakcyjna`)
- Several props are named `data`; they have to be told apart by shape or position in the tree [P]. A fragile spot.
- Cache headers [P 2026-10-13, `polska`]: `private, max-age=28800, must-revalidate`; `cf-cache-status: HIT`; `age: 69574` (above `max-age`). The client caches such replies for 300 s (see D2 in [decisions.md](../decisions.md)).
- Sample: `page.stats_gov.json`
- 2.0: **308** to `/statystyki/{location}/dane-rzadowe` [P 2026-10-29, e2e]; the new page has `blocks`, several `data`, `monthlyData`, `spec`, `locativePhrase`, `anchorId`, `info`, and neither `sortedLocations` nor `tocItems` [P 2026-10-30, saved scan page]; see the 2.0 section. `get_government_statistics` is broken by this and by the redirects (T57, T63).

### `/statystyki/{location}/dane-rzadowe`: GUS + NBP since 2.0 [P 2026-10-30]
- Since the 2.0 build (2026-10-29) the old `/statystyki/statystyki-rzadowe/{location}` answers 308 to this route [P 2026-10-29]. The old route stays in the allowlist only to see that redirect.
- `location`: `polska`, a city slug or an aggregate, as before.
- Props [P 2026-10-30, live RSC payloads of the package client, `wroclaw` and `polska`]: `data` rows for dwellings (quarterly), population (`gus-wiek`) and NBP prices (`wroclaw` only), `monthlyData` (monthly dwellings), chart specs `spec` (`id` such as `gus-wynagrodzenia-wykres`, `datasets.<key>.points[] {period, values}`) which alone carry average area, demography, unemployment and wages, `blocks.govSections` (the section ids, the old `tocItems`), `citySlug` (absent on `polska`), `cityName`; no `tocItems`, `sortedLocations` or `currentSlug`.
- Request: an empty `_rsc` (`?_rsc`) with `RSC: 1` returns `text/x-component` (200) [P 2026-10-30]. Since the 2.0 build any other `_rsc` gets a 307 to the same URL with an empty one, and `page=1` a 308 to the URL without it; this applies to every RSC page the package reads.

### `/statystyki/portale-ogloszeniowe/{type}/{region}` [P]
- Data loaded client-side from `/api/announcement-stats`. The page contains only a skeleton and the region list.
- 2.0: **308** to `/statystyki/{region}/portale-ogloszeniowe` for `mieszkania/polska` [P 2026-10-30, scanner]; the target was not requested.

---

## Other

### `/zglos-dewelopera/mapa-zgloszen` [P]
- Props: `developerAbuseData[]` (105): `{developer_abuse_id, name, slug, developer, website, latitude, longitude, violations[], additionalInfo}`, that is reports of violations of the price transparency act.
- No sample is kept: the reports are user-submitted texts naming companies.
- 2.0: **410 Gone** for this page and for `/zglos-dewelopera` [P 2026-10-30, scanner]; the report-a-developer feature and its Turnstile form are gone. The route is still in `allowlist.PAGE_ROUTES`.
