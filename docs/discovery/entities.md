# Entities, identifiers, relations

The service has two independent data "worlds" that connect only through location:

```
 PRIMARY MARKET: OFFERS                          TRANSACTIONS: RCN (GUGiK)
 ----------------------                          -------------------------
 Developer                                       Powiat (powiat_rcn_id)
  developer_id:int, slug                          | 1..n
  | 1..n                                          v
  v                                              SourceRcn (source_rcn_id, e.g. 9 = Warsaw)
 Investment   (slug = global ID)                  |
  invest_id:int, slug, city_slug,                 v
  lat/lng, status active|archived                InvestRcn  = BUILDING / ADDRESS
  | 1..n                                          invest_rcn_id:int, slug "street-x-12-city",
  v                                               kind flat|house, lat/lng
 Sale        = OFFER (unit in the price list)     | 1..n
  sale_id:int, name "D1.1.1.4",                   v
  amount, size, status active|archived          SaleRcn    = UNIT / PROPERTY
  | 1..n                                          sale_rcn_id:int, name = EGiB unit id
  v                                               "146517_9.5795.356_BUD.239_LOK"
 SaleEvent   = PRICE EVENT                        | 1..n
  sale_event_id:int, event_type,                  v
  amount, event_date, source                    SaleEventRcn = TRANSACTION
                                                  sale_event_rcn_id:int, amount, amount_sqm,
                                                  date, buyer/seller, classification,
                                                  marketType, additionalData (raw RCN)

 Shared location: City (city_slug) - District (name) - Street (name)
                  City -> Powiat: /api/map/city-powiats/{city}
 Link between offers and RCN: valuation / unit report
                  (transactions within a radius of the investment's lat/lng)
```

## Identifiers

| Entity | ID | Where used | Stability |
|---|---|---|---|
| City | `city_slug` (ASCII) | page paths, `citySlug`/`city` in the API | [P] stable; `polska` = whole country (pages only) |
| District | name (`Mokotów`) | `filterDistrict`, `city-districts` | [P] no ID, text |
| Powiat | `powiat_rcn_id` (int) | `map/powiat-*`, `powiat-price-trend`, `filterPowiat` | [P] |
| Developer | `slug` (+ `developer_id`) | pages, `developer=`, `filterDeveloper=` | [P] slug used everywhere; `developer_id` auxiliary (sometimes `0` in props [P]) |
| Investment | `slug` (+ `invest_id`) | `map/investments/visible/{slug}`, pages | [P] the slug resolves an investment without city/developer. Older slugs without a city suffix (`smolna`), newer with a suffix (`mokotow-sportowy-13-warszawa`) [P] |
| Investment (num) | `invest_id` | `/api/investments/{id}/sale-events` | [P] |
| Sale (offer) | `sale_id` (int) | `/api/sale-events?saleId=`, `fetchBatchPriceChartData` | [P] |
| Sale → page | `raport-mieszkania-{slugify(name)}` | report URL | [W] collision risk |
| InvestRcn (building) | `slug` and `invest_rcn_id` | slug: pages + `map/transactions/visible/{slug}`; id: `avg-price-trend/building/{id}`, `transaction-count?investRcnId=` | [P] both needed |
| SaleRcn (unit) | `sale_rcn_id` | `sale-events-rcn/batch?ids=` | [P] |
| SaleEventRcn | `sale_event_rcn_id`; externally `additionalData.transactionId` (`PL.PZGIK.…`) | — | [P] |

**Note on naming**: in the RCN world the backend calls a building "invest" and a unit "sale". In the props of building pages the field is even named `invest_id`, though it holds `invest_rcn_id` [P]. The domain model should use the names `Building`, `Unit`, `Transaction`.

## Value dictionaries (observed)

| Field | Values | Source |
|---|---|---|
| Investment/Sale `status` | `active`, `archived` | [P] |
| `SaleEvent.event_type` | `OFFER_EVENT`, `ARCHIVED_EVENT`, `RESTORED_EVENT` | [P]. `OFFER_EVENT` = every asking-price entry in the history (price changes too), not only the first price [P 2026-10-10, `api.sale_events.price_history`]; no separate type for a price change was observed |
| `last_event_type` (offer list) | `PRICE_INCREASE`, `PRICE_DECREASE`, `NO_CHANGE`, `NEW_OFFER` (new offer, `total_events: 1`) | [P]; `NEW_OFFER` [P 2026-10-10, `page.offers_list.sort_desc`] |
| `kind` (`location-search`) | `city`, `district`, `street` | [P 2026-10-10] |
| Slug alphabet (city, investment, developer) | `[a-z0-9-]`: 166 of 168 slugs in the samples; exceptions only in the reports map (`Metro-Art`, `Forrest`, a different entity type) | [W] |
| `SaleEvent.source` | `ANNOUCMENT` (sic), `ANNOUCMENT_PR`, `""`; `event_data` may contain `{"source":"scraper_pr"}` | [P] |
| price-change filter (URL) | `decrease`, `increase`, `no_change` | [P z kodu] |
| `classification` (RCN) | `transakcja`, `udzial`, `anomalia_down`, `anomalia_up`, `hurt`, `rzadowa`, `egzekucja`, `bonifikata` | [P] (Warsaw, Sopot) |
| `filterClassification` (URL) | none (= `transakcja`), `anomalie`, `wszystkie` | [P z kodu] |
| `marketType` | `pierwotny`, `wtorny` | [P] |
| `buyerType` / `sellerType` | `osobaFizyczna`, `osobaPrawna` | [P]; others [H] |
| `transactionType` | `wolnyRynek` | [P]; others [H] |
| `type` (RCN) | `mieszkalna` (unit), `mieszkalny` (building/house) | [P] |
| `kind` (addresses) | `flat`, `house` | [P] |
| `is_flipped` | bool, marks a resale within a short time [H] | [P] |
| `participation` | share fraction, e.g. `1/1` | [P] |
| `radiusLevel` (valuation) | `sasiedztwo`, `okolica` | [P 2026-10-15]; others [H] |

## Normalization needed in the DTO → domain layer [P]

- Amounts/areas: `number` or `string` (`"amount": "994012"`, `"size": "55.25"`), depending on the endpoint.
- Coordinates: `number` or `string`.
- Dates: `YYYY-MM-DD`, ISO `…T00:00:00.000Z`, `YYYY-MM`, `YYYY-Qn`, epoch ms as a string (`announcement-stats`).
- `avg_*` fields may contain a median (`city-transaction-stats`) [H].
- Empty values: `""` instead of `null` (`street`, `district`, `source`, `event_data`).
