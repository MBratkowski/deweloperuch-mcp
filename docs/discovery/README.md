# deweloperuch.pl — mapa warstwy danych

Stan na **2026-10-09** (uzupełnienia z weryfikacji B: 2026-10-10), build Next.js `KD_IOP6Grqba7xa86pGVG`.
Metoda: statyczna analiza wszystkich chunków JS klienta (114 plików, w tym leniwie ładowane z runtime webpacka), dekodowanie payloadów RSC stron, pojedyncze requesty do każdego endpointu (odstęp ≥1 s, zgodnie z `Crawl-delay: 1`). Bez logowania, bez obchodzenia czegokolwiek.

Oznaczenia używane w całej dokumentacji:

- **[P] potwierdzone** — zaobserwowane w requeście/odpowiedzi albo w kodzie klienta.
- **[W] wniosek** — wynika z obserwacji, ale nie było bezpośredniego testu.
- **[H] hipoteza** — do sprawdzenia.

Powiązane dokumenty:

- [endpoints.md](endpoints.md) — katalog endpointów JSON `/api/*` i server actions
- [pages-rsc.md](pages-rsc.md) — strony SSR jako źródło danych (filtry, sortowanie, paginacja, propsy)
- [entities.md](entities.md) — encje, identyfikatory, relacje, słowniki wartości
- [samples/](samples/) — przycięte próbki odpowiedzi (`api.*.json`, `page.*.json`)
- [../capability-matrix.md](../capability-matrix.md) — capability matrix dla CLI/MCP
- [../open-questions.md](../open-questions.md) — luki i hipotezy
- [../decisions.md](../decisions.md) — decyzje architektoniczne

## 1. Architektura serwisu

| Element | Obserwacja | Status |
|---|---|---|
| Framework | Next.js App Router (React Server Components), `x-powered-by: Next.js` | [P] |
| CDN | Cloudflare przed całym serwisem, edge cache dla HTML i `/api/*` | [P] |
| Stan klienta | React Query (`queryKey`, `staleTime`), zwykły `fetch` same-origin | [P] |
| Sesja / auth | Brak cookies (`set-cookie` nie występuje w żadnej odpowiedzi), brak tokenów, brak nagłówków auth | [P] |
| Ochrona botów | Zwykłe requesty z przeglądarkowym UA przechodzą. Cloudflare Turnstile tylko w formularzach (zgłoszenia) | [P] |
| `robots.txt` | `Disallow: /api/`, `/internal/`, `/cron/`; `Crawl-delay: 1` | [P] |
| Backend za Next.js | Strony SSR dostają `initialApiParams` (`filterPrice`, `filterCitySlug`…), co sugeruje wewnętrzne API wołane serwerowo. Host nie wycieka do klienta | [H] |

Z `robots.txt` wynika, że `/api/` nie jest przeznaczone dla crawlerów. Nasz klient będzie wykonywał te same requesty co przeglądarka użytkownika, ale musi to robić oszczędnie (cache, limit współbieżności, brak masowego crawlowania). Szczegóły w [decisions.md](../decisions.md).

## 2. Kanały dostępu do danych

W serwisie są cztery kanały, z różną stabilnością i kosztem:

```
            ┌──────────────────────────────────────────────────────────────┐
            │                       deweloperuch.pl                        │
            ├───────────────┬──────────────────┬──────────────┬────────────┤
            │ A. JSON API   │ B. RSC payload   │ C. Server    │ D. Static  │
            │  GET /api/*   │  GET <strona>    │   Actions    │  / CDN     │
            │  34 ścieżki   │  RSC: 1          │  POST +      │  geojson,  │
            │               │  text/x-component│  Next-Action │  pmtiles   │
            ├───────────────┼──────────────────┼──────────────┼────────────┤
            │ autocomplete, │ listy z filtrami │ wycena (ma   │ granice    │
            │ statystyki,   │ i paginacją,     │ też GET),    │ powiatów,  │
            │ mapy, historia│ szczegóły dewel./│ wykresy cen, │ warstwy    │
            │ cen, wycena   │ inwestycji/oferty│ konkurencja  │ map        │
            │               │ /adresu, GUS/NBP │              │            │
            └───────────────┴──────────────────┴──────────────┴────────────┘
              stabilny         średnio stabilny   niestabilny    stabilny
              JSON             (zależy od         (ID zmienia    (pliki)
                               nazw propsów)      się z deployem)
```

