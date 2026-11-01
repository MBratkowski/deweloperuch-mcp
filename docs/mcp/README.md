# MCP server `deweloperuch-mcp`

An MCP server (SDK `mcp`, `MCPServer`) with data on developers' asking prices for apartments (primary market) from deweloperuch.pl. Read-only. `serverInfo.name` is `deweloperuch`, `version` is the package version.

**Transport: stdio only.** The server has no options other than `-h/--help`; an MCP client starts it and talks to it over stdin/stdout. Everything else (logs) goes to stderr.

Tool descriptions, schema field descriptions, `instructions` and error messages are product texts in Polish and are quoted verbatim in this documentation, with short English summaries.

## Tools

| Tool | Purpose |
|---|---|
| [`search_locations`](tools/search_locations.md) | Turns the name of a city, district or street into a `city_slug`. |
| [`search_offers`](tools/search_offers.md) | A page of offers in one city or one of its districts (not the whole of Poland) with price, area, price-per-m², district, status and price-drop filters and sorting. |
| [`get_offer`](tools/get_offer.md) | One offer with its full price history and `price_flags`. |
| [`search_investments`](tools/search_investments.md) | Investments of a city (averages, sorting, filter by developer) or by name across Poland. |
| [`get_investment`](tools/get_investment.md) | An investment with its developer and a list of offers, optionally with each offer's price history. |
| [`search_developers`](tools/search_developers.md) | Turns a developer name into a `developer_slug`. |
| [`get_developer`](tools/get_developer.md) | A developer profile: summary (computed from the investments), investments with active offers and cities; no website or description. |
| [`get_market_statistics`](tools/get_market_statistics.md) | Offer-market statistics of one city as of a day (`as_of`): counts, price, price per m² and area distributions, the largest developers. |
| [`get_transaction_statistics`](tools/get_transaction_statistics.md) | Transaction prices (RCN) of a city by month (secondary market) or quarter, since 2017. |
| [`rank_locations`](tools/rank_locations.md) | A ranking of places or powiats by RCN transactions and price per m². |
| [`get_building`](tools/get_building.md) | A building from the RCN with its units and transactions, optionally with the neighbourhood trend. |
| [`estimate_property_value`](tools/estimate_property_value.md) | An approximate value of an apartment at a point from nearby RCN transactions. |
| [`get_government_statistics`](tools/get_government_statistics.md) | Official GUS, NBP and Eurostat time series for Poland, an aggregate or a city (market context, not offers). |

All 13 have the annotations `readOnlyHint=true` and `openWorldHint=true`. Typical order: `search_locations` → `search_offers` → `get_investment` or `get_offer`; `search_investments` / `search_developers` turn names into slugs; to judge an offer price: `get_offer` (`price_flags`), then `get_market_statistics` or `estimate_property_value`. Three kinds of prices are not to be mixed: developers' asking prices (`search_offers`, `get_offer`, `search_investments`, `get_investment`, `get_developer`, `get_market_statistics`), RCN transaction prices (`get_transaction_statistics`, `rank_locations`, `get_building`, `estimate_property_value`) and official NBP, GUS and Eurostat data (`get_government_statistics`).

## Prompts

Four prompts (`prompts/list`, shown in Claude Desktop as ready-made commands) guide the model through the tools. They send no requests themselves. See [prompts.md](prompts.md).

## Server instructions (`instructions`)

