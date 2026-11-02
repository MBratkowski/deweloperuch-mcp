# Catalog of JSON endpoints (`/api/*`) and server actions

All endpoints: `GET`, same-origin `https://deweloperuch.pl`, no session/cookies, `application/json` response. Status [P] means the endpoint was called and the response saved in `samples/api.<file>.json`. Parameters marked (UI) are sent by the client code; their effect was not always tested separately.

**2.0 redesign (deployed 2026-10-29, build `VDpA73sQ-GRMsEMdmIQtu`, Next.js 15.5.25).** The entries below come from the survey of 2026-10-09 (build `KD_IOP6Grqba7xa86pGVG`); an entry that was re-checked on the 2.0 service carries `[P 2026-10-29]` (live e2e run), `[P 2026-10-30]` (probe, with a sample) or `[P 2026-10-31]` (probe, a raw fixture of `tests/fixtures/`, or the live e2e of the repaired tools) in a `2.0` bullet. What changed:
- 4 paths answer 404: `offers/city-sales`, `monthly-transaction-stats`, `map/powiat-stats` and `investments/{investId}/sale-events` (the last one is replaced by the `ev` field of `map/investments/visible/{slug}`).
- 7 more of the 34 baseline paths are no longer referenced by the 2.0 client; of these, `avg-price-trend/city` and `avg-price-trend/building` still answer 200, the other 5 were not requested. Section 8 lists all 11.
- 14 new paths appear in the client: 10 in the table of section 7 (none requested yet), and 5 promoted to headings: 2 on 2026-10-30, `map/offer-snapshot/{citySlug}` (section 2, D20; requested on 2026-10-31, shape and sizes known) and `statystyki/raw-transactions` (section 3, a D5 dump, never requested), and 3 on 2026-11-01, `map/tx-cities` and `statystyki/powiat-map-stats` (section 3) and `statystyki/gov-map-stats` (section 4; found in neither the table nor the first survey), all three requested once on 2026-11-01 [P 2026-11-01]; 5 existing paths gained fields or parameters (`cities`, `city-districts`, `investments`, `map/investments/visible`, `city-lookup`).
- A 404 means one of two things, told apart by its media type [P 2026-10-30, section 9]: an unknown entity on a live JSON route is `404` + `application/json` + `{"error": "<text>"}` (unknown investment, RCN building and city); a removed route is `404` + `text/html`, the Next.js not-found page (36,628 B, build comment `VDpA73sQ_GRMsEMdmIQtu`, 4 routes), also when the request asks for JSON. One route answers an unknown id with `200` instead: `sale-events` (`saleData: null`).
- Cache headers changed: all 11 JSON responses probed on 2026-10-30 send `public, max-age=28800, s-maxage=N, stale-while-revalidate=M` (N from 300 to 86400, see the entries); on 2026-10-09 several of these endpoints had `max-age=28800` only. In a second series later the same day every response (JSON 200, JSON 404, HTML 404) carried `max-age=172800` instead, with `s-maxage` unchanged [P 2026-10-30]; both values are presets of a CDN "browser cache TTL" setting, so this is probably a CDN setting, not the application [W]. The client caps its TTL at 300 s (D2), so no code changes.
- Tools repaired on 2026-10-31 [P 2026-10-31, live e2e: three runs, 116 requests, no STOP; every test passes except three expected xfails]: `get_market_statistics` reads `map/offer-snapshot/{citySlug}` (D20), the history of `get_investment` reads the `ev` field of `map/investments/visible/{slug}`, and the months of `get_transaction_statistics` come from the page `/statystyki/{city}/transakcje` ([pages-rsc.md](pages-rsc.md)), so three of the four removed routes above no longer break a tool. `rank_locations` over counties has no route yet: `map/powiat-stats` is a 404, the two powiat-level tests are the expected xfails and the tool answers „service changed” (D21, T58).
- Sections 7 and 8 are tables, not `` ### `GET /api/...` `` headings, on purpose: `tests/recon_scripts/test_probe_allowlist.py` pairs every such heading with `allowlist.API_PATHS`. Promoting a path from section 7 to a heading and to `API_PATHS` is one change: the heading here first, then the allowlist counterpart in code. The two promoted on 2026-10-30 (`map/offer-snapshot/{citySlug}`, `statystyki/raw-transactions`) have their `API_PATHS` entries since 2026-10-31 (`raw-transactions` also in `DUMP_PATHS`); the three promoted on 2026-11-01 (`map/tx-cities`, `statystyki/powiat-map-stats`, `statystyki/gov-map-stats`) since the same day.

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
- 2.0 [P z kodu 2026-10-30] (chunks `2432`, `6535`): the client sends `city=<name>` to get a slug and `slug=<slug>` (trimmed, lowercase) to get a name, each with `&source=transactions` for the transaction dictionary, and treats a falsy `city_slug` / `city` in the reply as "not found". Replaced by the probes below.
- **Unknown name** [P 2026-11-01, `api.city_lookup.unknown`]: `city=Nieistniejacemiasto&source=transactions` → **200**, 30 B, `{"city": null, "city_slug": null}` (both null, not a 404). Cache-Control `public, max-age=172800, s-maxage=86400, stale-while-revalidate=604800`, MISS. So "not found" is a 200 with null fields.
- **Village** [P 2026-11-01]: `slug=ignatki-osiedle` (no `source`) → 200, 56 B, `{"city": "Ignatki-Osiedle", "city_slug": "ignatki-osiedle"}`; the same with `&source=transactions` → 200, 56 B, `{"city": "Ignatki-osiedle", "city_slug": "ignatki-osiedle"}` (`api.city_lookup.village_transactions`). Both answer with a name, and the capitalisation differs (`-Osiedle` against `-osiedle`): the offers variant title-cases each part of the slug, the transactions variant returns the register's name [W]. So the offers dictionary does not reject a slug it does not hold (it derives a name from it), and a null answer cannot be read as "no offers there" [W]; to test existence use the transactions source or `map/tx-cities`.
- Sample: `api.city_lookup.json`, `api.city_lookup.slug_transactions.json`, `api.city_lookup.unknown.json`, `api.city_lookup.village_transactions.json`

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
- **Offers variant has `slug` too** [P 2026-11-01, `api.city_districts.offers_v2`]: `citySlug=warszawa` → 200, 917 B, `{districts: [{name, slug, count}]}`, 18 districts sorted descending by `count` (Białołęka `bialoleka` 2,729, Praga-Północ `praga-polnoc` 990, Mokotów `mokotow` 959, Targówek, Bemowo, Włochy, Praga-Południe `praga-poludnie` 719, Ursus, Ursynów, Wola, Bielany, Ochota, Śródmieście `srodmiescie` 245, Rembertów, Wawer, Wilanów, Wesoła, Żoliborz `zoliborz` 41). Every one of the 18 slugs equals a plain local transliteration of the name (lowercase, Polish letters to ASCII, non-alphanumerics to `-`, collapsed), so none differs [P]. Cache-Control `public, max-age=172800, s-maxage=300, stale-while-revalidate=86400`, MISS. Only Warszawa was checked; other cities' hyphenated or multi-word names (Kraków's `lagiewniki-borek-falecki` fits the same rule) are not proof for the rest [W].
- Sample: `api.city_districts.json`, `api.city_districts.transactions.json`, `api.city_districts.offers_v2.json`

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
- **2.0: HTTP 404** [P 2026-10-29, live e2e of the package client: a valid city and an unknown city both give 404, so the route is gone]; absent from all 97 chunks of the 2.0 client read by the scan (section 8). `get_market_statistics` was broken by this and is repaired: it reads `map/offer-snapshot` (D20, next entry; [P 2026-10-31, live e2e]).
- 2.0 [P 2026-10-30, `krakow`]: `404`, `text/html`, 36,628 B, the Next.js not-found page (the body starts `<!DOCTYPE html><!--VDpA73sQ_GRMsEMdmIQtu--><html lang="pl"><head>`), `cache-control: private, max-age=172800, must-revalidate`, `cf-cache-status: REVALIDATED`; no sample (non-2xx). A removed route, not an unknown city (section 9). D20 replaces it with `map/offer-snapshot/{citySlug}` (next entry).
- Sample: `api.city_sales_sopot.json`

