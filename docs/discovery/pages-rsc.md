# SSR (RSC) pages as a data source

Search with filters, sorting and pagination, and most detail views, exist **only** as server-rendered pages. The data is in the props of client components in the RSC payload.

## 2.0 redesign (deployed 2026-10-29): read this first

Every section after this one describes the survey of 2026-10-09 (build `KD_IOP6Grqba7xa86pGVG`). The service now runs build `VDpA73sQ-GRMsEMdmIQtu` (Next.js 15.5.25, still webpack). An old entry that was re-checked carries `[P 2026-10-29]` (live e2e run of the package client) or `[P 2026-10-30]` (the saved HTML of the bundle scan, read offline with `flight.py`, no extra request). The old headings stay as they are because `tests/recon_scripts/test_probe_allowlist.py` pairs them with `allowlist.PAGE_ROUTES`; the 2.0 routes are in the tables below, which that test ignores. Promoting a 2.0 route to a heading and to `PAGE_ROUTES` is one change: the heading here first, then the allowlist counterpart in code (T61). Three routes were promoted on 2026-10-30 (D20, D21): `/statystyki/{location}/transakcje` and `/statystyki/{location}/dane-rzadowe` (section "Statistics") and `/ceny-ofertowe/{city}/{district}/mieszkania` (section "Asking prices"). Their `PAGE_ROUTES` entries exist since 2026-10-31, so probe reached all three in round B2 (30 requests of 2026-10-31, [P 2026-10-31] below). The other 2.0 routes stay in the tables.

### RSC requests: an empty `_rsc` returns the payload (T63, resolved 2026-10-31)

Live e2e run of the package client on 2026-10-29 [P 2026-10-29, `tests/e2e/`]: `GET <path>?<filters>&_rsc=<hashed token>` with `RSC: 1` gets no payload, the 2.0 server redirects it:
- With `page=1` in the query: `308` to the same URL without `page=1` and without `_rsc` (the canonical form), e.g. `/ceny-ofertowe/krakow/mieszkania?page=1&perPage=10&_rsc=0db79c39` → `/ceny-ofertowe/krakow/mieszkania?perPage=10`.
- Otherwise (for example `page=2`, a developer page, an unknown developer): `307` to the same URL with an empty `_rsc`, e.g. `…/mieszkania?page=2&perPage=10&_rsc=4d5af205` → `…/mieszkania?page=2&perPage=10&_rsc` (the e2e log prints the target without `=`).

The empty `_rsc` is what the `307` points to, and **it returns the payload** [P 2026-10-31, probe: `RSC: 1`, `_rsc=` last in the query, no redirect followed]. `GET /ceny-ofertowe/warszawa/mieszkania?_rsc=` → `200 text/x-component`, 73,057 B (the HTML of the same page was 273,652 B on 2026-10-30), `cache-control: private, max-age=172800, must-revalidate`, `cf-cache-status: MISS` (the same address again: `HIT`, `age: 7`); props `sales` (25 rows) and `serverPaginationData` `{currentPage: 1, perPage: 25, totalCount: 11672, totalPages: 20, startItem: 1, endItem: 25}`. Samples: `page.offers_list.v2_sales`, `page.offers_list.v2_pagination`.
- Every request that reached an existing page answered `200 text/x-component` without a redirect: the offers list (also with `page=2`, `perPage`, sorting and filters), the district list, the developer page, `dane-rzadowe` for 3 locations and `transakcje`. A page above 1 is not redirected: `?page=2&perPage=10` → `serverPaginationData` `{currentPage: 2, perPage: 10, …}`. Unknown entities answer differently, see the section on each page and [endpoints.md](endpoints.md) section 9.
- The RSC payload carries the props the saved HTML had, checked on 4 pages (table after "Props of the 2.0 pages"). It is 27 to 62 % of the HTML (offers list 73,057 B against 273,652 B; developer page 152,436 B against 323,264 B; `dane-rzadowe` 376,989 B against 608,055 B; `transakcje` 151,126 B against 354,377 B).
- Not tested: `page=1` with an empty `_rsc` (does it still answer `308`? T77) and the canonical URL without `_rsc` (cached HTML?). The package leaves `page=1` out (`OffersQuery`), so neither matters for it.
- The pages that were not requested in RSC form (investments list, developers list, transactions list, addresses, city ranking, offer and investment pages) have their 2.0 props only from the saved HTML (T57).

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

Linked from the props, **not requested** (status unknown; the one exception is the district offer list `/ceny-ofertowe/{city}/{district}/mieszkania`, answered `200` on 2026-10-31, section "Asking prices"): district pages `/ceny-ofertowe/{city}/{district}/{mieszkania|inwestycje|deweloperzy|mapa}`, `/ceny-transakcyjne/{city}/{district}/{mieszkania|domy|adresy|mapa}` and `/statystyki/{city}/{district}/{transakcje|oferty|najem-krotkoterminowy}` (the district is an ASCII slug such as `bemowo`, listed in the props `items`, `districts`, `statsDistrictPages`), the pages of the offers ranking `/statystyki/polska/oferty/strona/{n}` (`pageHrefs`, 14 pages), and `/kalkulator-kredytu-hipotecznego`, `/kalkulator-refinansowania-kredytu`, `/kredyty`, `/o-nas`.

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

RSC payload against the saved HTML [P 2026-10-31, probe `page`, `RSC: 1`, empty `_rsc`; RSC bytes against the HTML bytes of the scan]:

