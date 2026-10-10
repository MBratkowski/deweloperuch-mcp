# Strony SSR (RSC) jako źródło danych

Wyszukiwanie z filtrami, sortowaniem i paginacją oraz większość widoków szczegółowych istnieje **wyłącznie** jako strony renderowane serwerowo. Dane są w propsach komponentów klienckich w payloadzie RSC.

## Jak pobierać [P]

```
GET https://deweloperuch.pl<ścieżka>?<filtry>&_rsc=<losowy token>
RSC: 1
→ 200 text/x-component
```

- Bez `_rsc` Cloudflare zwraca zcache'owany HTML, bo ignoruje `Vary: RSC` [P].
- Alternatywa: pełny HTML i dekodowanie `self.__next_f.push([1,"…"])`. Daje te same dane, ale jest ~10× większy (942 KB vs 98 KB) [P].
- Propsy leżą w elementach `["$","$L<id>",null,{…}]`. Referencje `"$f:props:…"` / `"$8:props:…"` wskazują na wcześniej zdefiniowane fragmenty, ale propsy z danymi list są inline [P].
- Format flight (wiersze `<id>:<tag><dane>`) [P z kodu, chunk `1517-…js` ReactFlightClient z cache skanera]:
  - wiersze z długością w BAJTACH, **bez `\n` po wierszu**: `<id>:T<hexlen>,<tekst>`; tagi binarne `A O o U S s L l G g M m V` (z `T`) działają tak samo. Wiersz po nich zaczyna się bezpośrednio za danymi, więc szukanie wierszy tylko na początku linii je gubi;
  - wiersze kończone `\n`: tagi `A`–`Z` (m.in. `E` błąd), `#`, `r`, `x` oraz wiersz modelu bez tagu (`<id>:<json>`);
  - hinty `:HL…` mają pusty id.
  - Na liście ofert wiersz z `initialData` idzie zaraz za dwoma wierszami `T` z JSON-LD (`16:T5ed,…` WebPage, `19:T1a27,…` ItemList) [P 2026-10-10, fiks `tests/fixtures/rsc/warszawa_perPage10.rsc`]. Obalono: stary parser (`_JSON_ROW`, wiersze tylko na początku linii) widział tam brak `initialData`, przez co `search_offers` nie działał na żywym serwisie.