### `GET /api/map/offer-snapshot/{citySlug}` [P 2026-10-31]
- **Bulk list of a city's active offers**, read by the 2.0 client; D20 makes it the source of `get_market_statistics` and `stats market` for one city in place of `offers/city-sales/{citySlug}` (404). As under D15 the body stays inside the process and outputs carry aggregates only. A read channel, and an internal route of the service that may change without notice.
- Evidence in the client [P z kodu 2026-10-30]: chunk `6760` (module `86840`, function `wM`) decodes it and the statistics page chunk requests it; the client's query key is `["analiza", "offer-snapshot", …]` and it keeps the reply for 6 h. The client names the path segment `location` (the statistics page's location slug) and does not request it for `polska`; D20 passes one city's slug and refuses `polska` before any request. The decoder reads `investments[]` by `id`, and per sale the positions 0, 1, 3, 4 and 5 of a tuple; it treats every sale as active.
- **Response [P 2026-10-31]** (`sopot`, 880 B, sample `api.offer_snapshot.sopot`; `warszawa`, 532,198 B; `wroclaw` [P 2026-10-30, PR #16], 261,340 B, sample `api.offer_snapshot.wroclaw`): `200`, `application/json`, an object with 4 keys, in this order:
  - `citySlug`: the requested slug (`"sopot"`, `"warszawa"`). `asOf`: `"YYYY-MM-DD"`, the day of the data (`"2026-10-31"` in both).
  - `investments`: `[{id, slug, name, street, lat, lng, district, developerId, developer, developerSlug}]`. `id` is the `invest_id` (integer), `lat` and `lng` are numbers, `street` and `district` are strings that may be `""` (Sopot: `district` is `""` for both investments; Warszawa: for 1 of 268), `developer` is the developer's name, `developerId` an integer. Warszawa: 268 investments, 100 developers, 19 distinct `district` values including `""` (`Białołęka` 2,706 offers, `Praga-Północ` 990, `Mokotów` 959 …).
  - `sales`: `[[id, investId, flag, amount, pricePerM2, size, startDifference], …]`, tuples of 7 numbers, no keys:

    | Index | Meaning | Type | Evidence [P 2026-10-31] |
    |---|---|---|---|
    | 0 | `sale_id` of the offer | int | the 125 offers read from the Warszawa offer list (the first 25 in the default order and the 100 dearest) are all found by this id |
    | 1 | `invest_id` of its investment: `investments[].id` | int | all 11,672 Warszawa sales resolve; 125 of 125 equal `invest.invest_id` of the list row |
    | 2 | **constant `0`**, meaning unknown (the client ignores it) | int | 0 in 11,672 of 11,672 Warszawa rows and 8 of 8 Sopot rows (T76) |
    | 3 | asking price, PLN (`amount`) | int | 125 of 125 equal `amount` of the list row |
    | 4 | price per m², PLN: `amount / size` rounded to 2 decimals (largest deviation 0.005) | int or float: a whole value is an integer (`34500`), 6,253 of 11,672 | 11,672 of 11,672; the list has no such field |
    | 5 | area, m² (`size`) | int or float (213 of 11,672 are integers) | 125 of 125 equal `size` of the list row |
    | 6 | `start_amount_difference`: the price minus the first asking price, PLN; negative = cheaper than at the start | int, or float in 81 of the 11,672 Warszawa rows | 125 of 125 equal `start_amount_difference` of the list row, and different from `last_amount_difference` in 38 of the 125; 2,167 rows are negative, 3,297 positive, 6,208 zero (the 81 fractions included; none of them is whole-valued: `-59696.59` of offer 98457, `-58338.99`, `8189.48` …; the 8 Sopot rows are integers) [P 2026-10-31, `offer_snapshot_warszawa_20261031.json`], and the offer list has 2,167 offers for `filterPriceChange=decrease` |

  - What the snapshot does **not** have: the offer's name, `status`, `last_event_type`, dates, `total_events`, the percent differences, and any price history. The investment of an offer is `investments[]` with `id` = tuple position 1; the developer's name and slug come with the investment (`developer`, `developerSlug`), the district of the offer is the investment's `district` (a name such as `Mokotów`).
  - What the package reads [P z kodu 2026-10-31, `offer_snapshot_dto.py`, `offer_snapshot_api.py`]: per sale the positions 0, 1, 3 and 5 (offer id, investment id, price, area) of a row of exactly 7 items (another length is a changed service, D21); per investment `id`, `slug`, `developerSlug` and `developer`; `asOf` only to show. It does not read positions 2, 4 and 6, so the fractions of position 6 matter to nothing, and it compares `citySlug` with the slug asked for: another city is a changed service, never the market of the city asked for. A fractional position 6 (offer 98457: price 686,646, difference -59,696.59) means that the first price had a fractional part [W].
  - Sopot, in full (8 offers of 2 investments, 880 B): `{"citySlug":"sopot","asOf":"2026-10-31","investments":[{"id":33,"slug":"smolna","name":"Smolna","street":"Świemirowo","lat":54.42735985,"lng":18.55839032,"district":"","developerId":32,"developer":"Invest Komfort Spółka Akcyjna Sp.K.","developerSlug":"invest-komfort-spolka-akcyjna"},{"id":1276,"slug":"nowe-kolibki-etap-4",…}],"sales":[[206523,33,0,3735107,39115.16,95.49,0],[2386,33,0,1399534,26164.4,53.49,-10466],[2377,33,0,1620768,24423.87,66.36,768],[206087,33,0,1679796,25490.08,65.9,0],[69910,1276,0,1655442,25733.59,64.33,-134558],[69931,1276,0,1579968,24288.52,65.05,-100032],[206136,1276,0,1612949,27040.22,59.65,198],[206648,1276,0,1261250,25882.41,48.73,0]]}`.
- **Completeness [P 2026-10-31]**: Warszawa has **11,672 sales**, exactly the `serverPaginationData.totalCount` of `/ceny-ofertowe/warszawa/mieszkania` on the same day (active offers; the `city-sales` of Kraków had 18 more than the list on 2026-10-13, for Warszawa the snapshot and the list agree exactly), and the 959 sales of investments with `district` `Mokotów` equal the `totalCount` of the district route. So the snapshot is the list of the city's **active** offers and it is complete for a city; archived offers are not in it (`filterStatus=archived` lists 12,471 of them on the offer list, and `includeArchived=true` 34,011 offers in all, T72). Every investment has at least one sale and every sale's investment is listed; sale ids are unique and not sorted; no sale has a zero or missing price, area or price per m².
- Size: Sopot 880 B, Warszawa 532,198 B (compact JSON, no whitespace; `city-sales` of Warszawa was 1.3 MB, with objects in place of tuples): about 46 B per sale counting the investments.
- Cache: `public, max-age=172800, s-maxage=3600, stale-while-revalidate=86400`; `cf-cache-status: EXPIRED` (`sopot`), `HIT` with `age` 37,703 s (`warszawa`): the CDN may serve a copy more than half a day old, so `asOf` is the date to show, not the date of the request.
- Unknown city: `404`, `application/json`, 24 B, `{"error":"Unknown city"}`, `cache-control: public, max-age=172800, s-maxage=3600`, `cf-cache-status: HIT`, `age` 53,556 s (section 9). By the 404 rule this reads as an unknown entity; no HTML 404.
- Not requested: `polska` and the aggregates (`7-miast`, …; the client does not ask for them) [H], and (by probe) a large city other than Warszawa; `krakow` was read by the live e2e instead [P 2026-10-31, live e2e]: `get_market_statistics` of Kraków and `stats market sopot` accept every 7-item row of their snapshots. `krakow` was replaced by `warszawa` in round B2: the largest city is the upper bound for the tool, and its rows could be compared with the offer-list rows captured the same day (no extra request).
- Sample: `api.offer_snapshot.sopot` is trimmed by the sample convention (3 sales, each tuple cut to its first 3 items and `"... (4 more, 7 total)"`), so the amounts and areas are **not** in it; the shape above and the full Sopot body are the reference. The raw fixtures `tests/fixtures/api/offer_snapshot_sopot_20261031.json` (880 B) and `offer_snapshot_warszawa_20261031.json` (532,198 B), byte-exact, captured through the package client on 2026-10-31, are what the contract tests of `get_market_statistics` read (`tests/fixtures/api/README.md`); the position 6 counts above were made on them.

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
- Unknown slug: `HTTP 404 {"error":"Investment not found"}` [P 2026-10-10, no sample because non-2xx]. Cache-Control `max-age=28800` for the 404 as well. 2.0: still 404 for an unknown slug [P 2026-10-29, live e2e]. 2.0 [P 2026-10-30, slug `nieistniejaca-inwestycja-e2e`]: `404`, `application/json`, 32 B, `{"error":"Investment not found"}`, `cache-control: max-age=172800` (no `public`, no `s-maxage`), `cf-cache-status: HIT`, `age: 63943` (probably the copy cached by the e2e run of 2026-10-29 [W]); no sample (non-2xx). This is the JSON 404 of section 9.
- **2.0 shape [P 2026-10-30, `api.map_inv_visible.v2` and `api.map_inv_visible.no_v`]**, slug `nowy-czechow` (investment 447, Lublin, 80 active of 127 offers), 200, 50,338 B: the top level has a new key `description` (string, `""` here) after `currency`; every `sale[]` row has two new keys after `creation_date`: `floor` (string; `""` on all 47 archived rows and a floor number as text on all 80 active rows) and `ev` (the price events, below). All other keys and types are as listed above (`sale_id` and `invest_id` integers, `amount`, `size`, `start_amount_difference(_percent)` strings).
- `ev` is the offer's price history in compact form: an array of 4-element arrays `[date "YYYY-MM-DD", amount (integer), event type index, source index]`, ascending by date (346 events in the 127 offers, 2 to 7 per offer). Decoding [P z kodu, module `80026` in chunks `6994` and `4010`]: type 0 `OFFER_EVENT`, 1 `ARCHIVED_EVENT`, 2 `RESTORED_EVENT`; source 0 `ANNOUCMENT_PR`, 1 `ANNOUCMENT`, 2 `ANNOUCMENT_OD`, 3 `DANEGOVPL`, 4 `archive_stale_sales`, 5 `""`. [P 2026-10-30] Offer 33103 (7 events): the decoded `ev` equals `/api/sale-events?saleId=33103` event for event (date, amount, type, source; `api.sale_events.v2`). Indexes seen in this investment: types 0, 1, 2 and sources 0, 1, 4, 5; indexes 2 and 3 (sources `ANNOUCMENT_OD`, `DANEGOVPL`) appear only in the code. Across all 127 offers: the first event's amount = `amount` − `start_amount_difference`, the last event's amount = `amount`, an active offer ends with `[…, 0, 0]` (an `OFFER_EVENT` from `ANNOUCMENT_PR`), an archived one with an `ARCHIVED_EVENT` (`[…, 1, 4]` in 16 offers, `[…, 1, 5]` in 31). `ev` carries no `sale_event_id` and no `event_data`; the client numbers the events 0, 1, … itself (chunk `6994`). The sample keeps 3 elements per array (sample convention), so each `ev` row shows its 4th item as `"... (1 more, 4 total)"`.
- `?v=2` [P 2026-10-30]: the 2.0 client sends `?v=2` for the offer detail (chunk `6994`) and nothing on the map page. A request with and one without `?v=2` return the same body (127 offers, 50,338 B, every field equal, `ev` and `floor` in both). So the version marker changes nothing for this slug [W: probably a cache-busting marker], and the package's adapter, which sends no `v`, already receives `ev`.
- What the package reads for `get_investment` with `include_history` [P z kodu 2026-10-31, `investment_price_events_dto.py`; live e2e [P 2026-10-31] passes]: per offer `sale_id` and `ev`, and of each `ev` row the positions 0, 1 and 2 (date, amount, event type index 0 to 2); the source index (position 3) is not read, so its values never seen (T68) block nothing. A type index outside 0 to 2 or a row of fewer than 3 items is a changed service, and an offer without `ev` is another answer (the one before 2.0), not an offer without history. A whole answer [P 2026-10-31, `tests/fixtures/api/map_inv_visible_smolna_20261031.json`], `smolna` (investment 33, Sopot): 17 offers (4 active, 13 archived) and 38 `ev` rows (1 to 5 per offer; types 0, 1 and 2 in 21, 15 and 2 rows; sources 0, 1 and 5 only, never 2, 3 or 4); in all 17 offers the first row's amount is `amount` − `start_amount_difference`, the 4 active offers end with `[…, 0, 0]` and the 13 archived with `[…, 1, 5]`.
- 2.0 Cache-Control [P 2026-10-30]: `public, max-age=28800, s-maxage=3600, stale-while-revalidate=86400`, `cf-cache-status: HIT` (`age` 12,153 with `?v=2`, 58,980 without it: separate cache entries).
- Sample: `api.map_inv_visible.json`, `api.map_inv_visible.v2.json`, `api.map_inv_visible.no_v.json`

### `GET /api/investments/{investId}/sale-events` [P]
- Price event history of **all offers of an investment**: `{ "<sale_id>": [{sale_event_id, event_type, event_data, amount, event_date, source}] }`
- Slow on cache MISS (~3 s). Sample: `api.inv_sale_events.json`
- **2.0: HTTP 404, HTML** [P 2026-10-30, `/api/investments/447/sale-events`, a valid `invest_id` taken from `map/investments/visible/nowy-czechow`]: `text/html`, 36,628 B (the Next.js not-found page; its build comment is `VDpA73sQ_GRMsEMdmIQtu`), `cache-control: private, max-age=28800, must-revalidate`, `cf-cache-status: MISS`; no sample (non-2xx). The body is an HTML page, not the JSON `{"error": ...}` of an application 404, so the route handler is gone, not just this id [W]. The 2.0 client does not call it either: it builds the same map from the `ev` field of `map/investments/visible/{slug}` ([P z kodu], chunk `6994`: `{"<sale_id>": [{sale_event_id: <index>, event_type, event_data: "", amount (string), event_date, source}]}`). `get_investment` with `include_history` was broken by this and reads `ev` of `map/investments/visible/{slug}` since 2026-10-31 (no extra request; [P 2026-10-31, live e2e]).

### `GET /api/sale-events?saleId=` [P]
- History of a single offer: `{ success, saleData: {name, amount, size, currency}, events: [...] }`
- Unknown `saleId` (e.g. 999999999): `HTTP 200 {"success": true, "saleData": null, "events": []}` [P 2026-10-10, no sample]. `success: false` was not observed (none of the inputs used triggered it); its meaning is still [H]. A missing offer is recognized by `saleData: null`.
- 2.0 [P 2026-10-30, `api.sale_events.unknown`]: `saleId=999999999` → still `200`, `application/json`, 44 B, `{"success":true,"saleData":null,"events":[]}` (the compact form; probe prints it indented), `cache-control: public, max-age=172800, s-maxage=3600, stale-while-revalidate=86400`, `cf-cache-status: MISS`. So this route answers an unknown id with a 200, unlike the 404 JSON of the other routes (section 9); `success` stays `true` (T31).
- `saleId=1` is **not** an unknown id [P 2026-10-31, no sample]: `200`, `application/json`, 397 B, `cache-control: public, max-age=172800, s-maxage=3600, stale-while-revalidate=86400`, `cf-cache-status: MISS`. `saleData` is `{name: "12.16", amount: "1950000", size: "60.27", currency: "PLN"}` and `events` has 2 rows: an `OFFER_EVENT` (`sale_event_id` 142376, amount `"1950000"`, `event_date` `2025-02-25T00:00:00.000Z`, source `ANNOUCMENT`) and an `ARCHIVED_EVENT` (`sale_event_id` 508443, the same amount and day, source `""`). So the first sale id exists (an archived offer); the unknown-id checks of 2026-10-10 and 2026-10-30 used `999999999`, and a small id is not a safe "unknown" example.
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
- **2.0: HTTP 404** [P 2026-10-29, live e2e of the package client]; absent from the 2.0 client (section 8). [P 2026-10-30]: `404`, `text/html`, 36,628 B, the same Next.js not-found page, `cache-control: private, max-age=172800, must-revalidate`, `cf-cache-status: HIT`, `age: 14346`; no sample (non-2xx). `rank_locations` over counties is broken [P 2026-10-31, live e2e: the two powiat-level tests are the expected xfails, the tool answers „service changed”, D21]. A candidate replacement is `/api/statystyki/powiat-map-stats` (below), 380 counties over a 12-month window [P 2026-11-01] (T59).

### `GET /api/map/tx-cities` [P 2026-11-01]
- No query string (the client sends none; any query string reportedly gives 404, not tested here [H]). Query key `tx-city-index`, client cache 30 min [P z kodu].
- 200, `application/json`, **3,300,101 B**, `{"cities": [...]}`: **16,283 rows**, no other top-level key. Cache-Control `public, max-age=172800, s-maxage=3600, stale-while-revalidate=86400, stale-if-error=86400`, `cf-cache-status: HIT`, `age` 112,822 s. Too large for a model: a place index for code, never for tool output.
- Row (all 13 keys in every row): `slug`, `name`, `lat`, `lng`, `flats`, `houses` (integers), `fSqm`, `fAmt`, `hSqm`, `hAmt` (integers or `null`), `powiatId` (integer, never null), `powiat` (string such as `powiat Warszawa`, `powiat białostocki`; never empty, one name per id), `ambiguous` (boolean). Example: `{"slug": "warszawa", "name": "Warszawa", "lat": 52.2333, "lng": 21.0081, "flats": 375082, "houses": 11908, "fSqm": 15705, "fAmt": 765890, "hSqm": 10744, "hAmt": 1720000, "powiatId": 302, "powiat": "powiat Warszawa", "ambiguous": false}`.
- **The index lists every RCN place with at least 5 transactions** (flats + houses; the smallest row has exactly 5; 1,561 rows have 5, 6,662 at most 10, 10,764 at most 20, 373 at least 1,000). Rows with 1 or 2 transactions, which the city ranking has in the thousands, are not here.
- `slug` is `name` transliterated to ASCII in 16,282 of 16,283 rows; exception `Tarnobrzeg` (capital T, not ASCII-lowercase) [P]. 13 rows have a postal-code or TERYT-like name and slug (`08-500-ryki`, `1812032-jezowe`, `0261011jelenia-gora-miasto` named `026101_1,jelenia Góra - Miasto`, `21-040-swidniik` next to `21-040-swidnik`): typos and import noise of the register [P]; they are not places to offer in a search.
- **`ambiguous`: 4,154 rows are `true`, and exactly those share their slug with another row**: 1,601 slugs occur more than once, 4,154 rows in all; no `ambiguous: false` row has a duplicate slug. So a slug alone does not identify a place; the pair (`slug`, `powiatId`) does [P]. 380 distinct `powiatId`, every one also a row `id` of `statystyki/powiat-map-stats` (no id unmatched either way).
- **`flats` and `houses` are counts over the whole RCN history; `fSqm`/`fAmt` and `hSqm`/`hAmt` look like a recent window, not the whole history** (the second part [W]):
  - Warszawa `flats` 375,082 + `houses` 11,908 = **386,990**, exactly the `transaction_count` of the ranking page (endpoints entry of `city-transaction-stats`); Kraków 245,629 + 2,567 = **248,196**, exactly `cities?variant=transactions` of 2026-10-30. So `flats + houses` is the all-time count that those two figures give [P 2026-11-01]; `flats` alone is a flats-only count (Kraków's `cities` count includes houses).
  - It is not the quarter of `city-transaction-stats` (Warszawa 3,606; Kraków 1,493): for the 1,928 unambiguous slugs present in both, `flats + houses` equals the ranking `transaction_count` in none [P].
  - `fSqm` (a price per m²) is not any known price: Warszawa 15,705 against ranking `avg_price_sqm` 16,413, page `oba.m2` 15,903 (powiat 302 in `powiat-map-stats`); Kraków 14,370 against 14,607 and 14,940. Among the 79 unambiguous places with at least 5,000 transactions the median difference to the ranking price is 6.4 %, the largest 23.5 % [P]. `fAmt` / `fSqm` is 48.77 m² for Warszawa, close to the typical size, so `fAmt` is probably an amount for the same population (mean or median unknown) [W].
  - `fSqm` is `null` in 8,888 rows, **including 2,906 rows that have `flats` > 0 (up to 641 flats)**, and `fAmt` is `null` exactly when `fSqm` is (no row has `fAmt` null with `fSqm` set). A place with hundreds of historical flats and no value therefore has no transactions in the window; this is why the window is [W], whose length is unknown [H] (T85). No row has `fSqm` 0. `hSqm` is `null` for 13,005 rows with `houses` > 0, `hAmt` for 2,298 of them.
  - Ignatki-osiedle (the village with the 8 transactions in the 2026-10-15 ranking): `flats` 254, `fSqm` 9,343, `fAmt` 453,493 [P].
- Totals: sum of `flats` 3,186,084, of `houses` 519,016.
- Sample (trimmed to 3 rows by the probe): `api.tx_cities.json`. The analysis above ran on the full body of a second request.

### `GET /api/statystyki/powiat-map-stats` [P 2026-11-01]
- No query string (the client sends none; it reads `quarterStart` and `own`). 200, `application/json`, **311,320 B**, cache-control `public, max-age=172800, s-maxage=86400, stale-while-revalidate=172800`, `cf-cache-status: HIT`, `age` 112,792 s.
- Envelope: `{"v": 6, "all": true, "periodStart": "2025-11-01", "periodEndMonth": "2026-10", "quarterStart": "2026-07-01", "own": true, "windowEnd": "2026-10-01", "rows": [...]}`. **So the market objects cover a 12-month window, 2025-11 to 2026-10** [P]; `quarterStart` is the current quarter.
- **380 rows, one per county** (`id` = `powiatId` of `map/tx-cities`; 380 unique ids, all matched). A row has `id`, `def` (`"wtorny"` in 343 rows, `"oba"` in 37: probably the market shown by default [H]), the market objects `wtorny` (secondary), `pierwotny` (primary), `oba` (both), `q` and `w`. A market object is `{n, m2, price, size, primary}`: `n` the number of transactions, `m2` a price per m², `price` an amount, `size` an area in m² (decimal), `primary` a number 0..100 or `null`. **No other key** in any market object (`primary` is `null` in 5 `oba` objects only).
- Missing markets are `null`, not `n: 0`: `pierwotny` is `null` in 70 rows, `wtorny` in 16, `oba` in 3; no object has `n` = 0 [P]. Warszawa (id 302): `wtorny` n 14,563 m2 16,395 price 779,000; `pierwotny` n 17,531 m2 15,468 price 764,088; `oba` n 32,095 m2 15,903 price 770,000, `primary` 54.6 in all three. Sopot (208): `pierwotny` null, `wtorny` n 310, `oba` n 409.
- `q`: `{own, yoy, wtorny, pierwotny, wszystko}`; `own` and `yoy` are objects keyed `wtorny`/`pierwotny`/`oba` (numbers or `null`: the 380 rows hold 80 `own` of 1/1/1, 51 of 0/0/0, 43 of all `null`), the three series are `{n: [13 numbers], m2: [13 numbers or null], hs, hm}`: 13 quarters of transaction counts and prices per m², newest last [W] (`hs`, `hm` unknown, `hm` values such as 549755806975 look like bit masks [H]). `w`: a 6-element array, e.g. `[6, 17531, 15468, 10167, 14026, 10.3]` for Warszawa; meaning unknown [H].
- **`primary` is a percentage, probably the share of primary-market transactions, but not one formula**: for Warszawa `pierwotny.n / oba.n * 100` = 54.6 = `primary` exactly. Across the 303 rows that have all three objects it matches within 0.5 percentage points in 130 rows and within 1 in 148; the same value in all three objects in only 110 rows (Kraków 51.8 / 53.6 / 51.4 against 55.6 computed); the largest gap is a row where `pierwotny.n` (340) exceeds `oba.n` (184). When `pierwotny` is `null`, `wtorny.primary` is 0 in 22 of the 60 rows that have `wtorny` and `oba`. So the figure is likely computed on a base that differs from the `n` shown (other classes or a different window) [W]; do not recompute it (T86).
- **`oba.n` is not `wtorny.n + pierwotny.n`**: equal in 80 of the 303 rows with all three, larger in 104, smaller in 119 [P]. When `pierwotny` is `null`, `oba.n` equals `wtorny.n` in 9 of 60 rows. So `oba` is not a sum of the two objects shown [P]; whether the two are measured on different transaction sets is open (T86).
- Counts differ from `city-transaction-stats` (a quarter) and from `map/tx-cities` (all history); a county has a market here but its price is `m2`, a figure of the 12-month window, so it is the best candidate for a county ranking replacing `map/powiat-stats` (404), after the median-or-mean question is settled (T85).
- Sample (trimmed): `api.powiat_map_stats.json`.

### `GET /api/map/powiat-investments/{powiatId}[?type=house]` [P]
- RCN buildings in a county with aggregates: `{powiatId, powiatName, investments: [{id, lat, lng, name, slug, city, citySlug, street, district, avgAmount, avgSize, avgPriceSqm, transactions, lastEventDate}]}`
- Sopot: 1,404 buildings, 419 KB.
- 2.0 [P z kodu 2026-10-30]: absent from the 2.0 client (section 8); not requested, live status unknown (T58).

### `GET /api/map/powiat-sales/{powiatId}[?type=house]` [P]
- **Dump of all transactions in a county**: `{powiatId, powiatName, investments: [...], sales: [{id, investId, priceSqm, amount, size, rooms, floor, type, lastEventDate, isFlipped, classification}]}`
- Sopot: 6,636 transactions, 1.6 MB. Warsaw an estimated ~80 MB [W]. **Do not use in MCP**.
- 2.0 [P z kodu 2026-10-30]: still referenced by the 2.0 client (the statistics page chunk and the `ceny-transakcyjne/[city]/mapa` and `adresy` page chunks); not requested.

### `GET /api/statystyki/raw-transactions?typ=<mieszkania|domy>[&powiat=<id>][&miasto=<slug>][&dzielnica=<name>]` [P z kodu 2026-10-30, dump (D5)]
- **Dump of every transaction of a city or county**, the 2.0 successor of the `rawTransactions` prop of the old statistics page (Warsaw: 128,912 rows, HTML 12.9 MB, see [pages-rsc.md](pages-rsc.md)). The 2.0 transactions page `/statystyki/{location}/transakcje` passes the URL as its prop `rawUrl` (Warsaw: `typ=mieszkania&powiat=302&miasto=warszawa`) [P 2026-10-30, saved scan page].
- Client validation [P z kodu 2026-10-30, chunk `6760`, module `65688`]: `typ` is `mieszkania` or `domy`; `powiat` 1 to 999999; `miasto` `[a-z0-9-]{1,80}`; `dzielnica` 1 to 80 characters and only together with `miasto`; `miasto` or `powiat` is required.
- **Never requested, by the package or by a check (D5).** It is in `DUMP_PATHS`, so the package's transport refuses it before any request. It is also in `API_PATHS` since 2026-10-31 (the sync test needs a dump to be a documented read channel, as `map/powiat-sales`), which lets probe read it within its body limit; do not probe it without a reason. The shape, size and cache headers are unknown. Sample: none.

### `GET /api/map/transactions/visible/{investRcnSlug}[?type=house]` [P]
- **RCN building with full transaction history**: `{invest_rcn_id, name, city, city_slug, street, slug, latitude, longitude, avg_amount, avg_size, avg_price_sqm, transactions, source_rcn, sale: [{sale_rcn_id, name, amount, amount_sqm, floor, floor_number, rooms, rooms_number, type, currency, size, start_amount_difference(_percent), total_events, creation_date, last_event_date, is_flipped, last_transaction_classification, sale_event_rcn: [{sale_event_rcn_id, amount, amount_sqm, currency, buyerType, sellerType, classification, transactionType, marketType, participation, creation_date, additionalData: {raw RCN record}}]}]}`
- 189 KB for a building with 86 units. Sample: `api.tx_visible.json`
- [P 2026-10-15] `tests/fixtures/api/tx_visible_cisna_20261015.json` (building 152198, `cisna`): `name` and `street` are empty strings (a village without streets); units with an empty `floor` have `floor_number` 0 (so 0 is not a ground floor there). 6 units, 7 transactions: 5 `transakcja`, 1 `udzial` (participation 1/2), 1 `egzekucja`. The counter `transactions` (5), `avg_amount` (274,600) and `avg_size` (72.08) are the means of the 5 `transakcja` transactions, `avg_price_sqm` (3,809.76) is their summed price over their summed area. Whether this is "all `transakcja` transactions" or "units whose last classification is `transakcja`" is open (T48) [H].
- 2.0 [P 2026-10-29, live e2e]: still answers 200 (`get_building` tests passed); the shape was not re-sampled.
- Unknown slug [P 2026-10-30, `nieistniejacy-budynek-e2e`]: `404`, `application/json`, 32 B, `{"error":"Investment not found"}` (the text of the offers route, though this one is about a building), `cache-control: max-age=172800`, `cf-cache-status: HIT`, `age: 63711`; no sample (non-2xx). Until then an unknown slug here was [H]. This is the JSON 404 of section 9.

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
- **2.0: HTTP 404** [P 2026-10-29, live e2e: `?propertyType=mieszkania&citySlug=warszawa`]; absent from the 2.0 client (section 8). [P 2026-10-30, the same query]: `404`, `text/html`, 36,628 B, the same Next.js not-found page, `cache-control: private, max-age=172800, must-revalidate`, `cf-cache-status: HIT`, `age: 16260`; no sample (non-2xx). `get_transaction_statistics` over months was broken by this and reads the statistics page props since 2026-10-31 (`view.monthly`, 118 rows for Warsaw, on `/statystyki/{city}/transakcje`, see [pages-rsc.md](pages-rsc.md); [P 2026-10-31, live e2e]). The page pads its series with empty months up to the current one; the package drops the trailing ones (Warszawa 3, Karpacz 10).
- Sample: `api.monthly_tx.json`

### `GET /api/statystyki/powiat-price-trend?powiatId=` [P]
- Quarterly: `[{quarter, med_price_sqm, trimmed_avg_price_sqm, avg_35_60_price_sqm, transaction_count}]`
- 2.0 [P z kodu 2026-10-30]: absent from the 2.0 client (section 8); not requested, live status unknown (T58).
- Sample: `api.powiat_trend_208.json`

### `GET /api/avg-price-trend/city/{citySlug}[?type=house[&metric=plot]]` [P]
- Quarterly: `{ data: [{period, avgPriceSqm, count}], scope: "city", scopeName }`
- [P 2026-10-16] `tests/fixtures/api/avg_trend_city_warszawa_20261016.json`: `scope` `city`, `scopeName` null, 39 quarters 2017-Q1..2026-Q3. Tail: 2025-Q3 3,902, 2025-Q4 3,605, 2026-Q1 3,721, 2026-Q2 1,034, 2026-Q3 37 with `avgPriceSqm` 33,176 (the same outlier as monthly 2026-07). Each quarter's `count` is about 2% above the sum of its months in `monthly-transaction-stats` (2026-Q1 3,721 vs 3,643) [P]; the cause is unknown [H].
- **2.0: still served, though the 2.0 client no longer calls it** [P 2026-10-30, `api.avg_trend_city.krakow`, `api.avg_trend_city.house_plot`]. `krakow` → 200, 2,180 B: `{data, scope: "city", scopeName: null}`, 40 contiguous quarters 2017-Q1 (6,002 PLN/m², 1,036 transactions) .. 2026-Q3 (15,027; 1,431) and 2026-Q4 (16,184; 4 transactions, the quarter in progress on 2026-10-30). `type=house&metric=plot` → 200, 1,932 B, the same envelope, 37 quarters 2017-Q1 (1,342; 23) .. 2026-Q2 (2,559; 53), with 2021-Q3 absent (a quarter without data is left out, not zero-filled), at least 1 transaction a quarter; 2026-Q3 and 2026-Q4 are not there yet, so the house series lags the flat one by two quarters. Cache-Control `public, max-age=28800, s-maxage=86400, stale-while-revalidate=604800` (`HIT`, `age` 21,101, for flats; `EXPIRED` for the house series).
- Unknown city [P 2026-10-30, `nieistniejace-miasto`]: `404`, `application/json`, 24 B, `{"error":"Unknown city"}`, `cache-control: public, max-age=172800, s-maxage=3600`, `cf-cache-status: MISS`; no sample (non-2xx). So an unknown city here is a JSON 404 (section 9), neither a 400 nor an empty series (T38 for this route).
- **`avgPriceSqm` is a median, not a mean** [P 2026-10-30, comparison of two responses of Warsaw]: against the 2.0 statistics page `/statystyki/warszawa/transakcje` (saved scan page, prop `priceChange.points[]` `{period, n, medSqm, avgSqm, …}`) and the fixture `tests/fixtures/api/avg_trend_city_warszawa_20261016.json`, in the 36 quarters 2017-Q1..2025-Q4 where both counts agree `avgPriceSqm` lies within 2.41 PLN/m² of `medSqm` (identical after rounding in 27), while the closest `avgSqm` is 165 PLN/m² away. Refuted: the reading of `avgPriceSqm` as a mean. `city_trend_dto.py` reads it as the median since 2026-10-31 (`tests/contract/api/dto/test_city_trend_dto.py`), and the live e2e [P 2026-10-31, `test_the_price_of_a_quarter_is_a_median`] finds the trend's price closer to the medians of its three months than to their means in every complete quarter compared (at least 4). `building_trend_dto.py` still reads the building trend's `avgPriceSqm` as a mean ([W] in its comment), probably a median as for the city (the building endpoint was not compared, T83).
- The last three Warsaw quarters differ between the fixture (2026-10-16: 2026-Q1 3,721, Q2 1,034, Q3 37) and the 2.0 page (2026-10-30: 3,150, 6, 0), while the page's own monthly series (`view.monthly`) sums to 3,641, 1,008 and 35 and agrees with the monthly fixture of 2026-10-15 within 2: the endpoint's recent quarters may no longer match the figures the 2.0 page shows (T46).
- The quarterly `count` is above the sum of the page's months [P 2026-10-31, fixtures `avg_trend_city_warszawa_20261016.json` and `stats_tx_warszawa_20261031.rsc`, `view.monthly`, the secondary market of flats]: in each of the 37 closed quarters of Warszawa, 2017-Q1..2026-Q1, it is 2.1 % to 4.0 % higher (2.1 to 2.2 % from 2023-Q1 on, so in the five quarters 2025-Q1..2026-Q1 too; 3.0 to 4.0 % in the nine quarters 2020-Q4..2022-Q4; 2.1 to 2.4 % before), 2.6 % in 2026-Q2 (1,034 against 1,008) and 5.7 % in 2026-Q3 (37 against 35). Against the 1.0 monthly series [P 2026-10-31, `monthly_tx_warszawa_20261015.json`] it is 2.07 to 2.19 % above in each of the 21 closed quarters 2021-Q1..2026-Q1, so the wider gaps of 2020-Q4..2022-Q4 are where the 2.0 months are below the 1.0 ones (T46). Whether the trend counts another market or other classes is open (T45).
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

### `GET /api/statystyki/gov-map-stats` [P 2026-11-01]
- No query string. 200, `application/json`, **11,152 B**, cache-control `public, max-age=172800, s-maxage=86400, stale-while-revalidate=172800`, `cf-cache-status: HIT`, `age` 112,227 s. Not in the section 7 table or in the first survey of the 2.0 client.
- `{"asOf": {...}, "rows": [{"slug", "values": {...}}]}`. `asOf` holds 7 indicator keys with the period each one is current to (text): `bezrobocie` "08.2026", `wynagrodzenie` "2025", `oddane` "08.2026", `rozpoczete` "08.2026", `powierzchnia` "08.2026", `przyrost` "2025", `nbpCena` "Q2 2026" [P].
- **66 rows**, unique slugs, one per city with powiat rights, the same 66 as the cities of `get_government_statistics` (`KNOWN_LOCATIONS` in `government_statistics_api.py`; `jastrzebie-zdroj`, not the 1.0 `jastrzebie`); all 66 slugs are also in `map/tx-cities`. Row order: Warszawa, Białystok, … (not alphabetical). `values` keys are the 7 `asOf` keys in every row.
- Missing values: `nbpCena` (NBP price per m²) is `null` in **49 of 66 rows** (only the 17 cities that the NBP covers have it: warszawa, bialystok, bydgoszcz, gdansk, gdynia, katowice, kielce, krakow, lublin, lodz, olsztyn, opole, poznan, rzeszow, szczecin, wroclaw, zielona-gora); the other six indicators are present in all 66 rows. Warszawa: `bezrobocie` 1.6 (%), `wynagrodzenie` 11,677.57, `oddane` 19,058, `rozpoczete` 15,150, `powierzchnia` 56.78 (m², unrounded), `przyrost` -2,291, `nbpCena` 16,723. Units are inferred from the names and the page [W].
- Sample: `api.gov_map_stats.json`.

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

Found by the bundle scan of 2026-10-30 [P z kodu]. All are plain GET requests (`fetch` calls, or image and tile URLs) used to render pages. "read" = a GET that returns data; "dump (D5)" = by its name a bulk transaction dump, which the package never requests. None of them was requested live, so the shapes below are what the client code reads, not what the server sends. To enable a probe, the path needs a `` ### `GET /api/...` `` heading in the sections above and an entry in `allowlist.API_PATHS` (and in `DUMP_PATHS` for a dump): the docs first, the code second (T59). Four rows were promoted and are no longer in this table: `/api/map/offer-snapshot/{citySlug}` (section 2, D20; requested on 2026-10-31), `/api/statystyki/raw-transactions` (section 3, a dump, D5; never requested), and on 2026-11-01 `/api/map/tx-cities` and `/api/statystyki/powiat-map-stats` (section 3; both requested, shapes known).

| Path | Client evidence | Call shape and what the client reads | Class |
|---|---|---|---|
| `/api/city-search-counts` | chunks `5665`, `3836` (search box) | no query; JSON; client cache 30 min | read |
| `/api/invest-offer-sparklines?ids=<id,id,…>` | chunk `3216` | csv of investment ids; JSON object keyed by id, each value an array of `[date, value]` pairs | read |
| `/api/sale-sparklines?ids=<id,id,…>` | chunks `4010`, `6335`, `app/start` | csv of sale ids, at most 48 per request (client batches); JSON object keyed by id, each value an array of `[date, amount, event type index]` triples (the index of `ev`, see `map/investments/visible`) | read |
| `/api/map/offer-lifecycle/{x}` | statistics page chunk | `x` comes from the page filters and looks like a location slug rather than an id [W]; client cache 6 h | read |
| `/api/statystyki/city-change-stats` | statistics page chunk | no query; reads `quarterStart` and `cities[]` (rows with an `o` flag) | read |
| `/api/transaction-price-scale?<filters>` | statistics page chunk | the query string is built from the page filters | read |
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
| `/api/offers/city-sales/{citySlug}` | **404, HTML page** [P 2026-10-29, live e2e, a valid and an unknown city; P 2026-10-30, `krakow`] | was `get_market_statistics`; repaired 2026-10-31 (reads `map/offer-snapshot`, D20) |
| `/api/monthly-transaction-stats` | **404, HTML page** [P 2026-10-29, live e2e; P 2026-10-30, `propertyType=mieszkania&citySlug=warszawa`] | was `get_transaction_statistics` (months); repaired 2026-10-31 (reads `view.monthly` of the statistics page) |
| `/api/map/powiat-stats` | **404, HTML page** [P 2026-10-29, live e2e; P 2026-10-30] | `rank_locations` (powiats): still broken, expected xfail of the live e2e [P 2026-10-31] |
| `/api/investments/{investId}/sale-events` | **404, HTML page** [P 2026-10-30, `invest_id` 447] | was `get_investment` (`include_history`); repaired 2026-10-31 (reads `ev`) |
| `/api/avg-price-trend/city/{citySlug}` | **200** [P 2026-10-30, `krakow`; `type=house&metric=plot`] | `get_transaction_statistics` (quarters): works [P 2026-10-31, live e2e] |
| `/api/avg-price-trend/building/{investRcnId}` | **200** [P 2026-10-29, live e2e; 1354 and 152198] | `get_building` (neighbourhood trend): works |
| `/api/building-outline` | not requested | none |
| `/api/map/powiat-investments/{powiatId}` | not requested | none |
| `/api/statystyki/powiat-price-trend` | not requested | none |
| `/api/size-distribution` | not requested | none |
| `/api/transaction-size-distribution` | not requested | none |

What replaced them in the 2.0 client [P z kodu 2026-10-30]: the offer price history is the `ev` field of `map/investments/visible/{slug}`; offer-market aggregates, monthly transaction series and county statistics now come from the page props of `/statystyki/{location}/…` (see [pages-rsc.md](pages-rsc.md)) and from the new `/api/statystyki/*` and `/api/map/tx-cities` paths of section 7. Whether those replacements fit the tools' needs is open (T59). Since 2026-10-31 the package uses three of them: `map/offer-snapshot` for the market statistics, `ev` for the investment history and the page's `view.monthly` for the months; the county ranking is the one still open.

---

## 9. Error answers: an unknown entity or a removed route (2.0)

Seven requests of 2026-10-30 with `probe.py api` (one each at 1 request per second; it sends `Accept: application/json`), plus the one made earlier the same day, plus one of 2026-10-31 (the unknown city of `map/offer-snapshot`). Media type as probe prints it (parameters cut off). "Page" is the Next.js not-found page: the body starts `<!DOCTYPE html><!--VDpA73sQ_GRMsEMdmIQtu--><html lang="pl"><head><meta charSet="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/><link rel="preload" href="/_next/static/media/26d0ba92e140f0dc-s.p.woff2" …` (the 300 characters probe prints for a non-2xx body; the `<title>` lies beyond them and was not read). All [P 2026-10-30] except the offer-snapshot row [P 2026-10-31]; only the 200 has a sample.

| Request | Case | Status | Media type | Size | Distinguishing content | `cache-control`; CDN |
|---|---|---|---|---|---|---|
| `map/investments/visible/nieistniejaca-inwestycja-e2e` | unknown investment | 404 | `application/json` | 32 B | `{"error":"Investment not found"}` | `max-age=172800`; HIT, age 63,943 |
| `map/transactions/visible/nieistniejacy-budynek-e2e` | unknown RCN building | 404 | `application/json` | 32 B | `{"error":"Investment not found"}` | `max-age=172800`; HIT, age 63,711 |
| `avg-price-trend/city/nieistniejace-miasto` | unknown city | 404 | `application/json` | 24 B | `{"error":"Unknown city"}` | `public, max-age=172800, s-maxage=3600`; MISS |
| `map/offer-snapshot/nieistniejace-miasto` (2026-10-31) | unknown city | 404 | `application/json` | 24 B | `{"error":"Unknown city"}` | `public, max-age=172800, s-maxage=3600`; HIT, age 53,556 |
| `sale-events?saleId=999999999` | unknown offer | **200** | `application/json` | 44 B | `{"success":true,"saleData":null,"events":[]}` | `public, max-age=172800, s-maxage=3600, stale-while-revalidate=86400`; MISS |
| `offers/city-sales/krakow` | removed route | 404 | `text/html` | 36,628 B | page | `private, max-age=172800, must-revalidate`; REVALIDATED |
| `monthly-transaction-stats?propertyType=mieszkania&citySlug=warszawa` | removed route | 404 | `text/html` | 36,628 B | page | `private, max-age=172800, must-revalidate`; HIT, age 16,260 |
| `map/powiat-stats` | removed route | 404 | `text/html` | 36,628 B | page | `private, max-age=172800, must-revalidate`; HIT, age 14,346 |
| `investments/447/sale-events` (earlier the same day) | removed route | 404 | `text/html` | 36,628 B | page; build comment `VDpA73sQ_GRMsEMdmIQtu` | `private, max-age=28800, must-revalidate`; MISS |

The two HITs of the first rows are probably the copies that the e2e run of 2026-10-29 cached, because `tests/e2e` asks for these very slugs [W]; the HIT of the offer-snapshot row (age 53,556 s, about 15 hours, more than its `s-maxage` of 3,600 s) is a copy that an earlier request for the same address left, probably a live test run [W]; why the CDN served it past `s-maxage` is not known. `sale-events?saleId=1` is not an unknown offer: on 2026-10-31 it answered `200` with a real archived offer (397 B, see its entry), which is why the unknown-offer row uses `999999999`.

Rule for the client when an `/api/*` route answers with a non-2xx status:

| Observed | Reads as | Certainty |
|---|---|---|
| `404` + `application/json` (a JSON object with an `error` string) | an unknown entity (investment, RCN building, city); `error` is detail for the log, not an interface: the texts differ per route (`Investment not found` even for a building, `Unknown city`) | [P 2026-10-30], 3 of 3 routes tried; [P 2026-10-31] 4 of 4 with `map/offer-snapshot` |
| `404` + `text/html` (the Next.js not-found page) | the route is gone or moved: the service changed, not an unknown entity | [P 2026-10-30], 4 of 4 removed routes; the same 36,628 B on all four, so one static page that does not echo the path; also sent to a request that asks for JSON |
| `404` with another media type, or a JSON `404` without `error` | not seen; read as a changed service | [W] |
| `200` + `saleData: null` (`sale-events` only) | an unknown offer | [P 2026-10-30] (`api.sale_events.unknown`) |

The media type is the discriminator, not the body: the size and the build comment of the page change with every deploy [W], and the JSON texts are per route. The HTML 404 is not a protection response: probe's challenge check did not fire on any of the four (exit 4, a plain HTTP error, not 3, STOP).

Where the rule does not hold, or was not tried:
- `sale-events` answers an unknown id with a `200` (`saleData: null`), not a 404 (above).
- A malformed identifier is a `400` + JSON `error`, not a 404: `avg-price-trend/building/<slug>` gives `{"error":"Valid investRcnId is required"}`; `city-sales/polska` gave `{"error":"Invalid citySlug"}` [P 2026-10-10], a route that is gone now. That is bad input from the client, not an unknown entity.
- `avg-price-trend/building/{id}`: a building without a neighbourhood trend is a `200` `{"data":[],"radiusKm":0}` [P 2026-10-15]; an unknown numeric id was not requested [H].
- Not requested: an unknown city on `map/investments`, `city-districts`, `offer-count`, `transaction-count`, `map/city-powiats/{citySlug}` and `developers?city=` (what is left of T38); `map/offer-snapshot/polska` and the aggregates (T69 is settled otherwise).
- Pages are outside the rule, and they are not alike (below).

### Pages: an unknown entity on an RSC request (2.0) [P 2026-10-31]

Seven page requests of 2026-10-31 with `probe.py page` (`RSC: 1`, empty `_rsc`; the digest was read with `--prop digest`, which prints the value of the first `"digest":` in the stream). Media type and size as probe prints them.

| Request | Case | Status | Media type | Size | What tells it |
|---|---|---|---|---|---|
| `/ceny-ofertowe/nieistniejace-miasto/mieszkania` | unknown city | **200** | `text/x-component` | 25,189 B | `E` row digest `NEXT_HTTP_ERROR_FALLBACK;404` (2 occurrences); no `sales`, no `serverPaginationData` |
| `/ceny-ofertowe/warszawa/deweloperzy/nieistniejacy-deweloper` | unknown developer | **200** | `text/x-component` | 17,814 B | the same digest (1 occurrence); 1.0 had no digest here |
| `/ceny-ofertowe/warszawa/nieistniejaca-dzielnica/mieszkania` | unknown district | **200** | `text/x-component` | 28,341 B | the same digest (2 occurrences) |
| `/statystyki/nieistniejace-miasto/dane-rzadowe` | unknown location | **404** | `text/x-component` | 24,757 B | the status; the body is a flight stream (it starts `1:"$Sreact.fragment"`, `2:I[98202,…,"GoogleTagManager"]`) |
| `/statystyki/nieistniejace-miasto/transakcje` | unknown location | **404** | `text/x-component` | 25,204 B | the status; the same kind of body |
| `/ceny-ofertowe/warszawa/mieszkania?filterDistrict=Mokotów` (and `=mokotow`) | a known city with a parameter that no longer works | **200** | `text/x-component` | 27,316 B (27,309 B) | no `sales`, no `serverPaginationData`; whether the digest is inside was not read |

- All seven: `cache-control: private, max-age=172800, must-revalidate`, `cf-cache-status: MISS`. The 404s of the two statistics pages are no protection response: probe ended with exit 4 (a plain HTTP error), not 3 (STOP).
- So on 2.0 pages an unknown entity is **either** a `200` with the 404 digest (the offer lists and the developer page: city, district, developer) **or** an HTTP `404` with a `text/x-component` body (the two statistics pages: unknown location). The rule for `/api/*` above (a 404 is "unknown" only with a JSON `error`) does **not** carry over: a client that reads every 404 without a JSON `error` as "the service changed" misreads the unknown location of the statistics pages. The media type is again the discriminator: a `404` whose `Content-Type` is `text/x-component` is the application's own answer to an unknown location [P 2026-10-31, 2 of 2 statistics routes]; a `404` `text/html` on a page route was not observed in this round (the report pages answer `410` HTML, [P 2026-10-30, scanner]).
- Not read: whether the body of the two 404s holds an `E` row with the digest (probe prints 300 characters of a non-2xx body), and the answer of a statistics page to an unknown district (`/statystyki/{city}/{district}/transakcje`) or to a plain HTML request (T36).

### How the package reads these answers (D21) [P z kodu 2026-10-31; live e2e 2026-10-31]

The transport (`api/http/transport.py`: `_check`, `_moved_or_gone`, `_says_unknown`) and `RscPage` (`api/http/rsc_page.py`). The rule is the table above made strict: an answer reads as "unknown" only where the service was seen to say so. A redirect, a 410 and every other 404 read as a changed service; any other non-2xx status is a service error, and 401, 403, 429 and a challenge are a STOP before anything else.

| Answer | The package reads it as | Certainty |
|---|---|---|
| any `3xx` (the transport never follows one) | a changed service (`UnexpectedResponseError`, CLI exit 6) | [P z kodu]; the moved routes of 2026-10-29 answered 308 and a hashed `_rsc` 307 |
| `410` | a changed service | [P z kodu]; `/zglos-dewelopera` answers 410 [P 2026-10-30, scanner] |
| `404` + `application/json` with an `error` string, on a JSON route | an unknown entity (`NotFoundError`, exit 7) | [P 2026-10-30], 3 routes, and `map/offer-snapshot` [P 2026-10-31]; the live e2e passes for an unknown investment and an unknown city (market) [P 2026-10-31] |
| `404` + `text/x-component` | an unknown location **only on a page that opts in** (`RscPage(unknown_404=True)`): the two statistics pages, `transakcje` and `dane-rzadowe` | [P 2026-10-31], 2 of 2 routes; the live e2e passes for both (an unknown location says „nie ma statystyk rządowych” and „nie ma cen transakcyjnych”, never „service changed”) |
| `404` on any other page, a `404` `text/html`, JSON without an `error` string | a changed service: the offer lists and the developer page answer an unknown entity with a `200` and the 404 marker, so a 404 there means a removed or rebuilt route | [P z kodu]; such a 404 on these pages was never seen [W] |
| `200` with the 404 marker (`NEXT_HTTP_ERROR_FALLBACK;404`) and without the data props | an unknown city, district or developer (`NotFoundError`) | [P 2026-10-31]; also a page past the last one of a known list (Sopot, page 2) [P 2026-10-31, live e2e, T34] |
| `200` without the data props and without the marker | a page that does not match the contract: a changed service | [P z kodu]; a known developer in an unknown city is such a page [P 2026-10-31, live e2e, T39] |

Residual risk [W]: a statistics route removed altogether might answer a 404 `text/x-component` too and would read as an unknown location. The government adapter guards its 70 `KNOWN_LOCATIONS` (for them an "unknown" answer is a changed service); the transaction adapter has no such list. The live e2e after each deploy of the service is the check (D21).
