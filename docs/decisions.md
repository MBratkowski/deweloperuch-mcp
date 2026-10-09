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
- Cache odpowiedzi z TTL ≈ `s-maxage` endpointu (5 min dla ofert, 1–24 h dla statystyk).
- Brak funkcji masowego crawlowania (np. „pobierz wszystkie transakcje w Polsce”).
- Timeouty i czytelne błędy dla 4xx/429/5xx; respektowanie `Retry-After`.
- User-Agent: do ustalenia (U1/T11). Preferowany uczciwy identyfikator klienta, o ile nie jest blokowany.

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

---

## Proponowany pierwszy vertical slice

**Cel:** przejść przez wszystkie warstwy i oba kanały transportu (JSON i RSC) na najważniejszej ścieżce użytkownika: *„znajdź mieszkania deweloperskie w X w budżecie Y, pokaż szczegóły i historię ceny”*.

| Capability | Kanał | Dlaczego w slice |
|---|---|---|
| `search_locations` | A | model musi zamienić „Kraków, Podgórze” na `city_slug` i dzielnicę |
| `search_offers` | **B (RSC)** | najtrudniejszy kanał; jego wczesna walidacja zdejmuje główne ryzyko architektury |
| `get_offer` (z historią ceny) + `get_investment` | A | stabilny JSON; pokazuje mapowanie DTO→domena (typy string/number, daty, zdarzenia) |

Zakres techniczny slice'a: klient HTTP z limiterem i cache (D2), adaptery JSON i RSC, DTO + domena dla Offer/Investment/Developer/PriceEvent/Location, 4 komendy CLI, 4 narzędzia MCP, testy kontraktowe na próbkach i jeden ręczny smoke test na żywo.

Poza slice'em (kolejne iteracje): transakcje RCN i budynki → wycena → statystyki → GUS/NBP.