| Page | RSC bytes (HTML bytes) | Checked in the RSC payload, equal to the saved HTML |
|---|---|---|
| `/ceny-ofertowe/warszawa/mieszkania` | 73,057 (273,652) | `sales` (25 rows, the keys of the table above), `serverPaginationData` (6 keys) |
| `/ceny-ofertowe/warszawa/deweloperzy/atal` | 152,436 (323,264) | `hero` with the props `investments` (4 rows), `developerSlug`, `developerName`, `developerId`; the first of 4 `spec` props is `ceny-w-miastach` |
| `/statystyki/warszawa/dane-rzadowe` | 376,989 (608,055) | `blocks` (7 keys), `blocks.govSections` (8 ids), the `data` props (87, 21 and 80 rows), `monthlyData` (260), 3 `spec`, 2 `info` |
| `/statystyki/warszawa/transakcje` | 151,126 (354,377) | `view` (`monthly` 118 rows, equal row by row), `latestSummary` |

Not equal on every location: the `dane-rzadowe` props differ between `warszawa`, `7-miast` and `polska` (section "Statistics"). `developerName`, `developerId` and `developerSlug` are props of the single element held by the prop `hero`, together with `investments`; asking `probe --prop hero` returns that element `["$", "$L23", null, {…}]` with all four (the saved sample of it is cut to nothing by the tuple rule, see the developer page below).

How the new props map to tools [P 2026-10-31]:
- `search_offers` reads `sales` and `serverPaginationData` instead of `initialData`; the default is 25 rows per page (10 before) and the 20-page cap is still there; the `district` filter is the route `/ceny-ofertowe/{city}/{district}/mieszkania`, because `filterDistrict` no longer returns a list.
- `get_developer` reads the prop `hero` (`developerName`, `developerId`, `developerSlug`, `investments`) and the first `spec` (the cities); the old totals `filteredStats` and `citiesStats` have no replacement among the props, so the summary is computed from `investments` and the cities come from the rows of the `ceny-w-miastach` spec.
- `get_government_statistics` reads `data` (several, told apart by shape), `monthlyData`, `spec` and `blocks.govSections` instead of `sortedLocations` and `tocItems`; the set of props depends on the location (`polska` has no NBP `data`).
- `get_transaction_statistics` (monthly series) reads `view.monthly` of `/statystyki/{location}/transakcje`: flats, secondary market only.

## How to fetch [P]

```
GET https://deweloperuch.pl<path>?<filters>&_rsc=
RSC: 1
→ 200 text/x-component
```

- `_rsc` is the last query parameter and **empty** [P 2026-10-31] (T63). Until 2026-10-29 (build `KD_IOP6Grqba7xa86pGVG`) any value worked, and the package sent a hash of the path; the 2.0 server redirects a value it does not expect (`307`, or `308` with `page=1`) to the empty one [P 2026-10-29, e2e], and the empty one returns the payload [P 2026-10-31].
- Why empty [P z kodu 2026-10-30]: the 2.0 client (Next.js 15.5.25, chunk `1255`, module `13485`, `setCacheBustingSearchParam`) sets `_rsc` to a hash of the router headers `Next-Router-Prefetch`, `Next-Router-Segment-Prefetch`, `Next-Router-State-Tree` and `Next-Url`, and leaves it empty when none of them is sent (a prefetch header of `0` counts as none). The package and probe send only `RSC: 1`, so the value the client would compute for the same request is empty. A value computed for other router headers, or any invented one, is what the server redirects.
- `_rsc` gives the request an address of its own: Cloudflare ignores `Vary: RSC`, so the page's own address (without `_rsc`) returns cached HTML [P 2026-10-10, 1.0; not re-tested on 2.0]. On 2.0 the CDN caches the RSC response by the full address: the same address requested twice in a row was `MISS`, then `HIT` with `age` 6 to 9 s on 4 of 4 pairs [P 2026-10-31].
- `page`: the canonical address of the first page has no `page` parameter. The 2.0 server answers `page=1` with a `308` to the address without it [P 2026-10-29, e2e, hashed `_rsc`], so the package leaves `page=1` out (`OffersQuery`); `page=1` with an empty `_rsc` was not tested (T77). [P z kodu] the 1.0 client dropped `page=1`, `perPage=10`, `sortBy=last_event_date` and `sortOrder=desc` from the URLs it builds (chunk `1686-fe1f66e0f35e4b33`, the 1.0 build); the 2.0 chunks in the scanner cache show no such rule (the pager of chunk `5752` sets `page: "1"` on a change of `perPage`), so that the 2.0 client drops `page` up to 1 is [W]: only the server's `308` is [P].
- Alternative: full HTML and decoding `self.__next_f.push([1,"…"])`. Gives the same data but is 1.6 to 3.8 times larger (1.0: 942 KB against 98 KB [P]; 2.0 [P 2026-10-31]: 73,057 B against 273,652 B for the offer list, 376,989 B against 608,055 B for `dane-rzadowe`).
- Props sit in elements `["$","$L<id>",null,{…}]`. References `"$f:props:…"` / `"$8:props:…"` point to previously defined fragments, but the props with list data are inline [P].
- Flight format (rows `<id>:<tag><data>`) [P z kodu, chunk `1517-…js` ReactFlightClient from the scanner cache]:
  - rows with a length in BYTES, **no `\n` after the row**: `<id>:T<hexlen>,<text>`; binary tags `A O o U S s L l G g M m V` (with `T`) work the same way. The next row starts right after the data, so looking for rows only at the start of a line loses them;
  - rows terminated by `\n`: tags `A`–`Z` (incl. `E` error), `#`, `r`, `x`, and a model row without a tag (`<id>:<json>`);
  - hints `:HL…` have an empty id.
  - On the offer list the row with `initialData` comes right after two `T` rows with JSON-LD (`16:T5ed,…` WebPage, `19:T1a27,…` ItemList) [P 2026-10-10, fixture `tests/fixtures/rsc/warszawa_perPage10.rsc`]. Refuted: the old parser (`_JSON_ROW`, rows only at the start of a line) saw no `initialData` there, so `search_offers` did not work on the live service.
