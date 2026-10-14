# Raw JSON API responses

Complete response bodies of `GET /api/*` endpoints, byte for byte as the service sent them. The samples in `docs/discovery/samples/api.*.json` are trimmed to 3 elements per array; these files are complete, for tests that need every element (aggregates).

| File | Request target | Response | Size |
|---|---|---|---|
| `city_sales_sopot.json` | `/api/offers/city-sales/sopot` | 200, `{citySlug, investments ×2, sales ×6}` (the same offers as the sample `api.city_sales_sopot`) | 815 B |
| `city_sales_krakow.json` | `/api/offers/city-sales/krakow` | 200, 143 investments (all `active`), 7,325 sales (all `active`), 67 distinct `developerSlug` values, no `null` `amount`/`size`/`priceSqm`; `priceSqm` = `amount / size` to 0.01 for every sale | 711,642 B |

## Provenance

- Captured on 2026-10-13 with the package's own client (`deweloperuch_mcp`), one request per file, before `get_market_statistics` was built.
- Response headers of both: `Cache-Control: public, max-age=28800, s-maxage=300, stale-while-revalidate=3600`.
- In the same minute the offers list `/ceny-ofertowe/krakow/mieszkania?perPage=10` reported `total` 7,307, so the Kraków dump holds 18 more offers. The cause is [W] (perhaps anomalies hidden from the list).
- Content: offer ids, prices, areas, investment and developer slugs. There is no personal data, so nothing was replaced.

## Rules

- The files are byte-exact copies: never edit, reformat or re-save them.
- Never overwrite a file. A new observation is a new file, described in the table above with its source and date.
- Captures are live requests to the service: keep them rare, and replace any personal data with `"[usunięte]"`, as in the samples.

## Used by

`tests/support/providers/rsc.py` (`CITY_SALES`) and `tests/support/providers/routes/city_sales.py` (the `city-sales` routes), and through them the contract, unit, safeguards and characterization tests.
