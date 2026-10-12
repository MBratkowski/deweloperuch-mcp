# Capability matrix (v1, 2026-10-09)

The capabilities follow from the data actually available in the service ([discovery/](discovery/README.md)). Each capability is a domain operation. It may consist of several requests.

Channels: **A** = JSON `/api/*`, **B** = RSC page, **C** = server action.
Status:
- ✅ ready to implement: requests made, response shape known
- 🟡 feasible with caveats: some parameters or semantics unverified
- 🔴 unclear: data semantics unknown
- ⏸ deferred: low priority or out of scope

## Locations

| Capability | Data | Request(s) | Input | Output | Limitations | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Search locations | cities, districts, streets with lat/lng and offer/transaction count | A `cities?q`, `location-search?q`, optionally `city-lookup` | `query`, `market: offers\|transactions` | `[{kind: city\|district\|street, name, city_slug, lat?, lng?, count}]` | `cities` also returns localities with 0 offers | `locations search <q>` | `search_locations` | ✅ implemented (CLI+MCP, S1a `23cd5be`, S1b `a954994`); `kind` also `city` [P 2026-10-10], `cities` has pagination (`page`) |
| City districts | districts + counts | A `city-districts?citySlug` | `city`, `market` | `[{name, count}]` | names only, no IDs or geometry | `locations districts <city>` | (in `search_locations` or separate) | ✅ |
| City → RCN county | county ids | A `map/city-powiats/{city}` | `city` | `{powiat_ids, primary}` | — | (internal) | (internal) | ✅ |

## Developer offers (primary market)

| Capability | Data | Request(s) | Input | Output | Limitations | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Search offers (flats) | offer list with price, area, price changes, investment, developer | B `/ceny-ofertowe/{city}/mieszkania?filter…` | `city`, `price`, `price_per_m2`, `area` (min/max), `developer?`, `investment?`, `district?`, `rooms?`, `price_change?`, `include_archived?`, `sort`, `page`, `per_page` | MCP: `{total, returned, truncated, page, per_page, pages_available, hint, items}` (D11; original plan `{total, page, total_pages, items}`) | **max 20 pages × 100 = 2000**; `perPage` 10/25/50/100 [P 2026-10-10]; `sortBy` 5 values [P], default `sale_id`; `district`, `price_change`, `status`, `include_archived` [P 2026-10-10]; **`rooms` and `floors` do not work on the offer list** (refuted); other filters T33 | `offers search …` | `search_offers` | 🟡 (core ✅, implemented CLI+MCP; the exposed [P] parameters are only a subset, see the notes on new [P] in the report of B 2026-10-10); RSC parser fixed 2026-10-10 (rows `T<hexlen>,` without `\n`); e2e suite in `tests/e2e/` |
| Get offer + price history | offer data, price events | A `sale-events?saleId`, A `map/investments/visible/{slug}` (context) | `offer_id`, `investment_slug` | `Offer {…, investment, developer, price_history[]}` | `sale-events` does not return the investment; without the slug there is no context (see gaps) | `offers get <id> --investment <slug>` | `get_offer` | ✅ implemented (CLI+MCP); `OFFER_EVENT` = every price entry [P 2026-10-10]; unknown `saleId` → 200 with `saleData: null` |
| Search investments | investments with aggregates | B `/ceny-ofertowe/{city}/inwestycje`; A `investments?q` (by name); A `map/investments?…` (all in a city, with lat/lng) | `city`, `name?`, `developer?`, price filters, `sort`, `page` | `{total, items:[InvestmentSummary]}` | B: 20-page limit; A `map/investments` no limit, but no pagination | `investments search …` | `search_investments` | ✅ |
| Get investment | investment, developer, all offers (active+archived), optionally history | A `map/investments/visible/{slug}`, optionally A `investments/{id}/sale-events` | `investment_slug`, `include_history?` | `Investment {…, offers[]}` | `sale-events` slow on MISS (~3 s) | `investments get <slug>` | `get_investment` | ✅ implemented (CLI+MCP); unknown slug → 404 `Investment not found` [P 2026-10-10] |
| Search developers | developers with aggregates | B `/ceny-ofertowe/{city}/deweloperzy`; A `developers?q` | `city?` (`polska`), `name?`, `sort`, `page` | `{total, items:[DeveloperSummary]}` | — | `developers search …` | `search_developers` | ✅ |
| Get developer | profile, investments, statistics, price-change axis | B `/ceny-ofertowe/{city}/deweloperzy/{slug}` | `developer_slug`, `city?` | `Developer {…, investments[], stats}` | RSC only; `filteredStats`/`citiesStats` need field descriptions | `developers get <slug>` | `get_developer` | 🟡 |
| Offer statistics | offer count, price/price-per-m²/area histograms | A `offer-count`, `price-distribution`, `size-distribution` | `city`, filters as in search, `developer?`, `investment?` | `{count, price_histogram, price_m2_histogram, area_histogram}` | bucket boundaries must be reconstructed (`aligned`) | `stats offers …` | `get_offer_statistics` | 🟡 |
| Offer report (market comparison) | RCN valuation for an offer, competing offers nearby | B `…/{inv}/raport-mieszkania-{slug}`; B `…/{inv}/raport-inwestycji` | `investment_slug`, `offer_name` | `{offer, valuation, competitors[]}` | risk of offer-name slug collisions | `offers report …` | `compare_offer_to_market` | 🟡 |