### A. JSON API `/api/*` [P]

- Same-origin, `GET`, `application/json`, bez sesji.
- Cache CF: `s-maxage` od 300 s (oferty, liczniki) do 86400 s (statystyki RCN); `max-age=28800` dla przeglądarki. Część endpointów (`cities`, `location-search`, `sale-events`, `map/investments/visible`) i strony RSC nie mają `s-maxage`, tylko `max-age=28800` (strony: `private`) [P 2026-10-10].
- Parametry zawsze w query stringu lub ścieżce. Nie spotkałem body ani nagłówków wymaganych do działania.
- Błędy: `400 {"error": "..."}` przy złym parametrze (np. `avg-price-trend/building/<slug>` zamiast id). `valuation-pdf` jawnie obsługuje `429` + `Retry-After`.
- Pełny katalog: [endpoints.md](endpoints.md).

### B. Payload RSC stron (Server Components) [P]

Listy (mieszkania, inwestycje, deweloperzy, transakcje, adresy) i strony szczegółów nie mają własnego JSON API. Dane są renderowane na serwerze i przekazywane jako propsy komponentów klienckich (`initialData`, `investments`, `sales`, `data`…). UI zmienia filtry, sortowanie i stronę przez `router.push(?…)`, czyli nowy request RSC, a nie `fetch` do API.

- Request: `GET <ścieżka strony>?<filtry>&_rsc=<dowolny>` z nagłówkiem `RSC: 1` → `content-type: text/x-component`, ~10× mniej danych niż HTML.
- Parametr `_rsc` jest potrzebny, bo Cloudflare ignoruje `Vary: RSC`: bez niego dostajemy zcache'owany HTML [P].
- Format: linie `<id>:<json>`; propsy są w elementach `["$","$L<id>",null,{...props}]`. Parser referencyjny: [`src/deweloperuch_mcp/flight.py`](../../src/deweloperuch_mcp/flight.py) (`recon/flight.py` go reeksportuje).
- Paginacja ma twardy limit **20 stron** (`page=21` → zwraca stronę 20) [P]. `perPage` ∈ {10, 25, 50, 100} przyjęte (20 i 500 → 10) [P].
- Szczegóły per strona: [pages-rsc.md](pages-rsc.md).

### C. Next.js Server Actions [P]

`POST <strona>` z nagłówkami `Next-Action: <id>`, `Accept: text/x-component`, body = JSON tablicy argumentów. Odpowiedź to RSC (`0:{…}` / `1:<wynik>`). ID akcji to hash, który **zmienia się przy każdym deployu** [W]. Można go odczytać z chunków JS (nazwa eksportu jest jawna: `createServerReference("<id>",…,"fetchStandaloneValuation")`), patrz [`recon/scan_bundles.py`](../../recon/scan_bundles.py).

| Akcja | Typ | Uwagi |
|---|---|---|
| `fetchStandaloneValuation` | odczyt | Wynik identyczny z `GET /api/standalone-valuation` [P], więc używamy GET |
| `reverseGeocodeAddress` | odczyt | lat/lng → adres |
| `fetchBatchPriceChartData` | odczyt | wykresy cen dla listy `sale_id`; prawdopodobnie dubluje `/api/sale-events` [H] |
| `fetchCompetitorInvestment`, `searchCompetitorInvestments` | odczyt | raport mieszkania, porównanie z konkurencją |
| `fetchDevelopers`, `fetchInvestments`, `fetchDeveloperAbuse` | odczyt | formularz „zgłoś dewelopera” |
| `createSaleRcnReport`, `createInvestmentAction` | **zapis** + Turnstile | poza zakresem, nie wywoływać |

### D. Zasoby statyczne / CDN [P w kodzie, nie pobierane]

