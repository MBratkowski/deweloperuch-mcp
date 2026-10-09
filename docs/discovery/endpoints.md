# Katalog endpointów JSON (`/api/*`) i server actions

Wszystkie endpointy: `GET`, same-origin `https://deweloperuch.pl`, bez sesji/cookies, odpowiedź `application/json`. Status [P] oznacza, że endpoint został wywołany i odpowiedź zapisano w `samples/api.<plik>.json`. Parametry oznaczone (UI) są wysyłane przez kod klienta; ich efekt nie zawsze był testowany osobno.

Konwencje wartości:
- `citySlug`: ASCII slug miasta (`warszawa`, `krakow`, `gdansk`, …); `polska` = cały kraj (tylko w routingu stron, nie w API)
- kwoty w PLN, powierzchnie w m²
- `variant=transactions` przełącza słowniki z ofert na transakcje RCN; `propertyType` dla transakcji: `flat` (domyślnie) | `house` | `both`

---

## 1. Lokalizacje i autocomplete

### `GET /api/popular-search-items` [P]
Startowe podpowiedzi wyszukiwarki.
- Query: `variant` (`transactions`), `propertyType` (`flat`|`house`; tylko z `variant=transactions`)
- Response: `{ cities: [{name, slug, woj, offerCount}], developers: [{name, slug, offerCount}], investments: [{name, slug, offerCount}] }`
- Przy `variant=transactions` pole `offerCount` oznacza **liczbę transakcji**, a nie ofert [P]. Nazwa pola się nie zmienia.
- Cache: `max-age=28800`. Źródło UI: wyszukiwarka w hero (chunk `1936`, `2438`).
- Sample: `api.popular.json`, `api.popular_tx.json`

### `GET /api/cities?q=&limit=` [P]
- Query: `q` (fragment nazwy), `limit` (UI: 8), `variant`, `propertyType`
- Response: `{ cities: [nazwa], cityMappings: [{city, city_slug, offerCount}], hasMore, total, page }`
- Zwraca też miejscowości z 0 ofert. Paginacja (`page`) [H]: pola są w odpowiedzi, ale parametru nie testowano.
- Sample: `api.cities_q.json`

### `GET /api/city-lookup?city=<nazwa|slug>[&source=transactions]` [P]
- Normalizuje nazwę lub slug miasta do `{city, city_slug}`.
- Sample: `api.city_lookup.json`

### `GET /api/location-search?q=&limit=` [P]
- Query: `q`, `limit` (UI: 6), `variant`, `propertyType`
- Response: `{ suggestions: [{kind, city, citySlug, district, street?, count, lat, lng}] }`
- `kind` ∈ {`district`, `street`} zaobserwowane [P]; inne wartości [H]. `count` = liczba ofert/transakcji w obszarze [W].
- Sample: `api.location_search.json`

### `GET /api/city-districts?citySlug=` [P]
- Query: `citySlug`, `variant`, `propertyType`
- Response: `{ districts: [{name, count}] }`, posortowane malejąco po `count`
- Sample: `api.city_districts.json`

### `GET /api/investment-streets?q=&limit=&citySlug=` [P]
- Ulice z inwestycjami (w trybie transakcji: z budynkami RCN [W]).
- Query: `q` (≥2 znaki, inaczej bez filtra), `limit` (UI: 10), `citySlug`, `variant`, `propertyType`
- Response: `{ results: [{name, fullName, citySym, cityName, citySlug, investmentCount}], cityCenter: {lat, lng} }`
- Dopasowanie po podciągu (`q=pu` zwraca „Kacpury 11”) [P]
- Sample: `api.investment_streets.json`

### `GET /api/map/city-powiats/{citySlug}` [P]
- Mapuje miasto na powiaty RCN: `{ powiatIds: [int], primaryPowiatId: int }` (Warszawa → 302, Sopot → 208)
- Cache 24 h. Sample: `api.city_powiats_waw.json`

### `GET /api/building-outline?lat=&lng=[&street=]` [P]
- Obrys budynku: `{ polygon: GeoJSON Polygon }`. Źródło (OSM?) [H]. Cache 30 dni.
- Sample: `api.building_outline.json`