- Parser referencyjny: [`src/deweloperuch_mcp/flight.py`](../../src/deweloperuch_mcp/flight.py): `rows()`, `component_props()`, `error_digests()` (RSC) oraz `flight()` dla HTML. `find_json_after(text, "initialData")` zostaje dla `probe --prop`; `recon/flight.py` tylko reeksportuje.
- Cache-Control stron RSC: `private, max-age=28800, must-revalidate` (bez `s-maxage`; `cf-cache-status` MISS lub HIT z `age`) [P 2026-10-10, próbki z serii B; nagłówki w stderr probe'a, bez osobnej próbki].
- **Ryzyko**: nazwy propsów (`initialData`, `serverPaginationData`, …) są detalem implementacyjnym UI i mogą się zmienić bez ostrzeżenia [W]. Adapter RSC musi być izolowany i mieć testy kontraktowe na próbkach.

## Wspólne reguły list [P]

- `page`: od 1. **Maksimum 20 stron**: `page>20` zwraca stronę 20 (`pagination.page: 20`) [P].
- `perPage`: `10`, `25`, `50`, `100` zaakceptowane [P 2026-10-10: `perPage=25` → `pagination.perPage: 25`, 25 wierszy; obalono: hipoteza, że dozwolone są tylko {10, 50, 100}]. `20` i `500` dają domyślne 10 [P]. Pełna lista dozwolonych wartości nie jest znana: zaobserwowano 10, 25, 50, 100 (przyjęte) oraz 20, 500 (→ 10) [P]; inne [H] (T2 rozstrzygnięte częściowo; pełna lista: T29).
- Pułap: **2 000 rekordów na zapytanie**. `pagination.total` podaje pełną liczbę (np. 13 324), ale `totalPages` jest obcięte do 20 [P].
- `sortOrder` ∈ {`asc`, `desc`}.
- Zakresy: `min-max` (np. `filterPrice=500000-700000`). Brak dolnej granicy → `0-…`; brak górnej → wartości-wartownicy UI: cena `99999999`, cena/m² `999999`, metraż `9999` [P z kodu]. Serwer traktuje `filterPrice=0-99999999&filterSize=0-9999` jak brak filtra: `pagination.total` = 13324 = wynik bez filtrów (Warszawa) [P 2026-10-10]; wartownik cena/m² (`999999`) nie był testowany osobno [W].
- Listy: wartości po przecinku (`filterRooms=2,3`).
- `{city}` = slug miasta albo `polska` (cały kraj) [P].

---

## Ceny ofertowe

### `/ceny-ofertowe/{city}/mieszkania`: lista ofert [P]
| Parametr | Wartości | Status |
|---|---|---|
| `sortBy` | `amount`, `price_per_sqm`, `size`, `name`, `start_amount_difference_percent` | [P 2026-10-10] `amount` (asc i desc, próbka `page.offers_list.sort_desc`), `price_per_sqm`, `size`, `name`, `start_amount_difference_percent`: kolejność zgodna z wartością |
| `sortBy` (cd.) | `last_event_date` | [P 2026-10-10] przyjęty, ale pierwsze wiersze `asc` nie są uporządkowane po `last_event_date` widocznym w liście (np. 2026-10-03 przed 2026-09-03); faktyczny klucz nieznany [H] |
| `sortBy` (cd.) | `investment`, `last_amount_difference`, `last_amount_difference_percent`, `start_amount_difference` | [W z kodu], nie testowano |
| `sortBy` domyślny / nieznany | brak lub dowolny tekst (`bogus`) | [P 2026-10-10] identyczny wynik: rosnąco po `sale_id` (kolejność w bazie); nieznana wartość jest cicho ignorowana, bez błędu. Obalono: domyślne `sortBy` nie jest `amount` |
| `filterPrice`, `filterPricePerM2`, `filterSize` | zakres `min-max` | [P] (`filterPrice`, `filterSize`) |
| `filterDeveloper` | slug dewelopera | [W] |
| `filterProject` | slug inwestycji | [W] |
| `filterDistrict` | nazwa (np. `Mokotów`, URL-encoded) | [P 2026-10-10] total 1562 = `count` dzielnicy z `location-search` |
| `filterStreet` | nazwa | [W] |
| `filterPriceChange` | csv z `decrease`, `increase`, `no_change` | [P 2026-10-10] `decrease`: total 13324 → 2416. Dotyczy zmiany względem ceny początkowej (`start_amount_difference*`), nie ostatniego zdarzenia: wiersze z `last_event_type: PRICE_INCREASE` i ujemnym `start_amount_difference_percent` przechodzą. `increase`/`no_change`, wartości csv: [W] |
| `filterRooms`, `filterFloors` | csv | [P 2026-10-10] **bez efektu na liście ofert**: `filterRooms=2` i `filterFloors=1` zwracają total 13324 jak bez filtra (obalono: [W], że zawężają listę ofert; oferty nie mają pól rooms/floor). Filtry działają tylko w transakcjach |
| `filterStatus` | `archived` | [P 2026-10-10] `archived` → total 11415, same `status: archived`. `active` i inne wartości nie testowano [H] |
| `filterAnomalies` | `false` = pokaż też anomalie | [W] |
| `includeArchived` | `true` | [P 2026-10-10] total 13324 → 24739 (= 13324 aktywnych + 11415 archiwalnych) |
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
Nieznane miasto (`/ceny-ofertowe/nieistniejace-miasto/mieszkania`): HTTP **200** `text/x-component` bez propsa `initialData`; wskaźnikiem jest wiersz `E` z digestem `NEXT_HTTP_ERROR_FALLBACK;404` (`{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}`) [P 2026-10-10, fiks `tests/fixtures/rsc/unknown_city_perPage10.rsc`]. Obalono: segment `notFound` jako wskaźnik (`notFound` jest propem layoutu na każdej stronie). Klient musi rozpoznać digest (`error_digests()`), nie status HTTP ani sam brak `initialData`.
Sample: `page.offers_list.json`, `page.offers_list.filtered.json`, `page.offers_list.sort_desc.json`
`last_event_type` przyjmuje też `NEW_OFFER` (oferta bez zmian ceny, `total_events: 1`) [P 2026-10-10, `page.offers_list.sort_desc`].

### `/ceny-ofertowe/{city}/inwestycje`: lista inwestycji [P]
- `sortBy`: `name`, `active_offers`, `avg_amount`, `avg_size`, `avg_price_sqm` [P], `sum_changes`
- Props: `investments[]` (`invest_id, name, slug, city, city_slug, street, status, avg_amount, avg_size, avg_price_sqm, active_offers, total_offers, sum_start_amount_difference_plus/minus, developer{…}`), `serverPaginationData {currentPage, perPage, totalCount, totalPages, startItem, endItem}`, `initialSortBy`, `initialSortOrder`, `includeArchived`
- Sample: `page.investments_list.json`

### `/ceny-ofertowe/{city}/deweloperzy`: lista deweloperów [P]
- `sortBy`: `name`, `projectCount` [P], `totalSales`, `cityCount`, `avgSize`, `avgPrice`, `avgPricePerM2`, `sum_changes`
- Props: `developers[]` (`developer_id, name, slug, projectCount, totalSales, totalOffersCount, cities, cityCount, avgSize, avgPrice, avgPricePerM2, sum_start_amount_difference_plus/minus`), `serverPaginationData`, `filterCity`, `filterName`
- Sample: `page.developers_list.json`

### `/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`: profil dewelopera [P]
- Props: `data {developer, investments[], filteredStats, allCities, allCitiesWithSlugs, citiesStats, allInvestmentNames}`, `sale[]` (lekka lista ofert), `data[]` (dzienna oś zmian cen: `discountCount, increaseCount, discountValue, increaseValue, cumulative*`)
- Sample: `page.developer.json`

### `/ceny-ofertowe/{*}/deweloperzy/{*}/{investmentSlug}`: inwestycja [P]
- **Segmenty `{city}` i `{developer}` są ignorowane**. `/ceny-ofertowe/warszawa/deweloperzy/dom-development/nowy-targowek-vi` zwraca inwestycję ATAL [P].
- Props: `investments[1]`, `sales[]` (wszystkie, z archiwalnymi), `stats`, `data[]` (oś zmian cen)
- Zawiera to samo co `GET /api/map/investments/visible/{slug}` plus oś zmian. **Preferujemy JSON API**.
- Sample: `page.investment.json`

### `…/{investmentSlug}/raport-mieszkania-{slug(nazwa)}`: raport oferty [P]
- Slug = `slugify(sale.name)`: polskie znaki → ASCII, lowercase, usuń wszystko poza `[a-z0-9\s-]`, spacje → `-` [P z kodu]. `D1.1.1.4` → `d1114`. **Możliwe kolizje** (`D1.11.4` też da `d1114`) [W].
- Props: `property {name, investmentName, developer, address, area, offerPrice, offerPricePerSqm, latitude, longitude}`, `priceHistory[{amount, creation_date}]`, `competitors[]` (oferty o podobnym metrażu w okolicy: `investmentName, developer, distance, investSlug, developerSlug, sales[{saleId, area, price, pricePerSqm, sizeMatch}]`), `investmentSales[]`, `data` (**wycena RCN** w formacie `standalone-valuation`)
- Sample: `page.offer_report.json`

### `…/{investmentSlug}/raport-inwestycji`: raport inwestycji [P]
- Jak raport oferty, ale `property` opisuje średnią inwestycji.

### `/ceny-ofertowe/{city}/mapa` [P]
- Props: `initialInvestments[]` (jak `/api/map/investments`). Reszta przez JSON API.

---

## Ceny transakcyjne (RCN)

### `/ceny-transakcyjne/{city}/mieszkania` i `/domy`: lista transakcji [P]
| Parametr | Wartości | Status |
|---|---|---|
| `sortBy` | `creation_date` (domyślnie, desc), `amount` [P]; pozostałe [H] | |
| `filterPrice`, `filterPricePerM2`, `filterSize` | zakres `min-max` | `filterPrice` [P] |
| `filterRooms` | csv | [P] |
| `filterFloor` / `filterFloors` | csv | [W] |
| `filterDistrict`, `filterStreet` | nazwa | `filterDistrict` przyjęty [P], ale wyniki nie wyglądają na ściśle ograniczone do dzielnicy [H] |
| `filterPowiat` | csv `powiat_rcn_id` | [W] |
| `filterPolygon` | ? (rysowany obszar) | [H] |
| `filterFlipped` | `true` | [W] |
| `filterClassification` | brak = `transakcja`; `anomalie`, `wszystkie` | [W] |
| `filterLastTransactionDate` | kwartał (`AQ()` w chunku `2438`) | format [H] |

Props `initialData {data, pagination, stats}` + `initialApiParams` (echo filtrów po stronie serwera, przydatne do weryfikacji):
```json
{ "sale_rcn_id", "name": "<id lokalu z EGiB>", "amount", "amount_sqm", "floor", "floor_number", "rooms", "rooms_number",
  "type", "currency", "size", "size_building_area", "size_plot_area", "creation_date",
  "start_amount_difference(_percent)", "last_amount_difference(_percent)", "last_event_date", "total_events",
  "is_flipped", "last_transaction_classification",
  "invest": { "invest_rcn_id", "name", "city", "city_slug", "slug", "source_rcn": { "source_rcn_id", "name" } } }
stats: { averagePrice, averageSize, avgAmountPerM2, minPricePerSqm, maxPricePerSqm, pricePerSqmRange,
         totalTransactions, minPrice, maxPrice, minSize, maxSize }
```
`stats` dotyczy **całego zbioru po filtrach**, nie tylko strony [W]. Dzięki temu da się podać agregaty bez paginowania.
Sample: `page.transactions_list.json`, `page.transactions_list.params.json`

### `/ceny-transakcyjne/{city}/adresy`: lista budynków [P]
- `sortBy`: `name`, `transactions` (domyślnie), `avg_size`, `avg_price_sqm`, `avg_amount`
- Element: `{kind: "flat"|"house", invest_rcn_id, name, street, city, city_slug, avg_amount, avg_size, avg_price_sqm, transactions, slug, building_area, plot_area, source_rcn}`

### `/ceny-transakcyjne/{city}/adresy/{investRcnSlug}` i `/domy/{investRcnSlug}`: budynek/dom [P]
- Props: `investment {invest_id (= invest_rcn_id), latitude, longitude, name, slug, city, city_slug, street, avg_*, active_offers (= liczba lokali)}`, `sales[]` z `events[]` (pełne `sale_event_rcn` z `additionalData`)
- Domy mają dodatkowo `size_usable`, `size_building`, `size_plot` [P]
- To samo daje `GET /api/map/transactions/visible/{slug}`, które **preferujemy**.
- Sample: `page.address.json`, `page.house.json`

### `/ceny-transakcyjne/polska/miasta`: ranking miast [P]
- Props: `cities[]` (jak `/api/city-transaction-stats`), `teaserCharts[]` (miesięczne serie dla top miast)

---

## Statystyki

### `/statystyki/ceny-transakcyjne/{mieszkania|domy}/{city}` [P]
- Props: `rawTransactions[]` to **wszystkie transakcje miasta w skrócie** (Warszawa: 128 912 wierszy, HTML 12,9 MB): `{m: "YYYY-MM", s: metraż, a: kwota, ps: cena/m², c: klasyfikacja, rn: pokoje, fn: piętro}`. Zakres 2017-01 → bieżący miesiąc.
- `latestSummary` (ostatni pełny miesiąc), `slices` (r/r i k/k w przekrojach: metraż, pokoje, …), `topCities`
- Filtry w URL (`filterPrice`, `filterSize`, `filterRooms`, …) są obsługiwane po stronie klienta na `rawTransactions` [W].
- Za ciężkie do bezpośredniego użycia. Agregaty lepiej brać z `/api/monthly-transaction-stats`.

### `/statystyki/ceny-transakcyjne/{type}/{city}/mapa` [P]
- Props: `powiats[]`: `{powiat_rcn_id, powiat_name, transaction_count, med_price_sqm, med_size, med_amount, transaction_count_change, price_sqm_change, amount_change}` (okres: ostatni kwartał vs poprzedni? [H])

### `/statystyki/statystyki-rzadowe/{location}`: GUS + NBP [P]
- **Jedyny kanał** dla tych danych (brak JSON API).
- `location`: 69 lokalizacji: miasta oraz agregaty `polska`, `7-miast`, `10-miast`, `9-miast`, `6-miast-bez-warszawy` (prop `sortedLocations` z mapowaniem na `gus.teryt` i `nbp.dbName`)
- Sekcje (`tocItems`): `gus-mieszkania` (kwartalnie i miesięcznie: oddane/rozpoczęte wg form budownictwa), `gus-formy-budownictwa`, `gus-srednia-powierzchnia` (rocznie), `gus-demografia` (urodzenia, zgony, przyrost), `gus-wiek` (kohorty 5-letnie K/M), `gus-bezrobocie` (miesięczna stopa), `gus-wynagrodzenia`, `nbp` (kwartalnie: `pierwotnyOfertowa`, `pierwotnyTransakcyjna`, `wtornyOfertowa`, `wtornyTransakcyjna`)
- Kilka propsów nazywa się `data`; trzeba je rozróżniać po kształcie lub pozycji w drzewie [P]. To kruche miejsce.
- Sample: `page.stats_gov.json`

### `/statystyki/portale-ogloszeniowe/{type}/{region}` [P]
- Dane ładowane po stronie klienta z `/api/announcement-stats`. Strona zawiera tylko szkielet i listę regionów.

---

## Inne

### `/zglos-dewelopera/mapa-zgloszen` [P]
- Props: `developerAbuseData[]` (105): `{developer_abuse_id, name, slug, developer, website, latitude, longitude, violations[], additionalInfo}`, czyli zgłoszenia naruszeń ustawy o jawności cen.
- Sample: `page.developer_abuse_map.json`
