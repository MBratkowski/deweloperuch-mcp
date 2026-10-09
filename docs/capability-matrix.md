# Capability matrix (v1, 2026-10-09)

Capabilities wynikają z danych faktycznie dostępnych w serwisie ([discovery/](discovery/README.md)). Każda capability to operacja domenowa. Może składać się z kilku requestów.

Kanały: **A** = JSON `/api/*`, **B** = strona RSC, **C** = server action.
Status:
- ✅ gotowe do implementacji: requesty wykonane, kształt odpowiedzi znany
- 🟡 wykonalne z zastrzeżeniami: część parametrów lub semantyki niezweryfikowana
- 🔴 niejasne: semantyka danych nieznana
- ⏸ odłożone: niski priorytet albo poza zakresem

## Lokalizacje

| Capability | Dane | Request(y) | Input | Output | Ograniczenia | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Wyszukaj lokalizację | miasta, dzielnice, ulice z lat/lng i liczbą ofert/transakcji | A `cities?q`, `location-search?q`, opcjonalnie `city-lookup` | `query`, `market: offers\|transactions` | `[{kind: city\|district\|street, name, city_slug, lat?, lng?, count}]` | `cities` zwraca też miejscowości z 0 ofert | `locations search <q>` | `search_locations` | ✅ |
| Dzielnice miasta | dzielnice + liczność | A `city-districts?citySlug` | `city`, `market` | `[{name, count}]` | tylko nazwy, brak ID i geometrii | `locations districts <city>` | (w `search_locations` lub osobno) | ✅ |
| Miasto → powiat RCN | id powiatów | A `map/city-powiats/{city}` | `city` | `{powiat_ids, primary}` | — | (wewnętrzne) | (wewnętrzne) | ✅ |

## Oferty deweloperów (rynek pierwotny)

| Capability | Dane | Request(y) | Input | Output | Ograniczenia | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Wyszukaj oferty (mieszkania) | lista ofert z ceną, metrażem, zmianami ceny, inwestycją, deweloperem | B `/ceny-ofertowe/{city}/mieszkania?filter…` | `city`, `price`, `price_per_m2`, `area` (min/max), `developer?`, `investment?`, `district?`, `rooms?`, `price_change?`, `include_archived?`, `sort`, `page`, `per_page` | `{total, page, total_pages, items:[OfferSummary]}` | **max 20 stron × 100 = 2000**; `rooms`, `district`, `price_change` niezweryfikowane | `offers search …` | `search_offers` | 🟡 (rdzeń ✅) |
| Pobierz ofertę + historię ceny | dane oferty, zdarzenia cenowe | A `sale-events?saleId`, A `map/investments/visible/{slug}` (kontekst) | `offer_id`, `investment_slug` | `Offer {…, investment, developer, price_history[]}` | `sale-events` nie zwraca inwestycji; bez sluga brak kontekstu (patrz luki) | `offers get <id> --investment <slug>` | `get_offer` | ✅ |
| Wyszukaj inwestycje | inwestycje z agregatami | B `/ceny-ofertowe/{city}/inwestycje`; A `investments?q` (po nazwie); A `map/investments?…` (wszystkie w mieście, z lat/lng) | `city`, `name?`, `developer?`, filtry cen, `sort`, `page` | `{total, items:[InvestmentSummary]}` | B: limit 20 stron; A `map/investments` bez limitu, ale bez paginacji | `investments search …` | `search_investments` | ✅ |
| Pobierz inwestycję | inwestycja, deweloper, wszystkie oferty (aktywne+archiwalne), opcjonalnie historia | A `map/investments/visible/{slug}`, opcjonalnie A `investments/{id}/sale-events` | `investment_slug`, `include_history?` | `Investment {…, offers[]}` | `sale-events` wolne przy MISS (~3 s) | `investments get <slug>` | `get_investment` | ✅ |
| Wyszukaj deweloperów | deweloperzy z agregatami | B `/ceny-ofertowe/{city}/deweloperzy`; A `developers?q` | `city?` (`polska`), `name?`, `sort`, `page` | `{total, items:[DeveloperSummary]}` | — | `developers search …` | `search_developers` | ✅ |
| Pobierz dewelopera | profil, inwestycje, statystyki, oś zmian cen | B `/ceny-ofertowe/{city}/deweloperzy/{slug}` | `developer_slug`, `city?` | `Developer {…, investments[], stats}` | tylko RSC; `filteredStats`/`citiesStats` wymagają opisu pól | `developers get <slug>` | `get_developer` | 🟡 |
| Statystyki ofert | liczba ofert, histogram cen/ceny m²/metrażu | A `offer-count`, `price-distribution`, `size-distribution` | `city`, filtry jak w wyszukiwaniu, `developer?`, `investment?` | `{count, price_histogram, price_m2_histogram, area_histogram}` | granice kubełków trzeba odtworzyć (`aligned`) | `stats offers …` | `get_offer_statistics` | 🟡 |
| Raport oferty (porównanie z rynkiem) | wycena RCN dla oferty, konkurencyjne oferty w okolicy | B `…/{inv}/raport-mieszkania-{slug}`; B `…/{inv}/raport-inwestycji` | `investment_slug`, `offer_name` | `{offer, valuation, competitors[]}` | ryzyko kolizji slugów nazw ofert | `offers report …` | `compare_offer_to_market` | 🟡 |

## Transakcje (RCN)

