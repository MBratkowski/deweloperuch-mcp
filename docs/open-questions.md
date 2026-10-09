# Luki, hipotezy, rzeczy do sprawdzenia

Priorytet: **P1** blokuje vertical slice, **P2** potrzebne przed pełnym v1, **P3** nice-to-have.

## Do decyzji użytkownika

| # | Pytanie | Dlaczego ważne |
|---|---|---|
| U1 | (Do czasu rozstrzygnięcia obowiązuje tymczasowa reguła D9: żywe zapytania tylko za zgodą użytkownika.) **Polityka wobec `robots.txt: Disallow: /api/`.** Nasz klient woła te same endpointy co przeglądarka, ale robots wyklucza `/api/` dla automatów. Czy kontaktujemy się z autorami (aktywni na GitHub `deweloperuch`, X, TikTok), żeby uzyskać zgodę lub oficjalny dostęp? | Ryzyko blokady i etyka; wpływa na sposób identyfikacji klienta (UA) |
| U2 | ~~Stos technologiczny~~: **rozstrzygnięte 2026-10-09: Python** (decisions.md D8) | Fundament repo |
| U3 | **Tryb pracy MCP**: tylko lokalny stdio (Claude Desktop/Code) czy też zdalny (HTTP)? | Wpływa na cache i rate limiting (współdzielony vs per-użytkownik) |

## Techniczne

| # | P | Co | Typ | Jak sprawdzić |
|---|---|---|---|---|
| T1 | P1 | Rozwiązanie `sale_id` → inwestycja. `sale-events` nie zwraca inwestycji | luka | Sprawdzić inne kanały (np. `fetchBatchPriceChartData`). Alternatywa: wymagać `investment_slug` w `get_offer`, bo zawsze mamy go z wyników wyszukiwania |
| T2 | P1 | Dozwolone `perPage` poza {10, 50, 100} (np. 25?) | [H] | 1–2 requesty |
| T3 | P1 | Domyślne `sortBy` listy ofert i pełna lista dozwolonych wartości (co z nieznaną wartością?) | [H] | Requesty z każdą wartością, porównanie kolejności |
| T4 | P2 | `filterDistrict` w transakcjach nie zawęża wyników ściśle (wyniki spoza Mokotowa?) | [H] | Porównać `stats.totalTransactions` z/bez filtra, sprawdzić adresy |
| T5 | P2 | Format `filterLastTransactionDate` (kwartały, „Przed 2017”) | [H] | Ruch sieciowy w przeglądarce po ustawieniu filtra |
| T6 | P2 | `filterRooms`, `filterFloors`, `filterPriceChange`, `filterStatus`, `includeArchived` na liście ofert | [W] | Requesty kontrolne |
| T7 | P2 | Kolizje slugów raportu oferty (`D1.1.1.4` vs `D1.11.4`) i jak serwer je rozstrzyga | [W] | Znaleźć inwestycję z kolidującymi nazwami |
| T8 | P2 | **Geokodowanie adres → lat/lng** dla wyceny. UI /wycena: skąd bierze współrzędne? Brak zewnętrznego geokodera w bundlach | luka | Ruch sieciowy na /wycena po wpisaniu adresu. Fallback: lat/lng ulicy z `location-search` |
| T9 | P2 | Granice kubełków histogramów (`aligned: true`) | [W] | Odczytać moduł `84462` w chunku `2438` |
| T10 | P2 | Okres i baza `*_change` w `city-transaction-stats` / mapie powiatów; czy `avg_*` to mediana | [H] | Porównać z `monthly-transaction-stats` |
| T11 | P2 | Rate limiting: przy jakim tempie CF/aplikacja odpowiada 429/blokadą? Czy uczciwy User-Agent (`deweloperuch-mcp/x.y`) przechodzi? | [H] | Ostrożny test pojedynczych requestów z innym UA; **bez testów obciążeniowych** |
| T12 | P2 | Czy `offers/city-sales` zawiera kiedykolwiek oferty archiwalne; czy `polska` działa | [H] | 1 request |
| T13 | P3 | `announcement-stats`: znaczenie `blue/green`, `value`; poprawny `region` dla całej Polski | 🔴 | Treść strony /statystyki/portale-ogloszeniowe (legenda, opisy) w przeglądarce |
| T14 | P3 | Semantyka pól `filteredStats`, `citiesStats` (profil dewelopera), `slices` (statystyki) | [H] | Porównanie z UI |
| T15 | P3 | Nieprzeanalizowane: `/kredyty`, kalkulatory (prawdopodobnie bez danych backendu) | — | — |
| T16 | P3 | Weryfikacja ruchu w prawdziwej przeglądarce (DevTools/HAR) jako kontrola kompletności analizy statycznej, zwłaszcza interakcje mapy i filtrów | — | Sesja w Chrome z nagraniem ruchu sieciowego |
| T17 | P3 | Czy `Next-Router-State-Tree` jest wymagany dla server actions | [H] | Tylko jeśli kiedyś użyjemy C |

## Źródła alternatywne / uzupełniające

| Źródło | Co daje | Ograniczenia |
|---|---|---|
| `github.com/deweloperuch/rejestr-cen-nieruchomosci` | Surowe dane RCN (GML), **licencja CC0**, 12 miast (Gdańsk, Gdynia, Katowice, Kraków, Łódź, Łomża, Lublin, Olsztyn, Sopot, Toruń, Warszawa, Wrocław) | Ostatni push 2025-11-08, więc snapshot jest starszy niż serwis (dane do 2026-08); format GML wymaga parsera. Kandydat na drugie źródło danych w architekturze |
| GUGiK / Geoportal (RCN) | `transactionId: "PL.PZGIK.…"` z datami pobrania 2026 sugeruje, że serwis zasila się z krajowej usługi RCN | [H], nie badane; potencjalne źródło pierwotne |
