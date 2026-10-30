# Raw JSON API responses

Complete response bodies of `GET /api/*` endpoints, byte for byte as the service sent them. The samples in `docs/discovery/samples/api.*.json` are trimmed to 3 elements per array; these files are complete, for tests that need every element (aggregates).

| File | Request target | Response | Size |
|---|---|---|---|
| `city_sales_sopot.json` | `/api/offers/city-sales/sopot` | 200, `{citySlug, investments ×2, sales ×6}` (the same offers as the sample `api.city_sales_sopot`) | 815 B |
| `city_sales_krakow.json` | `/api/offers/city-sales/krakow` | 200, 143 investments (all `active`), 7,325 sales (all `active`), 67 distinct `developerSlug` values, no `null` `amount`/`size`/`priceSqm`; `priceSqm` = `amount / size` to 0.01 for every sale | 711,642 B |
| `offer_snapshot_wroclaw_20261030.json` | `/api/map/offer-snapshot/wroclaw` | 200, `{citySlug, asOf "2026-10-30", investments ×110, sales ×5,836}`; each sale a row `[id, investId, status, amount, priceSqm, size, change since the first price]`, status 0 in every row, `priceSqm` = `amount / size` to 0.01 in every row, 46 distinct `developerSlug` values; the same day `/statystyki/wroclaw/oferty` stated 5,836 offers, 110 investments, 46 developers and a median of 14,600 PLN/m² | 261,340 B |
| `city_tx_stats_20261015.json` | `/api/city-transaction-stats` | 200, 2,529 places, `avg_price_sqm` and `avg_amount` always integers, `avg_size` a fraction in 2,234 rows (Warsaw 48.8); exactly one row with `avg_price_sqm`, `avg_size` and `avg_amount` all 0: `Ignatki-osiedle` (`ignatki-osiedle`, 8 transactions, `price_sqm_change` -100); no `null`, empty or negative `avg_*`; 1,628 places with at most 2 transactions, 258 with at least 20, 108 with at least 50 | 565,898 B |
| `powiat_stats_20261015.json` | `/api/map/powiat-stats` | 200, 380 powiats (369 in the sample `api.powiat_stats` of 2026-10-09), no `avg_*` equal to 0; the fewest transactions is 17 | 49,960 B |
| `monthly_tx_warszawa_20261015.json` | `/api/monthly-transaction-stats?propertyType=mieszkania&citySlug=warszawa` | 200, `scope.label` `city`, 67 months 2021-01..2026-07; the tail: 2026-03 1,390, 2026-04 987, 2026-05 22, 2026-06 0 (every measure 0), 2026-07 35 with `med_price_sqm` 33,176 (about twice the months before); 2026-08 and 2026-09 absent | 10,750 B |
| `standalone_val_cisna_20261015.json` | `/api/standalone-valuation?area=50&lat=49.2167&lng=22.3333` | 200, `estimatedValue` 202,000, `estimatedPricePerSqm` 4,040, `radiusKm` 1 equal to `radiusCeilingM` 1000, `radiusLevel` `okolica` (the sample `api.standalone_val` has `sasiedztwo`), `periodMonths` 24, `stats.count` 2 (2,302 and 5,778 PLN/m²), 2 transactions, both `excluded: false`, in one building (`cisna`) | 2,823 B |
| `tx_visible_cisna_20261015.json` | `/api/map/transactions/visible/cisna` | 200, building 152198 (Cisna, no street), 6 units with 7 transactions: 5 `transakcja`, 1 `udzial` (participation 1/2), 1 `egzekucja`; the service's `transactions` counter is 5 and `avg_amount` 274,600 and `avg_size` 72.08 are the means of the 5 `transakcja` transactions, `avg_price_sqm` 3,809.76 their summed price over their summed area | 15,014 B as sent; the file differs by the replaced `additionalInfo` values |
| `avg_trend_building_152198_20261015.json` | `/api/avg-price-trend/building/152198` | 200, `{"data":[],"radiusKm":0}`: no quarters and a radius of 0 for the building of `tx_visible_cisna_20261015.json` | 24 B |
| `avg_trend_city_warszawa_20261016.json` | `/api/avg-price-trend/city/warszawa` | 200, `scope` `city`, `scopeName` null, 39 quarters 2017-Q1..2026-Q3; the tail: 2025-Q3 3,902, 2025-Q4 3,605, 2026-Q1 3,721, 2026-Q2 1,034, 2026-Q3 37 with `avgPriceSqm` 33,176; each quarter's `count` is about 2% above the sum of its months in `monthly_tx_warszawa_20261015.json` (2026-Q1 3,721 vs 3,643) | 2,133 B |
| `monthly_tx_karpacz_20261016.json` | `/api/monthly-transaction-stats?propertyType=mieszkania&citySlug=karpacz` | 200, `scope.label` `city`, 60 months 2021-01..2025-12 (no rows after 2025-12), a small town: median 1 transaction a month, 26 months with 0 (every measure 0), at most 7 | 8,824 B |