---

## 2. Oferty deweloperów (ceny ofertowe)

### `GET /api/developers?q=&limit=` [P]
- Query: `q`, `limit` (UI: 5) oraz kontekst wyszukiwania: `city`, `minPrice`, `maxPrice`, `minSize`, `maxSize` (UI)
- Response: `{ developers: [{name, slug, offerCount}], hasMore, total, page }`
- Sample: `api.developers_q.json`

### `GET /api/investments?q=&limit=` [P]
- Jak wyżej. Response: `{ investments: [{name, slug, offerCount}], hasMore, total, page }`
- Sample: `api.investments_q.json`

### `GET /api/offers/city-sales/{citySlug}` [P]
- **Zrzut wszystkich aktywnych ofert w mieście** w kompaktowej postaci.
- Response: `{ citySlug, investments: [{id, slug, developerSlug, status}], sales: [{id, investId, amount, size, priceSqm, status}] }`
- Warszawa: 278 inwestycji, 13 351 ofert, 1,3 MB [P]. Wszystkie `status: active` [P]. Czy archiwalne bywają włączane: [H].
- Cache CF 5 min. Używany w layoutach list ofert (`ceny-ofertowe/[city]/mieszkania|inwestycje`).
- Sample: `api.city_sales_sopot.json`

### `GET /api/map/investments?…` [P]
- Inwestycje z agregatami do mapy.
- Query (UI): `citySlug`, `developer` (slug), `project` (slug inwestycji), `price`, `size`, `pricePerM2` (zakresy `min-max`), `rooms`, `floor`, `priceChange` (`decrease,increase,no_change`), `includeArchived=true`
- Response: `[{invest_id, latitude, longitude, name, slug, city, city_slug, street, district, status, avg_amount, avg_size, avg_price_sqm, avg_*_archived, avg_*_total, active_offers, total_offers, developer: {developer_id, name, slug}}]`
- Sample: `api.map_investments_sopot.json`

### `GET /api/map/investments/visible/{investmentSlug}` [P]
- **Pełna inwestycja z wszystkimi ofertami** (aktywne i archiwalne).
- Response: inwestycja (`invest_id, developer_id, city, city_slug, street, latitude, longitude, year_construction, name, slug, status, currency, avg_*`, `active_offers, total_offers`) + `developer {developer_id, name, description, website, slug}` + `sale: [{sale_id, invest_id, name, type, status, amount, currency, size, start_amount_difference, start_amount_difference_percent, last_event_date, last_change_event_date, creation_date}]`
- Kwoty w `sale[]` są stringami, a lat/lng stringami [P].
- Identyfikacja wyłącznie po slugu, bez miasta [P].
- Sample: `api.map_inv_visible.json`

### `GET /api/investments/{investId}/sale-events` [P]
- Historia zdarzeń cenowych **wszystkich ofert inwestycji**: `{ "<sale_id>": [{sale_event_id, event_type, event_data, amount, event_date, source}] }`
- Wolny przy cache MISS (~3 s). Sample: `api.inv_sale_events.json`

### `GET /api/sale-events?saleId=` [P]
- Historia jednej oferty: `{ success, saleData: {name, amount, size, currency}, events: [...] }`
- Sample: `api.sale_events.json`

### `GET /api/offer-count?…` [P]
- Liczba ofert spełniających filtry: `{ count }`
- Query: `city`, `minSize`, `maxSize`, `minPrice`, `maxPrice`, `minPricePerM2`, `maxPricePerM2`, `developer`, `investment`, `includeArchived=true`, `priceChanges` (csv), `filterAnomalies=false`
- `offer-count?city=warszawa` → 13 324, a `price-distribution.total` → 13 351. Różnica wynika prawdopodobnie z domyślnego odfiltrowania anomalii [H].
- Sample: `api.offer_count.json`

