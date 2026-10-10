# Serwer MCP `deweloperuch-mcp`

Serwer MCP (SDK `mcp`, `MCPServer`) z danymi o cenach ofertowych mieszkań od deweloperów (rynek pierwotny) z deweloperuch.pl. Tylko odczyt. `serverInfo.name` to `deweloperuch`, `version` to wersja pakietu.

**Transport: tylko stdio** (tymczasowo, do potwierdzenia przez użytkownika). Serwer nie ma opcji poza `-h/--help`; uruchamia go klient MCP i rozmawia z nim przez stdin/stdout. Wszystko inne (logi) idzie na stderr.

## Narzędzia

| Narzędzie | Do czego |
|---|---|
| [`search_locations`](tools/search_locations.md) | Zamienia nazwę miasta, dzielnicy lub ulicy na `city_slug`. |
| [`search_offers`](tools/search_offers.md) | Strona ofert w mieście (albo w całej Polsce) z filtrami ceny i metrażu. |
| [`get_offer`](tools/get_offer.md) | Jedna oferta z pełną historią ceny. |
| [`get_investment`](tools/get_investment.md) | Inwestycja z deweloperem i listą ofert. |

Wszystkie cztery mają adnotacje `readOnlyHint=true` i `openWorldHint=true`. Typowa kolejność: `search_locations` → `search_offers` → `get_investment` albo `get_offer`.

## Instrukcje serwera (`instructions`)

> Dane z deweloperuch.pl: ceny ofertowe mieszkań od deweloperów (rynek pierwotny) w Polsce, z historią zmian cen. Typowa kolejność: search_locations (nazwa miejsca -> city_slug), search_offers (oferty w mieście z filtrami ceny i metrażu), potem get_investment (oferty jednej inwestycji) albo get_offer (jedna oferta z historią ceny). Serwis jest projektem społecznym: pytaj oszczędnie i zawężaj filtry zamiast przeglądać kolejne strony. Gdy błąd narzędzia zawiera STOP, przestań używać tych narzędzi, niczego nie ponawiaj, nie szukaj obejścia i powiedz o tym użytkownikowi, podając powód z komunikatu. Dalsze kroki należą do użytkownika; sam niczego nie odblokowuj ani nie uruchamiaj ponownie. Błędy walidacji argumentów bywają po angielsku: popraw wskazane pole zgodnie ze schematem i ponów.

## Konfiguracja klienta MCP

