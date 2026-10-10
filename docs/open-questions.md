# Luki, hipotezy, rzeczy do sprawdzenia

Priorytet: **P1** blokuje vertical slice, **P2** potrzebne przed pełnym v1, **P3** nice-to-have.

## Do decyzji użytkownika

| # | Pytanie | Dlaczego ważne |
|---|---|---|
| U1 | (Do czasu rozstrzygnięcia obowiązuje tymczasowa reguła D9: żywe zapytania tylko za zgodą użytkownika.) **Polityka wobec `robots.txt: Disallow: /api/`.** Nasz klient woła te same endpointy co przeglądarka, ale robots wyklucza `/api/` dla automatów. Czy kontaktujemy się z autorami (aktywni na GitHub `deweloperuch`, X, TikTok), żeby uzyskać zgodę lub oficjalny dostęp? | Ryzyko blokady i etyka; wpływa na sposób identyfikacji klienta (UA) |
| U2 | ~~Stos technologiczny~~: **rozstrzygnięte 2026-10-09: Python** (decisions.md D8) | Fundament repo |
| U3 | ~~Tryb pracy MCP~~: **rozstrzygnięte 2026-10-10: tylko stdio** (decisions.md D11) | Wpływa na cache i rate limiting (współdzielony vs per-użytkownik) |

## Techniczne

| # | P | Co | Typ | Jak sprawdzić |
|---|---|---|---|---|
| T1 | P1 | Rozwiązanie `sale_id` → inwestycja. `sale-events` nie zwraca inwestycji | luka | Sprawdzić inne kanały (np. `fetchBatchPriceChartData`). Alternatywa: wymagać `investment_slug` w `get_offer`, bo zawsze mamy go z wyników wyszukiwania |
| T4 | P2 | `filterDistrict` w transakcjach nie zawęża wyników ściśle (wyniki spoza Mokotowa?) | [H] | Porównać `stats.totalTransactions` z/bez filtra, sprawdzić adresy |
| T5 | P2 | Format `filterLastTransactionDate` (kwartały, „Przed 2017”) | [H] | Ruch sieciowy w przeglądarce po ustawieniu filtra |
| T7 | P2 | Kolizje slugów raportu oferty (`D1.1.1.4` vs `D1.11.4`) i jak serwer je rozstrzyga | [W] | Znaleźć inwestycję z kolidującymi nazwami |
| T8 | P2 | **Geokodowanie adres → lat/lng** dla wyceny. UI /wycena: skąd bierze współrzędne? Brak zewnętrznego geokodera w bundlach | luka | Ruch sieciowy na /wycena po wpisaniu adresu. Fallback: lat/lng ulicy z `location-search` |
| T9 | P2 | Granice kubełków histogramów (`aligned: true`) | [W] | Odczytać moduł `84462` w chunku `2438` |
| T10 | P2 | Okres i baza `*_change` w `city-transaction-stats` / mapie powiatów; czy `avg_*` to mediana | [H] | Porównać z `monthly-transaction-stats` |
| T11 | P2 | Rate limiting: przy jakim tempie CF/aplikacja odpowiada 429/blokadą? Czy uczciwy User-Agent (`deweloperuch-mcp/x.y`) przechodzi? | [H] | Ostrożny test pojedynczych requestów z innym UA; **bez testów obciążeniowych** |
| T13 | P3 | `announcement-stats`: znaczenie `blue/green`, `value`; poprawny `region` dla całej Polski | 🔴 | Treść strony /statystyki/portale-ogloszeniowe (legenda, opisy) w przeglądarce |
| T14 | P3 | Semantyka pól `filteredStats`, `citiesStats` (profil dewelopera), `slices` (statystyki) | [H] | Porównanie z UI |
| T15 | P3 | Nieprzeanalizowane: `/kredyty`, kalkulatory (prawdopodobnie bez danych backendu) | — | — |
| T16 | P3 | Weryfikacja ruchu w prawdziwej przeglądarce (DevTools/HAR) jako kontrola kompletności analizy statycznej, zwłaszcza interakcje mapy i filtrów | — | Sesja w Chrome z nagraniem ruchu sieciowego |
| T17 | P3 | Czy `Next-Router-State-Tree` jest wymagany dla server actions | [H] | Tylko jeśli kiedyś użyjemy C |
| T29 | P3 | Pełna lista dozwolonych `perPage` (zaobserwowano: 10, 25, 50, 100 przyjęte; 20, 500 → 10) | [H] | Kilka wartości, np. 30, 75; po T2 |
| T30 | P3 | Rzeczywisty klucz `sortBy=last_event_date` (nie zgadza się z widocznym `last_event_date`; może `last_change_event_date`) oraz niesprawdzone `investment`, `last_amount_difference(_percent)`, `start_amount_difference` | [H] | Po jednym zapytaniu na wartość, porównanie z polami listy |
| T31 | P3 | `success: false` w `/api/sale-events`: kiedy występuje (nieznany ID daje `success: true, saleData: null`; złe/puste `saleId`?) | [H] | 1–2 zapytania z błędnym `saleId` |
| T32 | P3 | `count` w `location-search` dla `street` i `city` (czy = liczba aktywnych ofert; w trybie transakcji = transakcje) | [H] | Porównać z `total` listy `filterStreet=` / `/api/cities offerCount` |
| T33 | P3 | Niesprawdzone wartości filtrów listy ofert: `filterPriceChange=increase,no_change` i csv, `filterStatus=active`, sentinel `filterPricePerM2=…-999999`, `filterDeveloper`, `filterProject`, `filterStreet`, `filterAnomalies`, `showArchivedInvestments` | [W] | Zapytania kontrolne z porównaniem `total` |