## Provenance

- `city_sales_*`: captured on 2026-10-13 with the package's own client (`deweloperuch_mcp`), one request per file, before `get_market_statistics` was built.
- Response headers of both: `Cache-Control: public, max-age=28800, s-maxage=300, stale-while-revalidate=3600`.
- In the same minute the offers list `/ceny-ofertowe/krakow/mieszkania?perPage=10` reported `total` 7,307, so the Kraków dump holds 18 more offers. The cause is [W] (perhaps anomalies hidden from the list).
- Content: offer ids, prices, areas, investment and developer slugs. There is no personal data, so nothing was replaced.
- `offer_snapshot_wroclaw_20261030.json`: captured on 2026-10-30 with one request outside the package's client, while looking for the successor of `city-sales` after the service's redesign of 2026-10-29; byte-exact. Content: offer ids, prices, areas, investment names, streets, coordinates and developer names and slugs (companies only). There is no personal data, so nothing was replaced.
- `*_20261015.json`: captured on 2026-10-15 with the package's own client (`HttpClient`, JSON headers), six requests in one sequential series through the shared limiter, no STOP before or after, for the flow A changes to the RCN tools (zeros as missing values, small samples, incomplete latest months). The building is the one of the valuation's comparable transactions; its trend is the next request with the building's `invest_rcn_id`.
- `*_20261016.json`: captured on 2026-10-16 the same way, two requests in one series, no STOP before or after, after the review of the incomplete-period rule asked for real quarters and a small town. Both `s-maxage=86400`; byte-exact, no personal data.
- `Cache-Control` of the 2026-10-15 captures: `s-maxage=86400` (city stats, monthly stats, building trend), `s-maxage=3600` (powiat stats, building), `s-maxage=300` (valuation).
- Personal data: every `additionalInfo` value of `tx_visible_cisna_20261015.json` (14) was replaced with `"[usunięte]"` in the raw text, the rest of the body is byte-exact. The other 2026-10-15 files are byte-exact; they hold RCN unit identifiers (`unitNumber`, as in the samples), no personal data.

## Rules

- The files are byte-exact copies: never edit, reformat or re-save them.
- Never overwrite a file. A new observation is a new file, described in the table above with its source and date.
- Captures are live requests to the service: keep them rare, and replace any personal data with `"[usunięte]"`, as in the samples.

## Used by

- `city_sales_*`: `tests/support/providers/rsc.py` (`CITY_SALES`) and `tests/support/providers/routes/offer_snapshot.py`, which serves their offers re-shaped as `offer-snapshot` rows (the routes of Sopot and Kraków), and through them the contract, unit, safeguards and characterization tests.
- `offer_snapshot_wroclaw_20261030.json`: `tests/support/providers/rsc.py` (`OFFER_SNAPSHOT_WROCLAW`), the Wrocław route of `tests/support/providers/routes/offer_snapshot.py` and `tests/contract/api/dto/test_city_sales_dto.py`.
- `city_tx_stats_20261015.json`, `powiat_stats_20261015.json`: `tests/support/providers/routes/rankings.py` (`CITIES_2026_10_15`, `POWIATS_2026_10_15`, `captured_ranking_routes`).
- `monthly_tx_warszawa_20261015.json`, `avg_trend_city_warszawa_20261016.json`, `monthly_tx_karpacz_20261016.json`: `tests/support/builders/transactions.py` (`MONTHLY_WARSZAWA`, `QUARTERLY_WARSZAWA`, `MONTHLY_KARPACZ`).
- `standalone_val_cisna_20261015.json`: `tests/support/providers/routes/valuation.py` (`CISNA`, `cisna()`, `cisna_route`).
- `tx_visible_cisna_20261015.json`, `avg_trend_building_152198_20261015.json`: `tests/support/providers/routes/buildings.py` (`CISNA_BODY`, `CISNA_TREND_BODY`, `cisna_routes()`).

Through them the contract, unit and characterization tests of the RCN tools read these files.