Po `uv sync` (zob. [README](../../README.md#quickstart)) skrypt jest w `.venv/bin/deweloperuch-mcp`. Przykład wpisu w konfiguracji klienta (format `mcpServers`, np. Claude Desktop, Claude Code `.mcp.json`):

```json
{
  "mcpServers": {
    "deweloperuch": {
      "command": "uv",
      "args": ["run", "--directory", "/ścieżka/do/deweloperuch-mcp", "deweloperuch-mcp"]
    }
  }
}
```

Albo bez `uv` w czasie uruchomienia, pełną ścieżką:

```json
{
  "mcpServers": {
    "deweloperuch": {
      "command": "/ścieżka/do/deweloperuch-mcp/.venv/bin/deweloperuch-mcp"
    }
  }
}
```

Serwer nie czyta żadnych własnych zmiennych środowiskowych. Zamek limitera i zapis STOP: `XDG_CACHE_HOME` ([konfiguracja](../configuration.md)).

## Reguły argumentów

- **Liczby:** JSON-owa liczba całkowita albo tekst z samych cyfr (`"10"`, `" 10 "`, z opcjonalnym `+`/`-`, do 18 cyfr). Odrzucane: `"10.0"`, tekst z innymi znakami, `true`/`false`. (Liczba JSON `10.0` jest przyjmowana jako 10.)
- **Opcjonalne** (`price_min`, `price_max`, `area_min`, `area_max`, `sort`): `""` albo `null` znaczy „brak”.
- **Z wartością domyślną:** `null` znaczy wartość domyślną: `page` (1), `per_page` (10), `limit` (20), `include_history` (`false`). `include_history: ""` jest błędem.
- **`sort`** jest przycinany (`" price_asc "` działa).
- Teksty (`query`, `city`, slugi) są walidowane przez usługi; błąd ma polski komunikat.

## Błędy

- **Błąd domenowy:** wynik narzędzia z `isError=true` i jednym polskim komunikatem, który mówi, co zmienić albo że seria się zatrzymała. Komunikat nie zawiera ścieżek, nazw propsów ani treści odpowiedzi serwisu. Szczegóły techniczne (cel, status, fragment ciała, z escapowanymi znakami niedrukowalnymi) trafiają tylko do logu serwera na stderr.
- **STOP** (401, 403, 429, challenge Cloudflare): komunikat zaczyna się od `STOP:`, jest bez przedrostka domenowego i kończy się wezwaniem do przerwania i zgłoszenia użytkownikowi. Teksty (dla modelu; bez czasów, źródła, ścieżek i informacji, jak zdjąć blokadę):
  - **pierwszy STOP w procesie:** `STOP: HTTP 403 (odmowa dostępu). Klient nie wyśle już żadnego zapytania; inne procesy też zostały wstrzymane. Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.` Analogicznie `HTTP 401 (brak autoryzacji)` i `HTTP 429 (limit zapytań)`. Challenge Cloudflare: `STOP: challenge Cloudflare (captcha/WAF). …` (przy statusie będącym STOP-em z etykietą statusu, np. `STOP: HTTP 403 (odmowa dostępu), challenge Cloudflare (captcha/WAF). …`);
  - **powtórne wywołanie w tym procesie:** `STOP: seria zapytań do deweloperuch.pl jest już przerwana; zapytanie nie zostało wysłane. Powód: HTTP 403 (odmowa dostępu). Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.`;
  - **z zapisu innego procesu (CLI, recon, inny serwer), 401/403/challenge:** `STOP: seria zapytań do deweloperuch.pl jest wstrzymana po wcześniejszym STOP (HTTP 403, odmowa dostępu). Zapytanie nie zostało wysłane. Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.` (dla challenge: `(challenge Cloudflare, captcha/WAF)`);
  - **z zapisu, 429:** `STOP: seria zapytań do deweloperuch.pl jest wstrzymana po wcześniejszym STOP (HTTP 429, limit zapytań); wstrzymanie trwa jeszcze ok. N s. Zapytanie nie zostało wysłane. Nie ponawiaj w tej sesji; przerwij i zgłoś to użytkownikowi.`;
  - **nieczytelny zapis:** `STOP: seria zapytań do deweloperuch.pl jest wstrzymana bezterminowo, bo zapis o wcześniejszym STOP jest nieczytelny. Zapytanie nie zostało wysłane. Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.`

  Szczegóły (źródło, PID, czasy, pauza limitera) trafiają tylko do logu serwera na stderr. Pozostałe błędy serwisu (5xx, sieć i inne) też są bez szczegółów i mówią „Nic nie ponawiam; spróbuj później.”.
- **Nieoczekiwany wyjątek:** `Nieoczekiwany błąd serwera MCP deweloperuch (szczegóły są w jego logu). Nie ponawiaj tego wywołania; zgłoś problem użytkownikowi.`
- **Błąd walidacji schematu** (zły typ, brak pola, wartość spoza `enum`/zakresu): generuje SDK, po angielsku, z prefiksem `Error executing tool …`. Popraw wskazane pole zgodnie z `inputSchema` i ponów. Komunikat zawiera link `errors.pydantic.dev`: to szum SDK, nie dane z serwisu.

Błędy usług (`Wyszukiwanie ofert w 'warszawa': …`, `Inwestycja 'smolna': …`) dostają kontekst domenowy; zob. [konfiguracja, błędy pakietu](../configuration.md#błędy-pakietu).

### STOP: informacje dla człowieka konfigurującego serwer

Tej części model nie dostaje. Po STOP żadne narzędzie nie wysyła zapytań (odpowiedzi jeszcze świeże w cache serwer nadal może zwracać):

- STOP zapisany przez dowolny proces (CLI, recon, inny serwer MCP) wstrzymuje ten serwer, dopóki zapis jest aktywny; 429 wygasa po pauzie, 401, 403 i challenge są bezterminowe ([konfiguracja](../configuration.md#stop-blokada-między-procesami)).
- Serwer, który raz zwrócił STOP (własny albo z zapisu innego procesu), jest **zatrzaśnięty do restartu**: pozostaje wstrzymany także po zdjęciu zapisu i po wygaśnięciu 429. Po wyjaśnieniu przyczyny uruchom go ponownie.
- Zapis sprawdzisz i zdejmiesz wyłącznie w CLI: [`deweloperuch stop status`](../cli/commands/stop-status.md), [`deweloperuch stop clear`](../cli/commands/stop-clear.md). Narzędzia MCP do zdejmowania blokady nie ma, a agentom w Claude Code blokuje tę komendę hook Bash.

## Rozmiary wyników

Kompaktowy JSON w treści (ta sama zawartość co `structuredContent`), pełne strony z próbek:

| Wywołanie | Znaki |
|---|---|
| `search_locations` | 682 |
| `search_offers`, 10 (domyślnie) | 3 398 |
| `search_offers`, 50 | 16 133 |
| `search_offers`, 50, `city=polska` | 18 183 |
| `get_investment`, `limit` 0 | 456 |
| `get_investment`, 20 (domyślnie) | 6 199 |
| `get_investment`, 50 | 14 819 |
| `get_investment`, 200 | 57 919 |

Cały `tools/list` ma ok. 18,3 tys. znaków. Listy mają `total`/`returned`/`truncated`; wyniki nie zawierają pól `null`, poza `total` w `search_locations` (zawsze obecne, `null` przy obcięciu).

## Zakończenie pracy

- EOF na stdin: czyste wyjście, kod 0.
- SIGINT: `KeyboardInterrupt` z tracebackiem na stderr.

## Uwaga dla hosta (stderr)

Serwer loguje na stderr: INFO przy błędach domenowych, a przy nieoczekiwanym błędzie rich traceback o rozmiarze ok. 29 KB. **Host musi czytać albo opróżniać stderr serwera**, inaczej bufor pipe może się zapchać i serwer się zawiesi. Logi `httpx` na stderr zawierają URL-e zapytań do serwisu (nie trafiają do modelu).

## Dokumentacja rekonesansu

Dane i ich ograniczenia: [discovery](../discovery/README.md), [endpoints](../discovery/endpoints.md), [pages-rsc](../discovery/pages-rsc.md), [entities](../discovery/entities.md). Otwarte pytania: [open-questions](../open-questions.md).

_Źródło: `src/deweloperuch_mcp/mcp_server.py`, `src/deweloperuch_mcp/mcp_results.py`, `tests/snapshots/mcp_tools.json`_
