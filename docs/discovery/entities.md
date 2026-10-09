# Encje, identyfikatory, relacje

Serwis ma dwa niezależne „światy” danych, które łączą się tylko przez lokalizację:

```
 RYNEK PIERWOTNY — OFERTY                       TRANSAKCJE — RCN (GUGiK)
 ────────────────────────                       ────────────────────────
 Developer                                       Powiat (powiat_rcn_id)
  developer_id:int, slug                          │ 1..n
  │ 1..n                                          ▼
  ▼                                              SourceRcn (source_rcn_id, np. 9 = Warszawa)
 Investment  ◄── slug = globalne ID              │
  invest_id:int, slug, city_slug,                ▼
  lat/lng, status active|archived               InvestRcn  = BUDYNEK / ADRES
  │ 1..n                                          invest_rcn_id:int, slug "ulica-x-12-miasto",
  ▼                                               kind flat|house, lat/lng
 Sale        = OFERTA (lokal w cenniku)           │ 1..n
  sale_id:int, name "D1.1.1.4",                   ▼
  amount, size, status active|archived          SaleRcn    = LOKAL / NIERUCHOMOŚĆ
  │ 1..n                                          sale_rcn_id:int, name = id lokalu EGiB
  ▼                                               "146517_8.0502.253_BUD.239_LOK"
 SaleEvent   = ZDARZENIE CENOWE                   │ 1..n
  sale_event_id:int, event_type,                  ▼
  amount, event_date, source                    SaleEventRcn = TRANSAKCJA
                                                  sale_event_rcn_id:int, amount, amount_sqm,
                                                  date, buyer/seller, classification,
                                                  marketType, additionalData (surowy RCN)

 Lokalizacja (wspólna): City (city_slug) ─ District (nazwa) ─ Street (nazwa)
                        City → Powiat: /api/map/city-powiats/{city}
 Łącznik ofert z RCN: wycena / raport mieszkania (transakcje w promieniu od lat/lng inwestycji)
```

## Identyfikatory

| Encja | ID | Gdzie używany | Stabilność |
|---|---|---|---|
| City | `city_slug` (ASCII) | ścieżki stron, `citySlug`/`city` w API | [P] stabilny; `polska` = cały kraj (tylko strony) |
| District | nazwa (`Mokotów`) | `filterDistrict`, `city-districts` | [P] brak ID, tekst |
| Powiat | `powiat_rcn_id` (int) | `map/powiat-*`, `powiat-price-trend`, `filterPowiat` | [P] |
| Developer | `slug` (+ `developer_id`) | strony, `developer=`, `filterDeveloper=` | [P] slug używany wszędzie; `developer_id` pomocniczy (bywa `0` w propsach [P]) |
| Investment | `slug` (+ `invest_id`) | `map/investments/visible/{slug}`, strony | [P] slug rozwiązuje inwestycję bez miasta/dewelopera. Starsze slugi bez sufiksu miasta (`smolna`), nowsze z sufiksem (`mokotow-sportowy-13-warszawa`) [P] |
| Investment (num) | `invest_id` | `/api/investments/{id}/sale-events` | [P] |
| Sale (oferta) | `sale_id` (int) | `/api/sale-events?saleId=`, `fetchBatchPriceChartData` | [P] |
| Sale → strona | `raport-mieszkania-{slugify(name)}` | URL raportu | [W] ryzyko kolizji |
| InvestRcn (budynek) | `slug` i `invest_rcn_id` | slug: strony + `map/transactions/visible/{slug}`; id: `avg-price-trend/building/{id}`, `transaction-count?investRcnId=` | [P] oba potrzebne |
| SaleRcn (lokal) | `sale_rcn_id` | `sale-events-rcn/batch?ids=` | [P] |
| SaleEventRcn | `sale_event_rcn_id`; zewnętrznie `additionalData.transactionId` (`PL.PZGIK.…`) | — | [P] |

**Uwaga o nazwach**: w świecie RCN backend nazywa budynek „invest”, a lokal „sale”. W propsach stron budynku pole nazywa się nawet `invest_id`, choć zawiera `invest_rcn_id` [P]. Model domenowy powinien używać nazw `Building`, `Unit`, `Transaction`.

## Słowniki wartości (zaobserwowane)

| Pole | Wartości | Źródło |
|---|---|---|
| Investment/Sale `status` | `active`, `archived` | [P] |
| `SaleEvent.event_type` | `OFFER_EVENT`, `ARCHIVED_EVENT`, `RESTORED_EVENT` | [P]; inne (np. zmiana ceny jako osobny typ?) [H] |
| `last_event_type` (lista ofert) | `PRICE_INCREASE`, `PRICE_DECREASE`, `NO_CHANGE` | [P] |
| `SaleEvent.source` | `ANNOUCMENT` (sic), `ANNOUCMENT_PR`, `""`; `event_data` może zawierać `{"source":"scraper_pr"}` | [P] |
| filtr zmian ceny (URL) | `decrease`, `increase`, `no_change` | [P z kodu] |
| `classification` (RCN) | `transakcja`, `udzial`, `anomalia_down`, `anomalia_up`, `hurt`, `rzadowa`, `egzekucja`, `bonifikata` | [P] (Warszawa, Sopot) |
| `filterClassification` (URL) | brak (= `transakcja`), `anomalie`, `wszystkie` | [P z kodu] |
| `marketType` | `pierwotny`, `wtorny` | [P] |
| `buyerType` / `sellerType` | `osobaFizyczna`, `osobaPrawna` | [P]; inne [H] |
| `transactionType` | `wolnyRynek` | [P]; inne [H] |
| `type` (RCN) | `mieszkalna` (lokal), `mieszkalny` (budynek/dom) | [P] |
| `kind` (adresy) | `flat`, `house` | [P] |
| `is_flipped` | bool, oznacza odsprzedaż w krótkim czasie [H] | [P] |
| `participation` | ułamek udziału, np. `1/1` | [P] |
| `radiusLevel` (wycena) | `sasiedztwo` | [P]; inne [H] |

## Normalizacja potrzebna w warstwie DTO → domena [P]

- Kwoty/metraże: `number` albo `string` (`"amount": "994012"`, `"size": "55.25"`), zależnie od endpointu.
- Współrzędne: `number` albo `string`.
- Daty: `YYYY-MM-DD`, ISO `…T00:00:00.000Z`, `YYYY-MM`, `YYYY-Qn`, epoch ms jako string (`announcement-stats`).
- Pola `avg_*` mogą zawierać medianę (`city-transaction-stats`) [H].
- Puste wartości: `""` zamiast `null` (`street`, `district`, `source`, `event_data`).