## Rozstrzygnięte

| # | Data | Wynik | Próbka |
|---|---|---|---|
| T2 | 2026-10-10 | Obalona: `perPage=25` przyjęte (`pagination.perPage: 25`, 25 wierszy). Dozwolony zbiór nie jest {10, 50, 100}; pełna lista otwarta jako T29 | (bez osobnej próbki; wynik w `pages-rsc.md`) |
| T3 | 2026-10-10 | Domyślnie (brak `sortBy`) i przy nieznanej wartości: rosnąco po `sale_id`, bez błędu. Potwierdzone: `amount` (asc, desc), `price_per_sqm`, `size`, `name`, `start_amount_difference_percent`. `last_event_date` przyjęte, klucz niejasny (T30). Reszta [W] (T30) | `page.offers_list.sort_desc` |
| T6 | 2026-10-10 | `filterPriceChange=decrease` działa (13324 → 2416, wg zmiany od ceny początkowej); `filterStatus=archived` działa (11415, same archiwalne); `includeArchived=true` działa (24739 = 13324 + 11415); `filterRooms` i `filterFloors` **nie działają** na liście ofert (total bez zmian). Pozostałe wartości: T33 | (bez osobnej próbki; wynik w `pages-rsc.md`) |
| T12 | 2026-10-10 | `city-sales` nie zawiera archiwalnych (`includeArchived` ignorowane, Sopot 6/6 `active`); `polska` → `400 Invalid citySlug` (nie działa) | (obserwacja bez próbki; `api.city_sales_sopot`) |
| T18 (a) | 2026-10-10 | Nieznany slug w `map/investments/visible/{slug}`: `404 {"error":"Investment not found"}` | (nie-2xx, bez próbki) |
| T19 (b) | 2026-10-10 | Nieznane miasto na stronie `/ceny-ofertowe/{city}/mieszkania`: HTTP 200 RSC bez `initialData`, z segmentem `notFound`; klient musi wykrywać brak propsa | (bez próbki) |
| T20 (c) | 2026-10-10 | Alfabet slugów: 166 z 168 slugów w próbkach to `[a-z0-9-]`; 2 wyjątki (`Metro-Art`, `Forrest`) tylko w mapie zgłoszeń, innym typie encji. Poziom [W] (obserwacja, nie test serwera) | `page.developer_abuse_map` |
| T21 (d) | 2026-10-10 | `count` dzielnicy = liczba aktywnych ofert (Mokotów: 1562 = `total` z `filterDistrict`). Dla ulic i miast: T32 | `api.location_search.kinds_limit20` |
| T22 (e) | 2026-10-10 | `limit` honorowany do co najmniej 20 (`q=mo&limit=20` → 20 wyników); `kind` ∈ {`city`, `district`, `street`}; brak flagi „więcej”; `q` z 1 znakiem → pusta lista | `api.location_search.kinds_limit20` |
| T23 (f) | 2026-10-10 | `sortBy=amount&sortOrder=desc` działa (malejąco od 7 820 948) | `page.offers_list.sort_desc` |
| T24 (g) | 2026-10-10 | Częściowo: nieznany `saleId` → `200 {success: true, saleData: null, events: []}`; `success: false` nie zaobserwowano (T31) | (bez próbki) |
| T25 (h) | 2026-10-10 | Wartownicy: `filterPrice=0-99999999&filterSize=0-9999` → total 13324 = wynik bez filtrów. Cena/m² (`999999`) nietestowana (T33) | (bez osobnej próbki) |
| T26 (i) | 2026-10-10 | Strony RSC: `private, max-age=28800, must-revalidate` (bez `s-maxage`). `city-sales`: `public, max-age=28800, s-maxage=300, stale-while-revalidate=3600`. `cities`, `sale-events`, `map/investments/visible` (także 404): `max-age=28800` bez `s-maxage`. `location-search`: `private, max-age=28800`. Wymagają `DEFAULT_TTL` w transporcie | — |
| T27 (j) | 2026-10-10 | `/api/cities`: `page` działa; `total` = wszystkie pasujące, `page` = numer strony, `hasMore` = są kolejne (`limit=2`: strona 1 → `hasMore: true`, strona 2 → `false`, `total: 4`) | `api.cities_q` (bez `hasMore: true`) |
| T28 (`OFFER_EVENT`) | 2026-10-10 | Każdy wpis ceny ofertowej, nie tylko pierwsza cena (oferta 4397: 12 zdarzeń `OFFER_EVENT` o zmiennych kwotach = `total_events`) | `api.sale_events.price_history` |

## Źródła alternatywne / uzupełniające

| Źródło | Co daje | Ograniczenia |
|---|---|---|
| `github.com/deweloperuch/rejestr-cen-nieruchomosci` | Surowe dane RCN (GML), **licencja CC0**, 12 miast (Gdańsk, Gdynia, Katowice, Kraków, Łódź, Łomża, Lublin, Olsztyn, Sopot, Toruń, Warszawa, Wrocław) | Ostatni push 2025-11-08, więc snapshot jest starszy niż serwis (dane do 2026-08); format GML wymaga parsera. Kandydat na drugie źródło danych w architekturze |
| GUGiK / Geoportal (RCN) | `transactionId: "PL.PZGIK.…"` z datami pobrania 2026 sugeruje, że serwis zasila się z krajowej usługi RCN | [H], nie badane; potencjalne źródło pierwotne |