> Dane z deweloperuch.pl o mieszkaniach w Polsce. Typowy plan: search_locations (nazwa miejsca -> city_slug), search_offers (oferty w mieście albo dzielnicy, z filtrami), potem get_offer (oferta z historią ceny) albo get_investment (oferty jednej inwestycji). Projekty w mieście i slug inwestycji po nazwie daje search_investments, slug dewelopera po nazwie search_developers (dalej get_developer). Ocena ceny oferty: get_offer (price_flags), potem porównaj z get_market_statistics albo estimate_property_value.
>
> Trzy rodzaje cen, nie mieszaj ich: ofertowe deweloperów (search_offers, get_offer, search_investments, get_investment, get_developer, get_market_statistics); transakcyjne z rejestru RCN (get_transaction_statistics, rank_locations, get_building, estimate_property_value; najnowsze okresy są niepełne, get_transaction_statistics oznacza je incomplete, a jego miesiące to tylko rynek wtórny); oficjalne NBP, GUS i Eurostatu, obok cen także mieszkania oddane, bezrobocie i wynagrodzenia (get_government_statistics). Jego location: polska, agregat (np. 7-miast) albo slug miasta (małe litery, bez polskich znaków, myślniki); search_locations tylko pomocniczo.
>
> Serwis jest projektem społecznym: pytaj oszczędnie i zawężaj filtry zamiast przeglądać kolejne strony. Gdy błąd narzędzia zawiera STOP, przestań używać tych narzędzi, niczego nie ponawiaj, nie szukaj obejścia i powiedz o tym użytkownikowi, podając powód z komunikatu. Dalsze kroki należą do użytkownika; sam niczego nie odblokowuj ani nie uruchamiaj ponownie. Gdy narzędzie odrzuci argumenty, popraw wskazane pola zgodnie z komunikatem i ponów. Gdy błąd mówi, że serwis mógł się zmienić, nie ponawiaj tego wywołania i powiedz o tym użytkownikowi; inne narzędzia mogą nadal działać. Pola kończące się na _url to linki do stron deweloperuch.pl: podawaj je użytkownikowi, np. w tabeli ofert.

Summary (three paragraphs): (1) what the data is and the typical plan: `search_locations` → `search_offers` (a city or one of its districts) → `get_offer` or `get_investment`; `search_investments` gives projects and investment slugs, `search_developers` developer slugs (then `get_developer`); to judge an offer price use `get_offer` (`price_flags`), then compare with `get_market_statistics` or `estimate_property_value`. (2) The three kinds of prices that must not be mixed: asking prices (`search_offers`, `get_offer`, `search_investments`, `get_investment`, `get_developer`, `get_market_statistics`), RCN transaction prices (the newest periods are incomplete and `get_transaction_statistics` marks them `incomplete`; its months are the secondary market only) and official NBP, GUS and Eurostat data (`get_government_statistics`), whose `location` is `polska`, an aggregate (for example `7-miast`) or a city slug (lower case, no Polish characters, hyphens); `search_locations` only helps. (3) The service is a community project, so ask sparingly and narrow filters instead of paging; on a STOP error stop using the tools, retry nothing, look for no workaround, report the reason to the user and unblock or restart nothing yourself; when a tool rejects arguments, fix the indicated fields and retry; when an error says the service may have changed, do not retry that call, tell the user, and know that other tools may still work; fields ending in `_url` are links to deweloperuch.pl pages to be shown to the user.

### Links to service pages

