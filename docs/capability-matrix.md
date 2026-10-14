# Capability matrix (updated 2026-10-14)

The capabilities follow from the data the service actually exposes ([discovery/](discovery/README.md); certainty tags are explained there). Each capability is a domain operation and may consist of several requests.

Channels: **A** = JSON `/api/*`, **B** = RSC page, **C** = server action.

Status:
- **implemented**: available in the CLI and as an MCP tool
- **feasible**: requests known and response shape understood, not implemented
- **unclear**: data semantics not yet understood
- **deferred**: low priority or out of scope

13 MCP tools are implemented: `search_locations`, `search_offers`, `get_offer`, `search_investments`, `get_investment`, `search_developers`, `get_developer`, `get_market_statistics`, `get_transaction_statistics`, `rank_locations`, `get_building`, `estimate_property_value`, `get_government_statistics`.

## Locations

| Capability | Data | Request(s) | Input | Output | Limitations | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Search locations | cities, districts, streets with lat/lng and offer/transaction count | A `cities?q`, `location-search?q`, optionally `city-lookup` | `query`, `market: offers\|transactions` | `[{kind: city\|district\|street, name, city_slug, lat?, lng?, count}]` | `cities` also returns localities with 0 offers; `cities` is paginated (`page`) | `locations search <q>` | `search_locations` | implemented |
| City districts | districts + counts | A `city-districts?citySlug` | `city`, `market` | `[{name, count}]` | names only, no IDs or geometry | none | none (districts come from `search_locations`) | feasible |
| City to RCN county | county ids | A `map/city-powiats/{city}` | `city` | `{powiat_ids, primary}` | none | internal | internal | implemented |

## Developer offers (primary market)

| Capability | Data | Request(s) | Input | Output | Limitations | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Search offers (flats) | offer list with price, area, price changes, investment, developer | B `/ceny-ofertowe/{city}/mieszkania?filter…` | `city`, `price`, `price_per_m2`, `area` (min/max), `developer?`, `investment?`, `district?`, `price_change?`, `status?`, `include_archived?`, `sort`, `page`, `per_page` | `{total, returned, truncated, page, per_page, pages_available, hint, items}` | max 20 pages x 100 = 2000 results; `perPage` 10/25/50/100; 5 sort keys, default `sale_id`; `rooms` and `floors` have no effect on the offer list; remaining filters untested (T33) | `offers search …` | `search_offers` | implemented |
| Get offer + price history | offer data, price events | A `sale-events?saleId`, A `map/investments/visible/{slug}` (context) | `offer_id`, `investment_slug` | `Offer {…, investment, developer, price_history[]}` | `sale-events` does not return the investment, so the slug is required (T1); unknown `saleId` gives 200 with `saleData: null` | `offers get <id> --investment <slug>` | `get_offer` | implemented |
| Search investments | investments with aggregates | B `/ceny-ofertowe/{city}/inwestycje`; A `investments?q`; A `map/investments?…` | `city`, `name?`, `developer?`, price filters, `sort`, `page` | `{total, items:[InvestmentSummary]}` | page route has the 20-page limit; `map/investments` has no limit but no pagination | `investments search …` | `search_investments` | implemented |
| Get investment | investment, developer, all offers (active + archived), optional history | A `map/investments/visible/{slug}`, optionally A `investments/{id}/sale-events` | `investment_slug`, `include_history?` | `Investment {…, offers[]}` | `sale-events` is slow on a cache miss (~3 s); unknown slug gives 404 `Investment not found` | `investments get <slug>` | `get_investment` | implemented |
| Search developers | developers with aggregates | B `/ceny-ofertowe/{city}/deweloperzy`; A `developers?q` | `city?` (`polska`), `name?`, `sort`, `page` | `{total, items:[DeveloperSummary]}` | none known | `developers search …` | `search_developers` | implemented |
| Get developer | profile, investments, statistics, price-change axis | B `/ceny-ofertowe/{city}/deweloperzy/{slug}` | `developer_slug`, `city?` | `Developer {…, investments[], stats}` | RSC only; `priceIncreaseCount` / `priceDecreaseCount` unreliable and unused (T14); unknown developer answers 200 with h1 "Deweloper nie znaleziony" | `developers get <slug>` | `get_developer` | implemented |
| Offer statistics | offer count, price / price-per-m2 / area histograms | A `offer-count`, `price-distribution`, `size-distribution` | `city`, filters as in search, `developer?`, `investment?` | `{count, price_histogram, price_m2_histogram, area_histogram}` | bucket boundaries must be reconstructed (`aligned`, T9) | none | none | feasible |
| Market statistics (offers) | offer-market aggregates per city (counts, prices, investments, developers) | A `offers/city-sales/{city}` (aggregated internally) | `city` | aggregates | the dump is used internally only; active offers only; may differ slightly from the offers list (Kraków 7325 vs 7307) | `stats market <city>` | `get_market_statistics` | implemented |
| Offer report (market comparison) | RCN valuation for an offer, competing offers nearby | B `…/{inv}/raport-mieszkania-{slug}`; B `…/{inv}/raport-inwestycji` | `investment_slug`, `offer_name` | `{offer, valuation, competitors[]}` | offer-name slug collisions possible (T7) | none | none | feasible |