### `GET /api/price-distribution?mode=amount|perM2&…` [P] / `GET /api/size-distribution?…` [P]
- Histogram: `{ buckets, min, max, distribution: [int], total, mode?, aligned }`
- Query: jak `offer-count` (bez `priceChanges`/`filterAnomalies`) + `mode`
- Granice kubełków nie są zwracane. Trzeba je odtworzyć z `min`, `max`, `buckets`, `aligned` (logika w chunku `2438`, moduł `84462`). Ostatni kubełek to „i więcej” [H].
- Sample: `api.price_dist_amount.json`, `api.size_dist.json`

### `GET /api/valuation-pdf?investSlug=&saleId=&city=` [kod, nie wywoływano]
- Generuje PDF „opinia” dla oferty. Jawny rate limit: `429` + `Retry-After`. Ciężka operacja, poza MVP.

---

## 3. Transakcje RCN (ceny transakcyjne)

### `GET /api/transaction-count?…` [P]
- `{ count }`. Query: `city`, `minSize`, `maxSize`, `minPrice`, `maxPrice`, `minPricePerM2`, `maxPricePerM2`, `rooms` (csv), `floors` (csv), `investRcnId`, `powiatRcnIds` (csv), `filterPolygon`, `classifications`, `filterFlipped=true`, `propertyType` (`house`|`both`; brak = mieszkania)
- Sample: `api.tx_count.json`

### `GET /api/transaction-price-distribution?mode=…` [P] / `GET /api/transaction-size-distribution?…` [P]
- Histogramy jak dla ofert. Bywają wolne przy MISS (2–5 s).

### `GET /api/map/powiat-stats[?type=house|both]` [P]
- Wszystkie powiaty (369) z agregatami za cały okres: `[{powiat_rcn_id, nazwa, transaction_count, avg_price_sqm, avg_size, avg_amount}]`
- Sample: `api.powiat_stats.json`

### `GET /api/map/powiat-investments/{powiatId}[?type=house]` [P]
- Budynki RCN w powiecie z agregatami: `{powiatId, powiatName, investments: [{id, lat, lng, name, slug, city, citySlug, street, district, avgAmount, avgSize, avgPriceSqm, transactions, lastEventDate}]}`
- Sopot: 1 404 budynki, 419 KB.

### `GET /api/map/powiat-sales/{powiatId}[?type=house]` [P]
- **Zrzut wszystkich transakcji w powiecie**: `{powiatId, powiatName, investments: [...], sales: [{id, investId, priceSqm, amount, size, rooms, floor, type, lastEventDate, isFlipped, classification}]}`
- Sopot: 6 636 transakcji, 1,6 MB. Warszawa szacunkowo ~80 MB [W]. **Nie używać w MCP**.

### `GET /api/map/transactions/visible/{investRcnSlug}[?type=house]` [P]
- **Budynek RCN z pełną historią transakcji**: `{invest_rcn_id, name, city, city_slug, street, slug, latitude, longitude, avg_amount, avg_size, avg_price_sqm, transactions, source_rcn, sale: [{sale_rcn_id, name, amount, amount_sqm, floor, floor_number, rooms, rooms_number, type, currency, size, start_amount_difference(_percent), total_events, creation_date, last_event_date, is_flipped, last_transaction_classification, sale_event_rcn: [{sale_event_rcn_id, amount, amount_sqm, currency, buyerType, sellerType, classification, transactionType, marketType, participation, creation_date, additionalData: {surowy rekord RCN}}]}]}`
- 189 KB dla budynku z 86 lokalami. Sample: `api.tx_visible.json`

### `GET /api/sale-events-rcn/batch?ids=<sale_rcn_id,…>` [P]
- Historia cen lokali: `{ "<id>": [{amount, creation_date}] }`
- Sample: `api.rcn_batch.json`

---

## 4. Statystyki

### `GET /api/monthly-transaction-stats?propertyType=&citySlug=|powiatRcnId=|street=` [P]
- Miesięczne agregaty transakcji: `{ scope: {label}, data: [{month, transaction_count, med_price_sqm, avg_price_sqm, med_size, avg_size, med_amount, avg_amount}] }`
- `propertyType`: `mieszkania` [P], `domy` [H]
- Ostatnie miesiące mają mało transakcji (opóźnienie zasilania RCN): `2026-07` ma 2 transakcje [P]
- Sample: `api.monthly_tx.json`

