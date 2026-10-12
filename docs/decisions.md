# Decyzje architektoniczne

Format: krótkie ADR. Status: **przyjęta** (wynika wprost z discovery), **proponowana** (czeka na akceptację), **otwarta**.

---

## D1. Kolejność kanałów: JSON API → RSC → server actions (przyjęta)

**Kontekst.** Dane są dostępne czterema kanałami o różnej stabilności ([discovery/README.md](discovery/README.md#2-kanały-dostępu-do-danych)).
**Decyzja.** Dla każdej capability używamy JSON `/api/*`, jeśli daje potrzebne dane. RSC tylko tam, gdzie JSON nie istnieje (wyszukiwanie z filtrami i paginacją, profil dewelopera, raporty, GUS/NBP). Server actions tylko wtedy, gdy nie ma alternatywy (na dziś: żadna capability v1).
**Konsekwencje.** Klient ma dwa adaptery transportowe: `json` i `rsc`. Adapter RSC jest izolowany i pokryty testami kontraktowymi na zapisanych próbkach, bo nazwy propsów mogą się zmienić bez zapowiedzi.

## D2. Oszczędny, przewidywalny klient HTTP (przyjęta, szczegóły otwarte, patrz U1/T11)

**Kontekst.** `robots.txt`: `Disallow: /api/`, `Crawl-delay: 1`. Serwis jest projektem społecznym za Cloudflare. Brak auth.
**Decyzja.**
- Globalny limiter: domyślnie ≤1 request/s, 1 request jednocześnie (konfigurowalne w dół, nie w górę bez świadomej decyzji).
- Cache odpowiedzi w pamięci procesu. **Doprecyzowanie (2026-10-10, polecenie użytkownika „popraw” po przebiegu e2e):**
  - TTL = świeżość odpowiedzi minus `Age`, najwyżej 300 s; świeżość to `s-maxage`, a bez niego `max-age`, a bez obu 300 s.
  - TTL ≤ 0 oznacza brak cache; błędy nie trafiają do cache.
  - Odpowiedź z dyrektywą `no-store` albo `no-cache` w `Cache-Control` (dowolna wielkość liter, także z wartością) nie trafia do cache. `private` i `must-revalidate` nie zmieniają TTL, bo cache jest prywatny dla procesu.
  - Dane lokalne nie są więc starsze niż 5 min, a powtórzenia w tym oknie nie idą do serwisu.
  - Pierwotna reguła „TTL ≈ `s-maxage`” dawała TTL ≤ 0 dla stron i `/api/*` z `max-age=28800` przy dużym `Age` z Cloudflare, więc każde powtórzenie szło do sieci (wykrył to zestaw e2e).
- Brak funkcji masowego crawlowania (np. „pobierz wszystkie transakcje w Polsce”).
- Timeouty i czytelne błędy dla 4xx/429/5xx; respektowanie `Retry-After`.
- User-Agent: do ustalenia (U1/T11). Preferowany uczciwy identyfikator klienta, o ile nie jest blokowany.

**Doprecyzowanie (2026-10-10, decyzja użytkownika): trwały STOP między procesami.**
- Po 401, 403, 429 albo challenge Cloudflare proces zapisuje STOP w `stop.json` obok zamka limitera (`${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/`). Dopóki zapis jest aktywny, żaden proces (CLI, serwer MCP, `recon/probe.py`, `recon/scan_bundles.py`) nie wysyła zapytań.
- STOP po 429 wygasa po pauzie; 401, 403 i challenge trwają do zdjęcia. Nieczytelny zapis oznacza STOP bezterminowy (fail-closed).
- Zdejmuje go wyłącznie użytkownik przez `deweloperuch stop clear`, bez dodatkowego potwierdzenia w terminalu. Agentów blokują hook Bash i reguła w `CLAUDE.md`; narzędzia MCP do zdejmowania nie ma.
- Proces, który zwrócił STOP, pozostaje zatrzaśnięty do restartu. Dotyczy to też serwera MCP, nawet po zdjęciu zapisu albo wygaśnięciu 429.
- Szczegóły: [configuration.md](configuration.md#stop-blokada-między-procesami), handoff `2026-10-10-0740-trwaly-stop-miedzy-procesami`.

## D3. Nazewnictwo domenowe niezależne od backendu (przyjęta)

**Kontekst.** Backend nazywa budynek RCN „invest”, lokal „sale”, a pola mają niespójne typy ([entities.md](discovery/entities.md)).
**Decyzja.** Model domenowy: `Developer`, `Investment`, `Offer`, `PriceEvent`, `Building`, `Unit`, `Transaction`, `Location`, `Valuation`, `TimeSeries`. DTO odzwierciedlają backend 1:1 (z tolerancją typów), a mapowanie DTO→domena normalizuje liczby, daty i puste stringi.

## D4. Limit wyszukiwania jawny w kontrakcie (przyjęta)

**Kontekst.** Listy RSC zwracają najwyżej 20 stron × 100 = 2000 rekordów, przy `total` sięgającym np. 351 314.
**Decyzja.** Wyniki wyszukiwania zawierają `total`, `returned`, `truncated` i podpowiedź, by zawęzić filtry. Agregaty (np. `stats` z listy transakcji) są pokazywane zamiast żądania pełnych danych.

## D5. Ciężkie zrzuty nie trafiają do MCP (przyjęta)

`map/powiat-sales` (do ~80 MB), `rawTransactions` (12,9 MB HTML), pełny `radiusPool` wyceny (180 KB) nie są wystawiane bezpośrednio. Jeśli kiedyś będą potrzebne, to jako wewnętrzne źródło lokalnego indeksu z osobną decyzją.

## D6. Wspólny core, cienkie adaptery (przyjęta, zgodnie z założeniem projektu)

```
deweloperuch client (http + json adapter + rsc adapter + DTO)
        │
        ▼
domain / services  (capabilities z capability-matrix, model domenowy, mapowanie DTO→domena)
     │         │
     ▼         ▼
    CLI       MCP     (parsowanie argumentów / schematy tooli, formatowanie outputu)
```
CLI i MCP wołają te same funkcje serwisów. CLI służy też jako narzędzie developerskie (`--json`, `--raw` dla DTO).

**Doprecyzowanie (2026-10-10, decyzja użytkownika):**
- W v1 nie ma `--raw`; surowe dane daje `recon/probe.py`.
- `services.Session` jest jedynym punktem wejścia.
- CLI i MCP importują z pakietu tylko `services`, `errors` i `domain.models`; MCP dodatkowo własną reprezentację `mcp_results`. Pilnuje tego `tests/test_layering.py`.

## D7. Wykrywanie dryfu serwisu (proponowana)

`recon/scan_bundles.py` listuje ścieżki `/api/*` i server actions z aktualnych bundli. Testy kontraktowe na `docs/discovery/samples/` plus okresowe (ręczne) uruchomienie skanera pokażą zmiany po deployach serwisu. Bez automatycznego crawla w CI.

## D8. Stos technologiczny (przyjęta 2026-10-09: Python)

**Decyzja użytkownika:** Python: FastMCP, pydantic, httpx, typer; pytest + pytest-socket + respx, ruff, mypy, uv. Tabela poniżej zostaje jako uzasadnienie.

**Doprecyzowanie (2026-10-09, decyzja użytkownika):**
- Serwer MCP budujemy na oficjalnym SDK `mcp>=2.3`. W linii 2.x FastMCP przemianowano na `MCPServer` (`from mcp.server.mcpserver import MCPServer`), a `mcp.server.fastmcp` jest tylko shimem z błędem migracji. Odrzucono przypięcie `mcp<2`.
- `mcp` 2.x ciągnie też pakiet `httpx2`. Klient projektu jawnie używa `httpx`, bo respx mockuje tylko `httpx`.

| | Python | TypeScript |
|---|---|---|
| MCP | oficjalny SDK z FastMCP (dekoratory, schemat z type hints) | oficjalny `@modelcontextprotocol/sdk` (najdojrzalszy) |
| Modele/walidacja | pydantic: tolerancyjne DTO, łatwa normalizacja | zod: schematy współdzielone z inputem tooli |
| CLI | typer/click | commander/yargs |
| Dystrybucja | `uvx deweloperuch-mcp` | `npx deweloperuch-mcp` |
| Fit do projektu | narzędzia recon już w Pythonie; praca z danymi i agregatami | ekosystem MCP i Next.js w JS; jeden język z serwisem (bez praktycznego zysku) |

Rekomendacja: **Python**. Domena to głównie normalizacja i agregacja danych, pydantic dobrze obsługuje niespójne typy z backendu, a FastMCP daje mało boilerplate'u. TypeScript też jest w pełni uzasadniony, jeśli zespół woli JS.

## D9. Żywe zapytania do czasu rozstrzygnięcia U1 (przyjęta 2026-10-09, tymczasowa)

**Kontekst.** Polityka wobec `robots.txt: Disallow: /api/` (U1) jest otwarta.
**Decyzja użytkownika.** Dopóki U1 nie jest rozstrzygnięte, każda seria żywych zapytań (weryfikacja hipotez, skan driftu) wymaga jawnej zgody użytkownika w bieżącej rozmowie. User-Agent to jedna stała. Jej wartość wybiera użytkownik przy rozstrzyganiu U1; do tego czasu zostaje obecna wartość ze skanera, oznaczona `TODO(U1)`.

**Doprecyzowanie (2026-10-09, decyzja użytkownika):** stała `USER_AGENT` mieszka w module pakietu `deweloperuch_mcp` (tylko stdlib), bo zainstalowany pakiet nie widzi katalogu `recon/`. `recon/config.py` ją reeksportuje. Wykonane 2026-10-09: `BASE_URL` i `USER_AGENT` są zdefiniowane w `src/deweloperuch_mcp/identity.py`. Test w `tests/test_identity.py` pilnuje jednej definicji User-Agenta.

## D10. Poziom wymuszania zasad przez Claude Code (przyjęta 2026-10-09)

**Decyzja użytkownika.**
- Hooki są siatką na pomyłki, nie granicą bezpieczeństwa:
  - własność plików per agent dla Edit/Write/NotebookEdit;
  - blokada URL-i serwisu w Bash;
  - przypomnienie o handoffie.
- Testy blokują sieć przez `pytest-socket`.
- Narzędzia przeglądarki (`mcp__claude-in-chrome`) wymagają potwierdzenia przy każdym użyciu.
- Bez sandboxa Claude Code.

Konfiguracja: `.claude/settings.json`, `.claude/hooks/`, zasady w `CLAUDE.md`.

**Doprecyzowanie (2026-10-10, decyzja użytkownika):**
- Testy serwera MCP dopuszczają gniazda AF_UNIX (potrzebne pętli asyncio); AF_INET, AF_INET6 i DNS są dalej zablokowane.
- Testy uruchamiające podprocesy wstawiają w nich guard pytest-socket (`NO_NETWORK` w `tests/test_mcp_server.py`, guard w `tests/throttle_worker.py`) i nie wołają ścieżek, które mogłyby dojść do usług.
- Hook Bash blokuje też agentom zdejmowanie STOP (D2): `deweloperuch … stop clear` oraz zmiany i usuwanie plików limitera.

**Doprecyzowanie (2026-10-10, polecenie użytkownika: „pisz e2e testy”, „zrób jak najwięcej testów e2e”): wyjątek dla zestawu e2e.**
- Opcjonalny zestaw `tests/e2e/` łączy się z żywym serwisem, ale wyłącznie przez podprocesy: serwer MCP przez stdio, CLI i `probe`. Sam proces testów nadal ma blokadę sieci (dopuszcza tylko AF_UNIX).
- Uruchamia się tylko przy obu włącznikach naraz: `DEWELOPERUCH_LIVE=1` i `-m live`. Domyślny `uv run pytest` go pomija i nie łączy się z siecią.
- Uruchomienie to seria żywych zapytań w rozumieniu D9: wymaga zgody użytkownika i nie może iść równolegle z recon-verifierem ani drift-checkerem.
- Budżet zapytań na przebieg jest twardy i pilnuje go asercja w zestawie.
- Zestaw korzysta ze wspólnego limitera i zapisu STOP (D2). STOP kończy przebieg bez ponowień.
- Testy offline korzystają z prawdziwych odpowiedzi serwisu: próbek `docs/discovery/samples/` i surowych payloadów `tests/fixtures/`. Payloadów nie buduje się z założeń, chyba że test sprawdza sam kształt.

## D11. Interfejs MCP i CLI v1 (przyjęta 2026-10-10, decyzja użytkownika)

**Kontekst.** S1b dało pierwszy publiczny interfejs; rozmiar wyniku dla modelu to główne ograniczenie MCP.
**Decyzja.**
- **Transport MCP: tylko stdio** (rozstrzyga U3).
  - Narzędzia mają adnotacje `readOnlyHint` i `openWorldHint`, bez `idempotentHint`.
  - Błędy wracają jako wynik `isError` z polskim komunikatem, nie jako `ToolError`.
- **Reprezentacja MCP** (`mcp_results.py`) jest osobna od modelu domenowego.
  - Pozycje są skrócone, a pola `null` pomijane, z wyjątkiem `total` (D4), które jest zawsze obecne.
  - `search_offers.per_page` ∈ {10, 50}, domyślnie 10.
  - `get_investment.limit`: domyślnie 20, najwyżej 200.
- **CLI:**
  - `--json` daje pełny model domenowy, `offers search --per-page` przyjmuje 10/50/100, a `investments get` domyślnie pokazuje wszystkie oferty.
  - Kody wyjścia: 0 OK, 1 inny błąd, 2 błędne wejście, 3 STOP, 4 błąd serwisu, 5 limiter, 6 nieoczekiwana odpowiedź, 7 brak zasobu.
- **Wejście MCP:**
  - liczby całkowite przyjmowane także jako tekst z samych cyfr; `true`/`false` w polach liczbowych odrzucane;
  - `""` i `null` oznaczają brak wartości albo wartość domyślną; `sort` jest przycinany.
- **Parametry:** usługi i schematy wystawiają tylko parametry `[P]`. Rozszerzenia przychodzą po weryfikacji (przepływ B).

**Konsekwencje.** Większe strony (100) i pełne modele są dostępne w CLI, nie w MCP. Zmiana tych limitów zmienia snapshot `tests/snapshots/mcp_tools.json`.

## D12. Komunikaty błędów: dla modelu bez szczegółów backendu (przyjęta 2026-10-10, decyzja użytkownika)

**Kontekst.** Ścieżki, nazwy propsów i treść odpowiedzi serwisu w komunikacie dla modelu to kanał prompt injection i szum. Sekwencje terminala w treści odpowiedzi to ryzyko dla CLI.
**Decyzja.**
- `str(err)` jest domenowy (co się stało z ofertą, inwestycją, wyszukiwaniem i co zrobić). Nie zawiera ścieżek, propsów, treści odpowiedzi, rozmiarów ani etykiet decyzji.
- Szczegóły techniczne idą do `err.detail`, zawsze escapowane (`errors.printable`). MCP zapisuje je tylko w logu na stderr, CLI pokazuje w linii `Szczegóły:`.
- Komunikaty STOP mówią tylko, co zatrzymało serię, i każą przerwać i zgłosić to użytkownikowi. Nie podają czasów, źródła ani sposobu zdjęcia blokady, a tekst z pliku STOP nigdy nie trafia do modelu.

**Doprecyzowanie (2026-10-11, polecenie użytkownika: w tabeli wyników „powinny być linki”): linki do publicznych stron.**
- Wyniki mogą zawierać pełne adresy publicznych stron serwisu dla człowieka, wyłącznie w dedykowanych polach `url` (np. strona inwestycji, profil dewelopera, lista ofert z tymi samymi filtrami).
- Adresy buduje jedna funkcja z potwierdzonych [P] wzorców stron z `docs/discovery/pages-rsc.md`. Bez parametru `_rsc` i bez ścieżek `/api/*`.
- Komunikaty błędów nadal nie zawierają żadnych adresów ani ścieżek.
- Adresu, którego wzorzec nie jest [P], nie podajemy (dziś: strona pojedynczej oferty).
- Link listy ofert zawiera publiczne parametry strony (np. `filterPrice`, `sortBy=amount`). To świadomy wyjątek od D3: są częścią adresu, który użytkownik otwiera, a nie nazwami pól wyniku.
- Pola z linkami nazywają to, na co wskazują: `list_url` (lista ofert), `investment_url`, `developer_url`.

---

## Proponowany pierwszy vertical slice

**Cel:** przejść przez wszystkie warstwy i oba kanały transportu (JSON i RSC) na najważniejszej ścieżce użytkownika: *„znajdź mieszkania deweloperskie w X w budżecie Y, pokaż szczegóły i historię ceny”*.

| Capability | Kanał | Dlaczego w slice |
|---|---|---|
| `search_locations` | A | model musi zamienić „Kraków, Podgórze” na `city_slug` i dzielnicę |
| `search_offers` | **B (RSC)** | najtrudniejszy kanał; jego wczesna walidacja zdejmuje główne ryzyko architektury |
| `get_offer` (z historią ceny) + `get_investment` | A | stabilny JSON; pokazuje mapowanie DTO→domena (typy string/number, daty, zdarzenia) |

Zakres techniczny slice'a: klient HTTP z limiterem i cache (D2), adaptery JSON i RSC, DTO + domena dla Offer/Investment/Developer/PriceEvent/Location, 4 komendy CLI, 4 narzędzia MCP, testy kontraktowe na próbkach i jeden ręczny smoke test na żywo.

**Stan (2026-10-10):** slice zrobiony bez smoke testu na żywo (S1a `23cd5be`, S1b `a954994`). Smoke test czeka na zgodę na serię żywych zapytań (D9).

Poza slice'em (kolejne iteracje): transakcje RCN i budynki → wycena → statystyki → GUS/NBP.