- Reference parser: [`src/deweloperuch_mcp/flight.py`](../../src/deweloperuch_mcp/flight.py): `rows()`, `component_props()`, `error_digests()` (RSC) and `flight()` for HTML. `find_json_after(text, "initialData")` stays for `probe --prop`; `recon/flight.py` only re-exports.
- Cache-Control of RSC pages: `private, max-age=28800, must-revalidate` (no `s-maxage`; `cf-cache-status` MISS or HIT with `age`) [P 2026-10-10, samples headers only, no separate sample]. 2.0 [P 2026-10-31]: `private, max-age=172800, must-revalidate` on every page requested (30 requests; the same 172,800 s as on the JSON responses of the second series of 2026-10-30, [endpoints.md](endpoints.md)), also on the 404 of an unknown statistics location.
- **Risk**: prop names (`initialData`, `serverPaginationData`, …) are a UI implementation detail and may change without warning [W]. The RSC adapter is isolated and covered by contract tests on samples. **It happened on 2026-10-29**: the 2.0 build renamed or dropped the props of most pages (see the 2.0 section above) and redirected every RSC request with a hashed `_rsc`. The format of this section (rows, props in elements) is unchanged on 2.0 [P 2026-10-31]; the request shape is now `RSC: 1` with an empty `_rsc` (T63).

## Common list rules [P]

- 2.0 [P 2026-10-31, RSC payloads of the offer list of Warszawa]: the default page size is 25 (10 before) and `totalPages` is `ceil(totalCount / perPage)` capped at 20 (11,672 offers → 20; 237 offers → 10 pages; with `perPage=10` it is 20 again, so only the first 200 offers are reachable). `perPage=10` and `perPage=100` are accepted (`serverPaginationData.perPage` 10; 100 rows). `page=2` works (`perPage=10`: `currentPage` 2, `startItem` 11, `endItem` 20). The paging props are `serverPaginationData {currentPage, perPage, totalCount, totalPages, startItem, endItem}`. Not re-tested on 2.0: `page>20`, `perPage` 20, 50 and 500 (T29).
- `page`: from 1. **Maximum 20 pages**: `page>20` returns page 20 (`pagination.page: 20`) [P] (1.0).
- `perPage`: `10`, `25`, `50`, `100` accepted [P 2026-10-10: `perPage=25` → `pagination.perPage: 25`, 25 rows; refuted: hypothesis that only {10, 50, 100} are allowed]. `20` and `500` give the default 10 [P] (1.0; the 2.0 default is 25). The full list of allowed values is not known: observed 10, 25, 50, 100 (accepted) and 20, 500 (→ 10) [P]; others [H] (full list: T29). 2.0 [P 2026-10-31]: 10 and 100 accepted again.
- Ceiling: **2,000 records per query**. `pagination.total` gives the full count (e.g. 13,324), but `totalPages` is truncated to 20 [P] (1.0; on 2.0 `serverPaginationData.totalCount` and `totalPages`).
- `sortOrder` ∈ {`asc`, `desc`}.
- Ranges: `min-max` (e.g. `filterPrice=500000-700000`). No lower bound → `0-…`; no upper bound → UI sentinel values: price `99999999`, price/m² `999999`, area `9999` [P z kodu]. The server treats `filterPrice=0-99999999&filterSize=0-9999` as no filter: `pagination.total` = 13324 = result without filters (Warsaw) [P 2026-10-10]; the price/m² sentinel (`999999`) was not tested separately [W]. 2.0 [P 2026-10-31]: the upper bound is inclusive, and the three ranges narrow the list by `amount`, `size` and `amount / size`: `filterPrice=0-500000` → 237 offers, `filterSize=0-40` → 3,108, `filterPricePerM2=0-15000` → 2,855; each equals the count of the offer snapshot of Warszawa the same day with the value `≤` the bound (`<` would give 237, 3,104 and 2,820; [endpoints.md](endpoints.md), `map/offer-snapshot`). The sentinels were not re-tested on 2.0 (T33).
- Lists: comma-separated values (`filterRooms=2,3`).
- `{city}` = city slug or `polska` (whole country) [P].

---

## Asking prices