## Transactions (RCN)

| Capability | Data | Request(s) | Input | Output | Limitations | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Search transactions | unit/house transactions + aggregates of the whole filtered set | B `/ceny-transakcyjne/{city}/mieszkania\|domy?filter…` | `city`, `property: flat\|house`, `price`, `price_per_m2`, `area`, `rooms?`, `floor?`, `district?`, `street?`, `classification?`, `sort`, `page`, `per_page` | `{total, stats, items:[TransactionSummary]}` | 2000-result limit; `district` may not narrow strictly (T4); `filterLastTransactionDate` format unknown (T5) | none | none | feasible |
| Search buildings / addresses | buildings with transaction counts and averages | B `/ceny-transakcyjne/{city}/adresy`; A `investment-streets?variant=transactions` | `city`, `street?`, `sort`, `page` | `{total, items:[BuildingSummary]}` | none known | none | none | feasible |
| Get building with transactions | all units and transactions in a building, RCN details | A `map/transactions/visible/{slug}`, A `avg-price-trend/building/{id}` (1 km neighborhood trend) | `building_slug`, `property?` | `Building {…, units[{transactions[]}], neighborhood_trend?}` | large responses (189 KB for 86 units), trimmed | `buildings get <slug>` | `get_building` | implemented |
| Transaction statistics over time | monthly medians/averages, counts | A `monthly-transaction-stats` (city/county/street), A `avg-price-trend/city/{city}` (quarterly), A `statystyki/powiat-price-trend` | `scope: city\|powiat\|street`, `id`, `property`, `granularity: month\|quarter` | `[{period, count, median_price_m2, avg_price_m2, median_area, median_amount, …}]` | latest months incomplete (RCN lag); months with 0 transactions return zeros, treated as missing | `stats transactions …` | `get_transaction_statistics` | implemented |
| Transaction count / histogram | count, price and area distribution | A `transaction-count`, `transaction-*-distribution` | `city`, filters, `powiat_ids?`, `building_id?` | as for offers | slow on a cache miss (2-5 s) | none | none | feasible |
| City / county ranking | transaction count, prices, changes | A `city-transaction-stats`, A `map/powiat-stats` | `property?`, `sort`, `limit` | `[{city, count, price_m2, change_pct…}]` | period and base of changes unknown; `avg_` may be a median; city and county counts inconsistent (T10, T44) | `stats cities` | `rank_locations` | implemented |

## Valuation

| Capability | Data | Request(s) | Input | Output | Limitations | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Value a property | estimated value, price/m2, comparable transactions, radius, trend | A `standalone-valuation?area&lat&lng&address` | `lat`, `lng`, `area_m2`, `address?` | `{estimated_value, price_per_m2, radius_m, period_months, comparables[top N], stats}` | needs coordinates; no confirmed address-to-lat/lng geocoding (T8); 180 KB response is trimmed; `distance` rounded to 50 m | `valuation estimate …` | `estimate_property_value` | implemented |

## External statistics

| Capability | Data | Request(s) | Input | Output | Limitations | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| GUS/NBP statistics | construction (completed/started), average area, demographics, unemployment, wages, NBP prices | B `/statystyki/statystyki-rzadowe/{loc}` | `location` (69 options), `dataset` | time series per dataset | RSC only; several `data` props to tell apart by shape | `stats government <loc> <dataset>` | `get_government_statistics` | implemented |
| Listing portal statistics | daily sell/rent series x 2 sources | A `announcement-stats` | `region`, `property` | series | meaning of `blue/green` and `value` unknown; `polska` empty (T13) | none | none | unclear |

## Deferred

| Capability | Source | Reason |
|---|---|---|
| Price transparency violation reports | B `/zglos-dewelopera/mapa-zgloszen` | niche; easy to add later |
| Building outline, flood/Airbnb layers, county borders | A `building-outline`, CDN pmtiles, `/geo/powiaty.geojson` | geometric data has little value for an LLM |
| Bulk dumps (`powiat-sales`, `rawTransactions`) | A / B | too large for MCP |
| Valuation PDF | A `valuation-pdf` | rate limit, binary |
| Loan calculators | client logic | not service data |
| Writing (violation and error reports) | C + Turnstile | the service has write actions; this project is read-only and never calls them |

## Design principles for the tools

- List results always return `total` and a truncation indicator, so the model knows to narrow the filters.
- Identifiers in outputs are those accepted by the "get" tools: `investment_slug`, `offer_id`, `building_slug`, `developer_slug`, `city_slug`.
- Large arrays (comparable transactions, investment offers) are trimmed with a `limit` parameter and an `omitted` field.