| Capability | Dane | Request(y) | Input | Output | Ograniczenia | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Wyszukaj transakcje | transakcje lokali/domów + **agregaty całego zbioru** | B `/ceny-transakcyjne/{city}/mieszkania\|domy?filter…` | `city`, `property: flat\|house`, `price`, `price_per_m2`, `area`, `rooms?`, `floor?`, `district?`, `street?`, `classification?`, `sort`, `page`, `per_page` | `{total, stats, items:[TransactionSummary]}` | limit 2000; `district` budzi wątpliwości; format `filterLastTransactionDate` nieznany | `transactions search …` | `search_transactions` | 🟡 (rdzeń ✅) |
| Wyszukaj budynki/adresy | budynki z liczbą i średnimi transakcji | B `/ceny-transakcyjne/{city}/adresy`; A `investment-streets?variant=transactions` | `city`, `street?`, `sort`, `page` | `{total, items:[BuildingSummary]}` | — | `buildings search …` | `search_buildings` | 🟡 |
| Pobierz budynek z transakcjami | wszystkie lokale i transakcje w budynku, szczegóły RCN | A `map/transactions/visible/{slug}`, A `avg-price-trend/building/{id}` (trend okolicy 1 km) | `building_slug`, `property?` | `Building {…, units[{transactions[]}], neighborhood_trend?}` | duże odpowiedzi (189 KB / 86 lokali) — trzeba przycinać | `buildings get <slug>` | `get_building` | ✅ |
| Statystyki transakcji w czasie | miesięczne mediany/średnie, liczby | A `monthly-transaction-stats` (miasto/powiat/ulica), A `avg-price-trend/city/{city}` (kwartalnie), A `statystyki/powiat-price-trend` | `scope: city\|powiat\|street`, `id`, `property`, `granularity: month\|quarter` | `[{period, count, median_price_m2, avg_price_m2, median_area, median_amount, …}]` | ostatnie miesiące niekompletne (opóźnienie RCN) | `stats transactions …` | `get_transaction_statistics` | ✅ |
| Liczba/histogram transakcji | liczba, rozkład cen i metraży | A `transaction-count`, `transaction-*-distribution` | `city`, filtry, `powiat_ids?`, `building_id?` | jak dla ofert | wolne przy MISS (2–5 s) | (w `stats transactions`) | (w `get_transaction_statistics`) | 🟡 |
| Ranking miast / powiatów | liczba transakcji, ceny, zmiany | A `city-transaction-stats`, A `map/powiat-stats` | `property?`, `sort`, `limit` | `[{city, count, price_m2, change_pct…}]` | okres i baza zmian nieznane; `avg_` może oznaczać medianę | `stats cities` | `rank_locations` | 🟡 |

## Wycena

| Capability | Dane | Request(y) | Input | Output | Ograniczenia | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Wyceń nieruchomość | szacowana wartość, cena/m², transakcje porównawcze, promień, trend | A `standalone-valuation?area&lat&lng&address` | `lat`, `lng`, `area_m2`, `address?` | `{estimated_value, price_per_m2, radius_m, period_months, comparables[top N], stats}` | wymaga współrzędnych: brak potwierdzonego geokodowania adres→lat/lng (patrz luki); 180 KB → przycinamy | `valuation estimate …` | `estimate_property_value` | ✅ |

## Statystyki zewnętrzne

| Capability | Dane | Request(y) | Input | Output | Ograniczenia | CLI | MCP tool | Status |
|---|---|---|---|---|---|---|---|---|
| Statystyki GUS/NBP | budownictwo (oddane/rozpoczęte), średnia powierzchnia, demografia, bezrobocie, wynagrodzenia, ceny NBP | B `/statystyki/statystyki-rzadowe/{loc}` | `location` (69 opcji), `dataset` | serie czasowe per dataset | tylko RSC; kilka propsów `data` do rozróżnienia po kształcie | `stats government <loc> <dataset>` | `get_government_statistics` | 🟡 |
| Statystyki portali ogłoszeniowych | dzienne serie sprzedaż/wynajem × 2 źródła | A `announcement-stats` | `region`, `property` | serie | znaczenie `blue/green` i `value` nieznane; `polska` pusta | — | — | 🔴 |

## Odłożone (⏸)

| Capability | Źródło | Powód |
|---|---|---|
| Zgłoszenia naruszeń jawności cen | B `/zglos-dewelopera/mapa-zgloszen` | niszowe; łatwe do dodania później |
| Obrys budynku, warstwy powódź/Airbnb, granice powiatów | A `building-outline`, CDN pmtiles, `/geo/powiaty.geojson` | dane geometryczne mają małą wartość dla LLM |
| Zrzuty hurtowe (`powiat-sales`, `rawTransactions`) | A / B | za duże dla MCP; ewentualnie jako źródło lokalnego indeksu |
| PDF wyceny | A `valuation-pdf` | rate limit, binarne |
| Kalkulatory kredytowe | logika klienta | to nie dane serwisu |
| Zapisy (zgłoszenia, raporty błędów) | C + Turnstile | poza zakresem, tylko odczyt |

## Proponowany zestaw narzędzi MCP (v1)

`search_locations`, `search_offers`, `get_offer`, `search_investments`, `get_investment`, `search_developers`, `get_developer`, `get_offer_statistics`, `search_transactions`, `get_building`, `get_transaction_statistics`, `estimate_property_value`, później `get_government_statistics`, `compare_offer_to_market`, `rank_locations`.

Zasady (do potwierdzenia w implementacji):
- Wyniki list zawsze zwracają `total` i informację o obcięciu (`truncated: true`, gdy `total > 2000`), żeby model wiedział, że ma zawęzić filtry.
- Identyfikatory w outputach to te, które przyjmują narzędzia „get”: `investment_slug`, `offer_id`, `building_slug`, `developer_slug`, `city_slug`.
- Duże tablice (transakcje porównawcze, oferty inwestycji) są przycinane z parametrem `limit` i polem `omitted`.