### `/ceny-ofertowe/{city}/mieszkania`: offer list [P]
| Parameter | Values | Status |
|---|---|---|
| `sortBy` | `amount`, `price_per_sqm`, `size`, `name`, `start_amount_difference_percent` | [P 2026-10-10] `amount` (asc and desc, sample `page.offers_list.sort_desc`), `price_per_sqm`, `size`, `name`, `start_amount_difference_percent`: order matches the value. 2.0 [P 2026-10-31]: `amount` with `sortOrder=desc` and `perPage=100` → 100 rows in descending order, the first 7,820,948 (the same top price as on 2026-10-10); the other keys were not re-tested |
| `sortBy` (cont.) | `last_event_date` | [P 2026-10-10] accepted, but the first `asc` rows are not ordered by the `last_event_date` visible in the list (e.g. 2026-10-03 before 2026-09-03); actual key unknown [H] |
| `sortBy` (cont.) | `investment`, `last_amount_difference`, `last_amount_difference_percent`, `start_amount_difference` | [W z kodu], not tested |
| `sortBy` default / unknown | absent or any text (`bogus`) | [P 2026-10-10] identical result: ascending by `sale_id` (database order); an unknown value is silently ignored, no error. Refuted: the default `sortBy` is not `amount`. 2.0 [P 2026-10-31]: the default order (no `sortBy`) is still ascending by `sale_id` (25 rows, ids increasing) |
| `filterPrice`, `filterPricePerM2`, `filterSize` | `min-max` range | [P] (`filterPrice`, `filterSize`). 2.0 [P 2026-10-31], all three: `filterPrice=0-500000` → 237 of 11,672, `filterSize=0-40` → 3,108, `filterPricePerM2=0-15000` → 2,855 (the upper bound is inclusive, see "Common list rules"; `filterPricePerM2` is [P] for the first time) |
| `filterDeveloper` | developer slug | [W] |
| `filterProject` | investment slug | [W] |
| `filterDistrict` | name (e.g. `Mokotów`, URL-encoded) | [P 2026-10-10] total 1562 = district `count` from `location-search`. **2.0: refuted [P 2026-10-31]**: `filterDistrict=Mokotów` (the name) and `filterDistrict=mokotow` (the slug) both answer `200 text/x-component` (27,316 B and 27,309 B) with no `sales` and no `serverPaginationData`; the district list is now the route `/ceny-ofertowe/{city}/{district}/mieszkania` (below, T73) |
| `filterStreet` | name | [W] |
| `filterPriceChange` | csv of `decrease`, `increase`, `no_change` | [P 2026-10-10] `decrease`: total 13324 → 2416. Refers to the change relative to the initial price (`start_amount_difference*`), not the last event: rows with `last_event_type: PRICE_INCREASE` and negative `start_amount_difference_percent` pass. `increase`/`no_change`, csv values: [W]. 2.0 [P 2026-10-31]: `decrease` → 2,167 of 11,672, as many as the offers of the snapshot with a negative `start_amount_difference` (index 6 of its rows) |
| `filterRooms`, `filterFloors` | csv | [P 2026-10-10] **no effect on the offer list**: `filterRooms=2` and `filterFloors=1` return total 13324 as without a filter (refuted: [W] that they narrow the offer list; offers have no rooms/floor fields). The filters work only in transactions |
| `filterStatus` | `archived` | [P 2026-10-10] `archived` → total 11415, all `status: archived`. `active` and other values not tested [H]. 2.0 [P 2026-10-31]: `archived` → total 12,471 (against 11,672 active offers); the rows were not read |
| `filterAnomalies` | `false` = also show anomalies | [W] |
| `includeArchived` | `true` | [P 2026-10-10] total 13324 → 24739 (= 13324 active + 11415 archived). 2.0 [P 2026-10-31]: 11,672 → **34,011**, which is not 11,672 + 12,471 = 24,143: 9,868 more than the active and the `filterStatus=archived` offers together (1.0 added up exactly); the cause is unknown (T72) |
| `showArchivedInvestments` | `true` | [W] |

Props `initialData` (1.0, until 2026-10-29):
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