- `/geo/powiaty.geojson`: granice powiatów, `properties.id` = `powiat_rcn_id` [W].
- `https://cdn.deweloperuch.pl/warstwa/powodz/…`: warstwa ryzyka powodziowego (kafle).
- `https://cdn.deweloperuch.pl/warstwa/airbnb/airbnb-points.pmtiles`: punkty Airbnb (PMTiles).
- Podkład mapy: `tiles.openfreemap.org/styles/liberty`.

## 3. Domeny danych (skrót)

| Domena | Źródło pierwotne | Główne kanały |
|---|---|---|
| **Oferty deweloperów** (ceny ofertowe, historia zmian) | strony deweloperów / ogłoszenia (`source: ANNOUCMENT`, `ANNOUCMENT_PR`, `scraper_pr`) | B (listy, szczegóły), A (`map/*`, `offers/city-sales`, `sale-events`, liczniki, rozkłady) |
| **Transakcje RCN** (ceny transakcyjne) | Rejestr Cen Nieruchomości / GUGiK (`transactionId: "PL.PZGIK.…"`) | B (listy, adresy), A (`map/powiat-*`, `map/transactions/visible`, statystyki) |
| **Statystyki rynku** | agregaty z RCN i ofert | A (`monthly-transaction-stats`, `powiat-price-trend`, `avg-price-trend`, `city-transaction-stats`, rozkłady), B (`/statystyki/...`) |
| **Statystyki rządowe** | GUS (mieszkania oddane/rozpoczęte, demografia, bezrobocie, wynagrodzenia), NBP (ceny ofertowe/transakcyjne rynek pierwotny/wtórny) | tylko B (`/statystyki/statystyki-rzadowe/{loc}`) |
| **Portale ogłoszeniowe** | dzienne serie „blue/green × sell/rent” | A (`announcement-stats`) |
| **Wycena** | porównawcza na bazie RCN w promieniu | A (`standalone-valuation`), B (raport mieszkania/inwestycji) |
| **Lokalizacje** | słowniki miast/dzielnic/ulic, powiaty | A (`cities`, `location-search`, `city-districts`, `investment-streets`, `city-lookup`, `map/city-powiats`) |
| **Zgłoszenia naruszeń** (jawność cen) | crowdsourcing | B (`/zglos-dewelopera/mapa-zgloszen`) |
| Kalkulatory / kredyty | obliczenia po stronie klienta | poza zakresem |

Model encji i ID: [entities.md](entities.md).

## 4. Najważniejsze ustalenia dla projektu

1. **Nie ma jednego API do wszystkiego.** Wyszukiwanie z filtrami i paginacją istnieje wyłącznie jako strony RSC. JSON API obsługuje autocomplete, mapy, statystyki i historię.
2. **Wyszukiwanie przez RSC ma sufit 20 × perPage(100) = 2000 wyników** na zapytanie [P]. Większe zbiory trzeba zawęzić filtrami albo pobrać „hurtem” przez JSON API (np. `offers/city-sales/{city}`: 1,3 MB dla Warszawy, 13 351 ofert; CF cache 5 min).
3. **Dane transakcyjne per powiat są ogromne.** `map/powiat-sales/{id}` dla Sopotu ma 1,6 MB i 6 636 transakcji; dla Warszawy szacunkowo ~80 MB [W]. Nie nadaje się do przekazywania modelowi. Lepiej używać list RCN z filtrami.
4. **Wycena ma stabilny GET** (`/api/standalone-valuation`), więc nie potrzebujemy server action.
5. **Slug inwestycji jest de facto globalnym ID.** Strona inwestycji ignoruje segmenty miasta i dewelopera w URL [P], a `map/investments/visible/{slug}` przyjmuje sam slug [P].
6. **Nazewnictwo backendu jest mylące**: w RCN „invest” oznacza budynek/adres (`invest_rcn_id`), a „sale” oznacza lokal. Domena powinna to przemianować (Building/Unit/Transaction).
7. **Typy liczbowe są niespójne**: kwoty raz jako `number`, raz jako `string` (`"amount": "994012"`). Daty to raz `YYYY-MM-DD`, raz ISO z `T00:00:00.000Z`. Warstwa DTO→domena musi to normalizować.