Results contain addresses of public pages for humans, only in `*_url` fields: `list_url` (`search_offers`, `get_market_statistics`: the offer list with the same filters; for a `search_offers` call with a `district`, that district's list), `investment_url` (`search_offers`, `search_investments`, `get_investment`, `get_offer`, `get_developer`), `developer_url` (`search_developers`, `search_investments`, `get_investment`, `get_offer`, `get_developer`, `get_market_statistics`), `stats_url` (`get_government_statistics`, `get_transaction_statistics`), `ranking_url` (`rank_locations`, `level=city`) and `building_url` (`get_building`):

- only page patterns listed in [pages-rsc.md](../discovery/pages-rsc.md) are built: the offer list of a city or of a district, the developer profile, the investment, the statistics pages, the transaction ranking and the building page;
- `list_url` has no `page=1`: the first page is the address without a `page` parameter (the service redirects `page=1` to it), e.g. `https://deweloperuch.pl/ceny-ofertowe/warszawa/mieszkania?perPage=10`, and `https://deweloperuch.pl/ceny-ofertowe/warszawa/mokotow/mieszkania?perPage=10` for a district;
- `stats_url` of `get_transaction_statistics` is `https://deweloperuch.pl/statystyki/{city}/transakcje`; that of `get_government_statistics` is `https://deweloperuch.pl/statystyki/{location}/dane-rzadowe#{section}`, where the anchor is an id from that location's own list of sections (it differs per location);
- without `_rsc` and `/api/`; no link to a single offer (its page is not confirmed);
- a missing slug means no link (the field is omitted); the `offers` items in `get_investment` and the `comparables` of `estimate_property_value` have no links;
- error messages contain no addresses.

## MCP client configuration

Installation options (Claude Desktop extension, `uvx` from PyPI or GitHub, from source): [README](../../README.md#install). Windows is supported starting with 0.1.3. With `uvx` the entry is `"command": "uvx", "args": ["deweloperuch-mcp"]` (if the client reports `spawn uvx ENOENT`, use the full path from `which uvx`, or `(Get-Command uvx).Source` in PowerShell). For a source checkout, after `uv sync` the script is at `.venv/bin/deweloperuch-mcp` on macOS/Linux or `.venv\Scripts\deweloperuch-mcp.exe` on Windows. JSON paths use doubled backslashes, e.g. `"C:\\path\\to\\deweloperuch-mcp"`. An example entry in the client configuration (`mcpServers` format, e.g. Claude Desktop, Claude Code `.mcp.json`):

```json
{
  "mcpServers": {
    "deweloperuch": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/deweloperuch-mcp", "deweloperuch-mcp"]
    }
  }
}
```

Or without `uv` at run time, by full path:

```json
{
  "mcpServers": {
    "deweloperuch": {
      "command": "/path/to/deweloperuch-mcp/.venv/bin/deweloperuch-mcp"
    }
  }
}
```

The server reads no environment variables of its own. The limiter lock and the STOP record: `XDG_CACHE_HOME` ([configuration](../configuration.md)).

## Argument rules

- **Numbers:** a JSON integer or a string of digits only (`"10"`, `" 10 "`, with an optional `+`/`-`, up to 18 digits). Rejected: `"10.0"`, a string with other characters, `true`/`false`. (The JSON number `10.0` is accepted as 10.)
- **Optional filters** (e.g. `price_min`, `area_max`, `price_per_m2_min`, `district`, `sort`, `name`, `developer_slug`, `address`): blank text or `null` means "none".
- **With a default value:** `null` means the default: `page`, `per_page`, `limit`, `periods`, `status`, `level`, `granularity`, `include_history`, `price_dropped`, `include_trend`. Blank text is also the default for the choice parameters (`status`, `level`, `sort`, `granularity`); for numbers and booleans it is an error (`include_history: ""`).
- **Fractional numbers** (`lat`, `lng`, `area_m2`): a JSON number or text with a decimal point (`"52.2297"`); a decimal comma and booleans are rejected.
- **Unknown arguments** are rejected (see [Errors](#errors)); the schema has `additionalProperties: false`.
- **Choice values** (`sort`, `status`, ...) are trimmed (`" price_asc "` works).
- Texts (`query`, `city`, `name`, slugs) are validated by the use cases; the error has a Polish message and no request is sent.

## Errors

- **Domain error:** a tool result with `isError=true` and one Polish message that says what to change or that the series stopped. The message contains no paths, prop names or service response content. Technical details (target, status, media type or body fragment, with non-printable characters escaped) go only to the server log on stderr: for a not-found the target, the status and the media type, without the service's text; for a redirect `HTTP 301 -> <Location>` (cut to 300 characters).
- **STOP** (401, 403, 429, Cloudflare challenge): the message starts with `STOP:`, has no domain prefix and ends with a call to stop and report to the user. The texts (for the model; without times, source, paths or how to clear the lock):
  - **the first STOP in the process:** `STOP: HTTP 403 (odmowa dostępu). Klient nie wyśle już żadnego zapytania; inne procesy też zostały wstrzymane. Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.` Analogously `HTTP 401 (brak autoryzacji)` and `HTTP 429 (limit zapytań)`. Cloudflare challenge: `STOP: challenge Cloudflare (captcha/WAF). …` (for a status that is itself a STOP, with the status label, e.g. `STOP: HTTP 403 (odmowa dostępu), challenge Cloudflare (captcha/WAF). …`);
  - **a repeated call in this process:** `STOP: seria zapytań do deweloperuch.pl jest już przerwana; zapytanie nie zostało wysłane. Powód: HTTP 403 (odmowa dostępu). Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.`;
  - **from another process's record (CLI, recon, another server), 401/403/challenge:** `STOP: seria zapytań do deweloperuch.pl jest wstrzymana po wcześniejszym STOP (HTTP 403, odmowa dostępu). Zapytanie nie zostało wysłane. Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.` (for a challenge: `(challenge Cloudflare, captcha/WAF)`);
  - **from a record, 429:** `STOP: seria zapytań do deweloperuch.pl jest wstrzymana po wcześniejszym STOP (HTTP 429, limit zapytań); wstrzymanie trwa jeszcze ok. N s. Zapytanie nie zostało wysłane. Nie ponawiaj w tej sesji; przerwij i zgłoś to użytkownikowi.`;
  - **unreadable record:** `STOP: seria zapytań do deweloperuch.pl jest wstrzymana bezterminowo, bo zapis o wcześniejszym STOP jest nieczytelny. Zapytanie nie zostało wysłane. Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.`

  Details (source, PID, times, limiter pause) go only to the server log on stderr. Other service errors (5xx, network and others) are also without details and say „Nic nie ponawiam; spróbuj później.” (I am retrying nothing; try later).
- **The service changed** (D21; CLI exit code 6): the tool cannot read what the service moved, removed or rebuilt. The message has the domain prefix (e.g. `Inwestycja 'smolna': …`, `Wyszukiwanie ofert w 'warszawa': …`) and two forms:
  - a redirect (3xx), a removed route (a 404 that is not the service's own "unknown" answer), a 410, or a 404 from a route that does not answer 404 for "unknown": `Inwestycja 'smolna': Narzędzie nie może pobrać tych danych, bo serwis przeniósł je w inne miejsce albo przestał je udostępniać. To nie musi znaczyć, że argumenty są błędne ani że szukanego obiektu nie ma. Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.` It carries no HTTP status, because next to a subject a status would read as "this entity is gone";
  - a 2xx whose data does not match the contract, e.g. `Wyszukiwanie ofert w 'warszawa': Na stronie serwisu brakuje oczekiwanych danych. Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.` or `Statystyki rynku w 'sopot': Dane z serwisu nie pasują do kontraktu klienta (inny format). …` with the same ending.

  The ending „Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi.” means: do not repeat this call and tell the user; other tools may still work (the server `instructions` say the same). The arguments may still be right, and the object may exist. "Not found" is only the service's own "unknown" answer: a JSON 404 with an `error`, the 404 flight stream of a statistics page, or Next.js's 404 marker in a 200 of an offer list or the developer page. Known cases: `rank_locations` with `level=powiat` and `get_developer` of a known developer in an unknown city answer so until repaired ([rank_locations](tools/rank_locations.md#data-limitations), [get_developer](tools/get_developer.md#data-limitations)).
- **Unexpected exception:** `Nieoczekiwany błąd serwera MCP deweloperuch (szczegóły są w jego logu). Nie ponawiaj tego wywołania; zgłoś problem użytkownikowi.`
- **Argument validation error** (wrong type, missing argument, value outside `enum`/range): a Polish result with `isError=true`, e.g. `Błędny argument narzędzia search_offers: status musi być jedną z wartości active, archived, all albo pusty, podano "sold". Popraw i ponów; nic nie zostało wysłane.` or `Błędny argument narzędzia search_locations: query: brak wymaganego argumentu. Popraw i ponów; nic nie zostało wysłane.` Nothing was sent to the service. Fix the indicated field according to `inputSchema` and retry.
- **Unknown arguments:** every tool rejects arguments that are not in its schema (`additionalProperties: false`), with an `isError` result that lists the allowed names, e.g. `Nieznany argument narzędzia search_offers: 'max_price'. Dozwolone argumenty: city, price_min, price_max, … Popraw nazwy i ponów; nic nie zostało wysłane.` (several: `Nieznane argumenty narzędzia …: 'a', 'b'. …`). **BREAKING** for clients that relied on unknown arguments being silently ignored (before, a typo such as `max_price` gave a result without the filter and without an error).

Service errors (`Wyszukiwanie ofert w 'warszawa': …`, `Inwestycja 'smolna': …`, `Budynek '<slug>': …`) get domain context; see [configuration, package errors](../configuration.md#package-errors).

### STOP: information for the person configuring the server

The model does not get this part. After STOP no tool sends requests (the server may still return responses that are still fresh in the cache):

- A STOP written by any process (CLI, recon, another MCP server) halts this server while the record is active; a 429 expires after the pause, 401, 403 and a challenge are indefinite ([configuration](../configuration.md#stop-shared-lock-between-processes)).
- A server that returned STOP once (its own or from another process's record) is **latched until restart**: it stays halted also after the record is cleared and after a 429 expires. Restart it after the cause is explained.
- You can check and clear the record only in the CLI: [`deweloperuch stop status`](../cli/commands/stop-status.md), [`deweloperuch stop clear`](../cli/commands/stop-clear.md). There is no MCP tool for clearing the lock.

## Result sizes

Compact JSON in the content (the same as `structuredContent`), from the recorded test cases (`tests/golden/mcp/`; the mocked service replays real captures):

| Call | Characters |
|---|---|
| `search_locations`, 5 items | 682 |
| `search_offers`, 10 (default) | 5 119 |
| `search_offers`, 50 | 23 901 |
| `search_investments`, `city=sopot` | 2 items 1 131; 10 items (default) 5 685; 30 items at most about 23 000 (the schema's estimate of 550-750 per item) |
| `get_investment`, 20 (default) | about 6 400 |
| `get_investment`, 17 offers with `include_history` | 7 952; at the default `limit` 20 up to about 10 000 |
| `get_investment`, 200 | about 58 100; 200 with the history on a 127-offer investment about 58 500 (live, 2026-10-31) |
| `search_developers`, 1 item | 196 |
| `get_developer`, whole country, 20 investments (default) | 8 528 |
| `get_market_statistics`, 5 developers | 1 611 |
| `get_transaction_statistics`, 12 months (default) | 2 502; 60 months 8 939 |
| `rank_locations` | 3 items 550; 5 items 927; 20 items 2 925 |
| `get_building`, 10 units (default) | 2 624 (3 units 1 112) |
| `estimate_property_value`, 50 comparables | 10 597 |
| `get_government_statistics`, 12 periods (default) | at most about 3 000 |
| `get_government_statistics`, 120 periods, widest dataset | 10 577 |

The tool listing (names, titles, descriptions, annotations, input and output schemas of 13 tools) is about 78 000 characters in compact JSON: the output schemas about 47 000, the input schemas about 15 000 and the descriptions about 14 000 (`tests/snapshots/mcp_tools.json`). Lists have `total`/`returned`/`truncated`; results contain no `null` fields, except `total` in `search_locations` and `search_developers` (always present, `null` when only "more than shown" is known) and `estimated_value` in `estimate_property_value`.

## Shutdown

- EOF on stdin: a clean exit, code 0.
- SIGINT: `KeyboardInterrupt` with a traceback on stderr.

## Note for the host (stderr)

The server logs to stderr: INFO for domain errors, and for an unexpected error a rich traceback of about 29 KB. **The host must read or drain the server's stderr**, otherwise the pipe buffer may fill up and the server will hang. The `httpx` logs on stderr contain the URLs of requests to the service (they do not reach the model).

## Data documentation

The data and its limits: [discovery](../discovery/README.md), [endpoints](../discovery/endpoints.md), [pages-rsc](../discovery/pages-rsc.md), [entities](../discovery/entities.md). Open questions: [open-questions](../open-questions.md).

_Source: `src/deweloperuch_mcp/consumers/mcp/server.py`, `src/deweloperuch_mcp/consumers/mcp/tools/`, `src/deweloperuch_mcp/consumers/mcp/presenters/`, `src/deweloperuch_mcp/consumers/mcp/support/`, `tests/snapshots/mcp_tools.json`_