**2.0 props [P 2026-10-31, RSC payload of `/ceny-ofertowe/warszawa/mieszkania`, samples `page.offers_list.v2_sales`, `page.offers_list.v2_pagination`]**: `initialData` is gone (and `initialApiParams`).
- `sales`: the rows, 25 by default, in the order of the request (no `sortBy`: ascending by `sale_id`). Keys of a row: `sale_id` (int), `name` (the developer's label, e.g. `A2`), `amount`, `start_amount_difference`, `start_amount_difference_percent`, `last_amount_difference`, `last_amount_difference_percent` (strings), `last_event_type` (all four values `PRICE_INCREASE`, `PRICE_DECREASE`, `NO_CHANGE`, `NEW_OFFER` occur among the 125 rows read), `total_events` (int), `currency` (`PLN`), `size` (string), `status` (`active` in all 125 rows; the archived ones were not read), `last_event_date`, `last_change_event_date`, `creation_date` (`YYYY-MM-DD`), `invest {invest_id, name, city, city_slug, slug, district, street, developer {developer_id, name, slug}}`. Against 1.0 only `invest.district` (a name, e.g. `Mokotów`) and `invest.street` are new. Every one of the 125 rows read (25 in the default order, the 100 dearest) is also in the offer snapshot of Warszawa with equal `amount`, `size`, investment, district, street and developer ([endpoints.md](endpoints.md), `map/offer-snapshot`).
- `serverPaginationData`: `{currentPage, perPage, totalCount, totalPages, startItem, endItem}`, all integers: Warszawa 11,672 active offers on 2026-10-31 (10,885 on 2026-10-30 in the saved page), `totalPages` capped at 20, `endItem − startItem + 1` is the number of rows.
- Unknown city: `200 text/x-component`, 25,189 B, the digest `NEXT_HTTP_ERROR_FALLBACK;404` twice, as on 1.0 [P 2026-10-31]; no `sales`.
- The other props of the page were not listed from the RSC payload; the saved HTML has layout props only (`items` with the 18 districts `{name, slug, href}`, `citySlug`, `cityName`, `cityLabel`, `surface`) [P 2026-10-30].
- `search_offers` is broken in code by the renamed props (T57); the redirect that broke it too is gone with the empty `_rsc` (T63).

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
- 2.0 [P 2026-10-30, saved scan page]: **the props above are gone** (`data`, `filteredStats`, `citiesStats`, `sale[]`). The page has `developer` (null), `developerSlug`, `developerName`, `developerId`, `hero`, `tabs`, `investments`, `timeline`, `spec`, `sparseBySize`; see the 2.0 section. `get_developer` is broken by this (T57); the redirects that broke it too are gone with the empty `_rsc` (T63).
- **2.0 RSC payload [P 2026-10-31]**, `ATAL` in `warszawa`: `200 text/x-component`, 152,436 B (HTML 323,264 B).
  - Identity and investments are the props of **one element**, the prop `hero`: `["$", "$L23", null, {investments, developerSlug, developerName, developerId}]` (the row reference is `$L23` in the RSC payload and was `$L25` in the saved HTML: it is no stable name) with `developerSlug` `atal`, `developerName` `ATAL S.A.`, `developerId` 43. `probe --prop hero --full` prints all four. **The sample `page.developer.v2_hero` holds no data**: the sample convention cuts a 4-element list to 3 items, and the props are the 4th, so it keeps only `"$"`, `"$L23"`, `null` and `"... (1 more, 4 total)"`. The same data can be saved by asking for the props inside the element, e.g. `--prop investments` (the first occurrence of the name is the list, [P 2026-10-30, saved HTML]), which round B2 did not do (no requests left). `developer` is null on this page, there is no `website` or `description`. A second occurrence of the prop `investments` in the stream is only a reference string (`$22:props:children:0:props:hero:props:investments` in the HTML); the first one is the list.
  - First row of `investments`, verbatim: `{"invest_id": 54, "name": "Nowy Targówek VI", "slug": "nowy-targowek-vi", "city": "Warszawa", "city_slug": "warszawa", "street": "Targówek", "status": "active", "active_offers": 21, "total_offers": 75, "avg_amount": 1073611.14, "avg_size": 60.84, "avg_price_sqm": 17646, "min_amount": 659315, "min_price_sqm": 16509, "latitude": 52.2815704, "longitude": 21.04711656, "sum_start_amount_difference_minus": -2901678, "sum_start_amount_difference_plus": 982674}`.
  - `investments` (4 rows for the city): `invest_id, name, slug, city, city_slug, street, status, active_offers, total_offers, avg_amount, avg_size, avg_price_sqm, min_amount, min_price_sqm, latitude, longitude, sum_start_amount_difference_minus, sum_start_amount_difference_plus` (18 keys; numbers, no strings; `avg_amount` has up to 2 decimals, `avg_price_sqm` is an integer; `status` `active` in all 4 rows). Nowy Targówek VI: 21 active of 75 offers, 17,646 PLN/m²; Warszawska 58A: 32 of 73, 16,123. There is no summary (`filteredStats`): the totals have to be computed from the rows. For the Warszawa page: 4 investments, Σ `active_offers` 60, offers-weighted mean of `avg_price_sqm` 16,110.4, which equals the `ceny-w-miastach` value of the same city below.
  - The cities: the first of 4 `spec` props is the chart `ceny-w-miastach` ("Ceny w miastach", `domain` `oferty`; sample `page.developer.v2_spec`), `views[""].rows` has one row per city of the developer, 14 for ATAL (as many as the 14 rows of `citiesStats` on 1.0): `key` (city slug), `label` (the city), `sub` (a display string with a Polish plural, `4 inwestycje`, `1 inwestycja`, `6 inwestycji`), `value` (mean PLN/m² of the active offers, integer), `text` (`16 110 zł/m²`, with no-break spaces), `extra` (the active offers as a **string**, `"60"`), `current` (true for the page's own city), `href` (`/ceny-ofertowe/{city}/deweloperzy/atal`, null when `current`) and `tip.rows` with `{key: cena|oferty|inwestycje, label, value}` whose `value` is a string (the count of investments is `tip.rows[key=inwestycje].value`, `"4"`). Rows are sorted by `value`, descending; `views[""]` also has `max`, `columns` (`{value: "Średnia", extra: "Oferty"}`), `reference`, `headline`, `table` (the last three null). Warszawa row: 4 investments, 60 active offers, 16,110.
  - The page has 4 `spec` props and the first is `ceny-w-miastach`, as in the HTML; the other three (HTML: `rozklad-metrazy`, `oferty-wg-metrazu`, `tempo-sprzedazy-wykres`) were not read from the RSC payload, nor were `timeline` (65 daily rows) and `sparseBySize` (60 rows): they are known only from the saved HTML [P 2026-10-30]. Since `find_json_after` returns the first occurrence, `--prop spec` is the cities chart only while this order holds.
- `{city}` filters the investments to that city; `polska` gives all cities (ATAL: 42 investments, 6587 `sale` rows, ~1.96 MB) [P 2026-10-13, raw fixtures `tests/fixtures/rsc/developer_atal_warszawa.rsc`, `developer_atal_polska.rsc`, consistency tests in the suite].
- Consistency in both fixtures [P 2026-10-13]: `filteredStats.totalProjects` = number of investments; `totalSales` = Σ `active_offers` = active rows in `sale`; Σ `total_offers` = len(`sale`); `totalCities` = number of cities of the investments; `averagePrice` = round(mean price of active offers); `averageSize` = mean area of active offers (±0.01); `avgAmountPerM2` = round(mean of investments' `avg_price_sqm` weighted by `active_offers`); per investment `total_offers`/`active_offers`/`avg_amount`/`avg_size` agree with `sale`. `citiesStats` is identical on the city page and the `polska` page (14 rows) and consistent with the investments; the Warsaw row equals the Warsaw page's `filteredStats`.
- `priceIncreaseCount`/`priceDecreaseCount` are 0 while the sums are non-zero: unreliable, not used (they stay unknown) [P 2026-10-13].
- A developer without active offers in that city gets 0 for every average: `filteredStats` is `{totalProjects: 0, totalSales: 0, totalCities: 0, averagePrice: 0, averageSize: 0, avgAmountPerM2: 0}` and `investments` is empty [P 2026-10-20, live: `/ceny-ofertowe/bialystok/deweloperzy/atal`; the same for `murapol` in `olsztyn` and `develia` in `lublin`]. A 0 is no value, not a price.
- Unknown developer (`/ceny-ofertowe/warszawa/deweloperzy/nieistniejacy-deweloper`), 1.0: HTTP 200, **no** `NEXT_HTTP_ERROR_FALLBACK;404` digest (unlike the offer list); h1 "Deweloper nie znaleziony", title "Deweloper nie znaleziony | Deweloperuch" [P 2026-10-13, fixture `developer_unknown_warszawa.rsc`]. The client had to detect this by the missing data / title.
- **Unknown developer on 2.0 [P 2026-10-31]: the 1.0 behaviour (no digest) is refuted.** The same URL answers `200 text/x-component`, 17,814 B, with the digest `NEXT_HTTP_ERROR_FALLBACK;404` (once), like an unknown city. Whether the heading text is also in the payload was not read; `error_digests()` is the indicator that was seen, so the "Deweloper nie znaleziony" heading need not be searched for.

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

### `/ceny-ofertowe/{city}/{district}/mieszkania`: district offer list [P 2026-10-31]
- `{district}` is an ASCII district slug (`mokotow`, `praga-poludnie`, `bialoleka`, `srodmiescie`), the `slug` of the props `items` (`{name, slug, href}`, 18 districts for Warszawa) of the city page and of `city-districts` [P 2026-10-30, saved scan page]. The saved 2.0 offer pages link districts in this path form (the props `items` and `districts`), and the 2.0 client builds this path for one district (chunk `5469`, module `1321`) [P z kodu 2026-10-30]. The siblings `/inwestycje`, `/deweloperzy` and `/mapa` of a district are linked too (see "Linked from the props" above); only the offer list is documented as a route here.
- `GET /ceny-ofertowe/warszawa/mokotow/mieszkania` (RSC, empty `_rsc`) → `200 text/x-component`, 76,267 B, no redirect [P 2026-10-31]. `serverPaginationData` is `{currentPage: 1, perPage: 25, totalCount: 959, totalPages: 20, startItem: 1, endItem: 25}` (sample `page.offers_list.v2_district_pagination`). The `sales` prop was not requested on this route; that it holds the district's rows (25, as on the city list, whose payload is 73,057 B) is [W].
- 959 equals the number of Mokotów offers in the offer snapshot of Warszawa the same day (the sales of the investments whose `district` is `Mokotów`, [endpoints.md](endpoints.md)): the route lists the district's active offers [P 2026-10-31].
- **It takes the place of `filterDistrict`**, which stopped working: on the city list `filterDistrict=Mokotów` (the name) and `filterDistrict=mokotow` (the slug) both answer `200 text/x-component` (27,316 B and 27,309 B) with no `sales` and no `serverPaginationData` (data props: `errorStyles`, `errorScripts`, `template`, `notFound`, `tytul`, `style`, `items`), a payload of the size of the not-found answers (25,189 B for an unknown city, 28,341 B for an unknown district). Whether the digest `NEXT_HTTP_ERROR_FALLBACK;404` is in it was not read [H] (T73). Refuted: `filterDistrict` as a working filter on the 2.0 city list [P 2026-10-10].
- Unknown district (`/ceny-ofertowe/warszawa/nieistniejaca-dzielnica/mieszkania`): `200 text/x-component`, 28,341 B, the digest `NEXT_HTTP_ERROR_FALLBACK;404` twice, like an unknown city [P 2026-10-31].
- Not requested on this route: the other parameters (sorting, the three ranges, `filterPriceChange`, `filterStatus`, `includeArchived`, `page`, `perPage`) and the `sales` rows (T73).

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
- 2.0: **308** to `/statystyki/{location}/dane-rzadowe` [P 2026-10-29, e2e]; the new page has `blocks`, several `data`, `monthlyData`, `spec`, `locativePhrase`, `anchorId`, `info`, and neither `sortedLocations` nor `tocItems` [P 2026-10-30, saved scan page]; see the 2.0 section. `get_government_statistics` is broken by this (T57); the redirects that broke it too are gone with the empty `_rsc` (T63).

### `/statystyki/portale-ogloszeniowe/{type}/{region}` [P]
- Data loaded client-side from `/api/announcement-stats`. The page contains only a skeleton and the region list.
- 2.0: **308** to `/statystyki/{region}/portale-ogloszeniowe` for `mieszkania/polska` [P 2026-10-30, scanner]; the target was not requested.

### `/statystyki/{location}/transakcje`: transaction statistics [P 2026-10-31]
- 200 in the scan of 2026-10-30 (`/statystyki/warszawa/transakcje`, 354,377 B of HTML). `{location}` is a city slug, `polska` or an aggregate (`7-miast`, `10-miast`, `6-miast-bez-warszawy`); the district form `/statystyki/{city}/{district}/transakcje` is linked from the props and was not requested.
- Old routes: `/statystyki/ceny-transakcyjne/mieszkania/{city}/mapa` answers 308 to this route (Warsaw) [P 2026-10-29, scanner]. The old `rawTransactions` page `/statystyki/ceny-transakcyjne/{mieszkania|domy}/{city}` was not requested, so whether it redirects here too is open (T55 a) [H]; it stays in `DUMP_PATHS` until the final cleanup (T61).
- Props [P 2026-10-30, saved scan page]: `view` (with the monthly series `monthly`, 118 rows for Warsaw), `priceChange`, `latestSummary`, `blocks`, `rawUrl`, `districts`, `statsDistrictPages`, … (the full list is in the table of 2.0 props above). It has no `rawTransactions`, so the page is **not** a D5 dump; the dump is the API path in `rawUrl`, `GET /api/statystyki/raw-transactions` ([endpoints.md](endpoints.md), listed in `DUMP_PATHS`).
- **RSC payload [P 2026-10-31]**, `warszawa`: `200 text/x-component`, 151,126 B (HTML 354,377 B), `cache-control: private, max-age=172800, must-revalidate`. `view` and `latestSummary` are equal to the saved HTML, row by row.
- `view` (sample `page.stats_transactions.v2_view`) is an object with `monthly`, `anchor` (`2026-Q1`, the last full quarter), `quarterly` (`current`, `prev`, `yearAgo`, each `{count, med_price_sqm, avg_price_sqm, med_size, avg_size, med_amount, avg_amount}`, and the labels `quarterLabel`, `prevQuarterLabel`, `yearAgoQuarterLabel`), `priceChange` (null here), `slices`, `segmentSeries` (40 quarters), `brackets`.
  - `monthly` has **118 rows, 2017-01 to 2026-10, one per month without a gap**, so it runs to the current month, with the months that have no transactions filled with zeros. A month with data has 10 keys: `month`, `transaction_count`, `secondary_count`, `unknown_count`, `med_price_sqm`, `avg_price_sqm` (integers), `med_size`, `avg_size` (one decimal), `med_amount`, `avg_amount` (integers). A month without transactions has **8**: no `secondary_count` and no `unknown_count`, and every other measure 0 (Warszawa: 2026-06, 2026-08, 2026-09, 2026-10).
  - Market and property type: **the secondary market of flats only**. In all 114 months with data `secondary_count` equals `transaction_count` and `unknown_count` is 0. The page text begins „Mediany cen transakcyjnych mieszkań w Warszawie na rynku wtórnym z aktów notarialnych: …” (the prop `lead` of the saved HTML), `propertyType` is `mieszkania` and `isMixedMarket` is false; the client labels such a series „rynek wtórny” (chunk `6760`, default `marketLabel`) [P z kodu 2026-10-30]. The primary market is not in this series.
  - Tail (Warszawa): 2026-03 1,388 transactions; 2026-04 986; 2026-05 22; 2026-06 0; 2026-07 35 (`med_price_sqm` 33,176, twice the months before); 2026-08, 2026-09 and 2026-10 0. The same figures as the saved HTML of 2026-10-30, so the recent months did not move in a day. `quarterly.current` (2026-Q1) counts 3,643, the sum of its 3 months 3,641 (T46).
- `latestSummary` (sample `page.stats_transactions.v2_latest_summary`): the row of the last month the page treats as complete, here **2026-04** (986 transactions, `med_price_sqm` 16,558), with the same 10 keys; it equals the 2026-04 row of `view.monthly`. The months after it (2026-05 with 22 transactions, and later) are probably the ones the RCN feed has not filled yet [W]. What rule picks the month is unknown [H]; the 1.0 notes of this file call it the last full month.
- Query parameters: `filterMarket=pierwotny` leaves `view` **unchanged** (the same 151,126 B, equal field by field) [P 2026-10-31]: the market filter works on the client only. [P z kodu 2026-10-30] chunk `1519` shows the notice „wybór „Oba rynki” / „Pierwotny” przelicza tylko mapę i wykres pojedynczych transakcji”, and the values are `oba` and `pierwotny` (anything else is the default, the secondary market `wtorny` [W]). The other query parameters of the page (`filterPrice`, `filterSize`, `filterRooms`, `filterDistrict`, `filterPowiat`, `filterPolygon`, `filterClassification`, `filterFloor(s)`, `filterLastTransactionDate`, `filterDateFrom`, `filterDateTo`, `filterStreet`, `type`, `dzielnica`, `miasto`, `powiat`, `typ`) are read by the client from the dump; they were not requested.
- The property type is **a path segment**, not a query parameter: `/statystyki/{location}/transakcje/domy` is the page for houses and `/statystyki/{location}/transakcje` the one for flats [P z kodu 2026-10-31, chunk `2432`, module `37295`: the route builder appends `/{subject}` for `domy`, and `transakcje` accepts `mieszkania` and `domy`]. That route is not in `PAGE_ROUTES`, so it was not requested; whether its `view.monthly` is the house series is open (T75).
- Unknown location (`/statystyki/nieistniejace-miasto/transakcje`): **HTTP 404 with `text/x-component`**, 25,204 B, `cache-control: private, max-age=172800, must-revalidate`, `cf-cache-status: MISS` [P 2026-10-31]. It is not the `200` with the digest of the offer list: the status is the signal. `probe` prints only 300 characters of a non-2xx body: it starts with flight rows (`1:"$Sreact.fragment"`, `2:I[98202,…,"GoogleTagManager"]`), so whether an `E` row with the 404 digest is inside was not read [H] (T36).

### `/statystyki/{location}/dane-rzadowe`: GUS + NBP [P 2026-10-31]
- 200 in the scan of 2026-10-30 (`/statystyki/warszawa/dane-rzadowe`, 608,055 B of HTML). The old route `/statystyki/statystyki-rzadowe/{location}` answers 308 to it [P 2026-10-29, e2e; also for an unknown location]. `{location}` is a city slug, `polska` or an aggregate, as on the transactions page.
- Props [P 2026-10-30, saved scan page]: `blocks {ld, oferty, rcn, portale, gus, nbp, govSections}`, several `data` told apart by shape (87 quarterly construction rows, 21 age-cohort rows, 80 NBP rows), `monthlyData` (260 monthly construction rows), several `spec` chart specs, `locativePhrase`, `anchorId`, `info`, `citySlug`, `cityName`; neither `sortedLocations` nor `tocItems` (the full row is in the table of 2.0 props above).
- **RSC payload [P 2026-10-31]**: `200 text/x-component`, `cache-control: private, max-age=172800, must-revalidate`. The data props (name, size) as `probe page` lists them, in the order of the stream:

| Location | RSC bytes | Data props |
|---|---|---|
| `warszawa` | 376,989 (HTML 608,055) | `blocks` (7 keys), `data` 87, `monthlyData` 260, `spec` 12 keys, `spec` 11, `info` 2, `data` 21, `spec` 10, `info` 4, `data` 80 |
| `7-miast` | 389,689 | `blocks` (7), `data` 87, `monthlyData` 260, `spec` 12, `spec` 11, `info` 2, `data` 21, `spec` 9, `data` 80 |
| `polska` | 625,434 | `blocks` (7), `data` 87, `monthlyData` 260, `spec` 12, `data` 21, **`seriesList` 4, `tableRows` 7, `miniCharts` 6, `mobileTop3` 3**, `spec` 11, `info` 2, `spec` 9; **no `data` with the 80 NBP rows** |

- Shapes: `data` 87 = quarterly construction rows `{quarter, oddane*, rozpoczete*}` (2005-Q1…), `data` 21 = age cohorts `{year, cohorts, totalKobiety, totalMezczyzni}`, `data` 80 = NBP quarters `{quarter, pierwotnyOfertowa, pierwotnyTransakcyjna, wtornyOfertowa, wtornyTransakcyjna}` (2006-Q3…), `monthlyData` 260 = monthly construction rows `{month, oddane*, rozpoczete*}` [P 2026-10-30, saved page; the sizes 87, 21, 80 and 260 were seen again in the RSC payload]. The number and order of the `data` and `spec` props depend on the location: the third `spec` has 10 keys on `warszawa` (the wages chart `gus-wynagrodzenia-roczne-wykres`, [P 2026-10-30, saved HTML]) and 9 on `7-miast` and `polska`, `warszawa` has a second `info` (4 elements) that `7-miast` lacks, and **`polska` has no `data` array of NBP rows**: its national overview is made of `seriesList` (4), `tableRows` (7), `miniCharts` (6) and `mobileTop3` (3), whose shape was not read (T74). A reader that tells the `data` props apart by shape and expects the three of Warszawa fails on `polska`.
- `blocks.govSections` (RSC payload of `warszawa`, sample `page.stats_gov.v2_sections`): `["gus-mieszkania", "gus-formy-budownictwa", "gus-srednia-powierzchnia", "gus-demografia", "gus-wiek", "gus-bezrobocie", "gus-wynagrodzenia", "nbp"]`, 8 ids in this order (the sample keeps 3 by the sample convention), the same as in the saved HTML. They are the old `tocItems` ids [P 2026-10-30]. `govSections` of `polska` and `7-miast` was not read [H].
- The section ids as anchors [P 2026-10-31, the saved HTML of `/statystyki/warszawa/dane-rzadowe`, read offline]: all 8 are the `id` of an element of the page (`id="gus-mieszkania"` …, once each), and 7 of them are also an `anchorId` prop (all but `gus-mieszkania`). The `get_government_statistics` link can use them as `#section`. Not checked on `polska` or `7-miast`.
- Unknown location (`/statystyki/nieistniejace-miasto/dane-rzadowe`): **HTTP 404 with `text/x-component`**, 24,757 B, `cache-control: private, max-age=172800, must-revalidate`, `cf-cache-status: MISS` [P 2026-10-31]: the same kind of answer as the unknown location of `transakcje`. The old route answers such a location with a 308 to this one [P 2026-10-29, e2e], so the unknown location is a 404 only at the new address.

---

## Other

### `/zglos-dewelopera/mapa-zgloszen` [P]
- Props: `developerAbuseData[]` (105): `{developer_abuse_id, name, slug, developer, website, latitude, longitude, violations[], additionalInfo}`, that is reports of violations of the price transparency act.
- No sample is kept: the reports are user-submitted texts naming companies.
- 2.0: **410 Gone** for this page and for `/zglos-dewelopera` [P 2026-10-30, scanner]; the report-a-developer feature and its Turnstile form are gone. The route is still in `allowlist.PAGE_ROUTES`.