### `GET /api/statystyki/powiat-price-trend?powiatId=` [P]
- Kwartalnie: `[{quarter, med_price_sqm, trimmed_avg_price_sqm, avg_35_60_price_sqm, transaction_count}]`
- Sample: `api.powiat_trend_208.json`

### `GET /api/avg-price-trend/city/{citySlug}[?type=house[&metric=plot]]` [P]
- Kwartalnie: `{ data: [{period, avgPriceSqm, count}], scope: "city", scopeName }`
- Sample: `api.avg_trend_city.json`

### `GET /api/avg-price-trend/building/{investRcnId}[?type=house[&metric=plot]]` [P]
- Trend dla sąsiedztwa budynku: `{ data: [...], radiusKm: 1 }`. Wymaga **numerycznego** `invest_rcn_id`; slug daje `400 {"error":"Valid investRcnId is required"}` [P].
- Sample: `api.avg_trend_building.json`

### `GET /api/city-transaction-stats` [P]
- Ranking miast (2 448): `[{city, city_slug, transaction_count, avg_price_sqm, avg_size, avg_amount, transaction_count_change, price_sqm_change, avg_size_change, amount_change}]`
- Okres agregacji i baza `*_change` są nieznane [H]. `avg_price_sqm`=16413 dla Warszawy jest prawie równe medianie 16414 z mapy statystyk, więc pole może mimo nazwy zawierać medianę [H].
- 548 KB, cache 24 h. Sample: `api.city_tx_stats.json`

### `GET /api/announcement-stats?region=&propertyType=` [P]
- Dzienne serie z portali ogłoszeniowych: `{ blueRent, blueSell, greenRent, greenSell: [{date: "<epoch ms jako string>", value}] }`
- `region`: slug miasta (np. `warszawa`), `top-6` [W z linków]. `polska` zwraca puste tablice [P].
- `propertyType`: `mieszkania` [P], `domy`, `dzialki` [W, w UI mapowane na „działki”]
- Znaczenie „blue/green” (dwa portale?) i `value` (liczba ogłoszeń? mediana ceny?) [H]
- Sample: `api.ann_waw.json`

---

## 5. Wycena

### `GET /api/standalone-valuation?area=&lat=&lng=[&address=]` [P]
- Wycena porównawcza na podstawie transakcji RCN w promieniu.
- Response: `{ estimatedValue, estimatedPricePerSqm, latitude, longitude, area, generatedAt, radiusKm, periodMonths, radiusLevel, areaElasticity, trendMonthlyPct, buildingTransactionCount, stats: {averagePricePerSqm, medianPricePerSqm, minPricePerSqm, maxPricePerSqm, count}, transactions: [{address, unitNumber, area, pricePerSqm, totalPrice, date, floor, distance, latitude, longitude, marketType, isSamePrimaryInvestment, saleRcnId, investRcnSlug, investRcnCitySlug, excluded}], buildings: [...], estimationContext: {pool, …}, radiusPool: [...], radiusCeilingM }`
- 180 KB, głównie `radiusPool` (279 pozycji). Do MCP przekazujemy tylko wynik i top porównania.
- `radiusLevel`: `sasiedztwo` [P]; inne poziomy [H]
- Identyczny wynik daje server action `fetchStandaloneValuation` [P]
- Sample: `api.standalone_val.json`

---

## 6. Server actions (szczegóły wywołania)

```
POST /<dowolna strona, np. /wycena>
Accept: text/x-component
Content-Type: text/plain;charset=UTF-8
Next-Action: <40+ hex, z chunków JS>
Next-Router-State-Tree: <url-encoded JSON drzewa routera>   # wysyłane przez UI; czy wymagane: [H]
Body: [ {argumenty} ]

→ 200 text/x-component
0:{"a":"$@1","f":"","b":"<buildId>"}
1:<wynik JSON>
```

Aktualne ID (build `KD_IOP6Grqba7xa86pGVG`): uruchom `python3 recon/scan_bundles.py`.