## Transactions (RCN)

| Capability | Data | Request(s) | Input | Output | Limitations | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Search transactions | unit/house transactions + **aggregates of the whole set** | B `/ceny-transakcyjne/{city}/mieszkania\|domy?filter…` | `city`, `property: flat\|house`, `price`, `price_per_m2`, `area`, `rooms?`, `floor?`, `district?`, `street?`, `classification?`, `sort`, `page`, `per_page` | `{total, stats, items:[TransactionSummary]}` | limit 2000; `district` raises doubts; format of `filterLastTransactionDate` unknown | `transactions search …` | `search_transactions` | 🟡 (core ✅) |
| Search buildings/addresses | buildings with transaction counts and averages | B `/ceny-transakcyjne/{city}/adresy`; A `investment-streets?variant=transactions` | `city`, `street?`, `sort`, `page` | `{total, items:[BuildingSummary]}` | — | `buildings search …` | `search_buildings` | 🟡 |
| Get building with transactions | all units and transactions in a building, RCN details | A `map/transactions/visible/{slug}`, A `avg-price-trend/building/{id}` (1 km neighborhood trend) | `building_slug`, `property?` | `Building {…, units[{transactions[]}], neighborhood_trend?}` | large responses (189 KB / 86 units), must be trimmed | `buildings get <slug>` | `get_building` | ✅ |
| Transaction statistics over time | monthly medians/averages, counts | A `monthly-transaction-stats` (city/county/street), A `avg-price-trend/city/{city}` (quarterly), A `statystyki/powiat-price-trend` | `scope: city\|powiat\|street`, `id`, `property`, `granularity: month\|quarter` | `[{period, count, median_price_m2, avg_price_m2, median_area, median_amount, …}]` | latest months incomplete (RCN lag) | `stats transactions …` | `get_transaction_statistics` | ✅ |
| Transaction count/histogram | count, price and area distribution | A `transaction-count`, `transaction-*-distribution` | `city`, filters, `powiat_ids?`, `building_id?` | as for offers | slow on MISS (2–5 s) | (in `stats transactions`) | (in `get_transaction_statistics`) | 🟡 |
| City / county ranking | transaction count, prices, changes | A `city-transaction-stats`, A `map/powiat-stats` | `property?`, `sort`, `limit` | `[{city, count, price_m2, change_pct…}]` | period and base of changes unknown; `avg_` may mean median | `stats cities` | `rank_locations` | 🟡 |

## Valuation

| Capability | Data | Request(s) | Input | Output | Limitations | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Value a property | estimated value, price/m², comparable transactions, radius, trend | A `standalone-valuation?area&lat&lng&address` | `lat`, `lng`, `area_m2`, `address?` | `{estimated_value, price_per_m2, radius_m, period_months, comparables[top N], stats}` | needs coordinates: no confirmed address→lat/lng geocoding (see gaps); 180 KB → we trim | `valuation estimate …` | `estimate_property_value` | ✅ |

## External statistics

| Capability | Data | Request(s) | Input | Output | Limitations | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| GUS/NBP statistics | construction (completed/started), average area, demographics, unemployment, wages, NBP prices | B `/statystyki/statystyki-rzadowe/{loc}` | `location` (69 options), `dataset` | time series per dataset | RSC only; several `data` props to tell apart by shape | `stats government <loc> <dataset>` | `get_government_statistics` | 🟡 |
| Listing portal statistics | daily sell/rent series × 2 sources | A `announcement-stats` | `region`, `property` | series | meaning of `blue/green` and `value` unknown; `polska` empty | — | — | 🔴 |

## Deferred (⏸)

| Capability | Source | Reason |
|---|---|---|
| Price transparency violation reports | B `/zglos-dewelopera/mapa-zgloszen` | niche; easy to add later |
| Building outline, flood/Airbnb layers, county borders | A `building-outline`, CDN pmtiles, `/geo/powiaty.geojson` | geometric data has little value for an LLM |
| Bulk dumps (`powiat-sales`, `rawTransactions`) | A / B | too large for MCP; possibly as a source for a local index |
| Valuation PDF | A `valuation-pdf` | rate limit, binary |
| Loan calculators | client logic | not service data |
| Writes (reports, error reports) | C + Turnstile | out of scope, read-only |

## Proposed MCP toolset (v1)

`search_locations`, `search_offers`, `get_offer`, `search_investments`, `get_investment`, `search_developers`, `get_developer`, `get_offer_statistics`, `search_transactions`, `get_building`, `get_transaction_statistics`, `estimate_property_value`, later `get_government_statistics`, `compare_offer_to_market`, `rank_locations`.

Principles (to be confirmed in implementation):
- List results always return `total` and a truncation indicator (`truncated: true` when `total > 2000`), so the model knows to narrow the filters.
- Identifiers in outputs are those accepted by the "get" tools: `investment_slug`, `offer_id`, `building_slug`, `developer_slug`, `city_slug`.
- Large arrays (comparable transactions, investment offers) are trimmed with a `limit` parameter and an `omitted` field.
