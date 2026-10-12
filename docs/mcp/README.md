# MCP server `deweloperuch-mcp`

An MCP server (SDK `mcp`, `MCPServer`) with data on developers' asking prices for apartments (primary market) from deweloperuch.pl. Read-only. `serverInfo.name` is `deweloperuch`, `version` is the package version.

**Transport: stdio only** (provisional, to be confirmed by the user). The server has no options other than `-h/--help`; an MCP client starts it and talks to it over stdin/stdout. Everything else (logs) goes to stderr.

Tool descriptions, schema field descriptions, `instructions` and error messages are product texts in Polish and are quoted verbatim in this documentation, with short English summaries.

## Tools

| Tool | Purpose |
|---|---|
| [`search_locations`](tools/search_locations.md) | Turns the name of a city, district or street into a `city_slug`. |
| [`search_offers`](tools/search_offers.md) | A page of offers in a city (or the whole of Poland) with price and area filters. |
| [`get_offer`](tools/get_offer.md) | One offer with its full price history. |
| [`get_investment`](tools/get_investment.md) | An investment with its developer and a list of offers. |

All four have the annotations `readOnlyHint=true` and `openWorldHint=true`. Typical order: `search_locations` → `search_offers` → `get_investment` or `get_offer`.

## Server instructions (`instructions`)

> Dane z deweloperuch.pl: ceny ofertowe mieszkań od deweloperów (rynek pierwotny) w Polsce, z historią zmian cen. Typowa kolejność: search_locations (nazwa miejsca -> city_slug), search_offers (oferty w mieście z filtrami ceny i metrażu), potem get_investment (oferty jednej inwestycji) albo get_offer (jedna oferta z historią ceny). Serwis jest projektem społecznym: pytaj oszczędnie i zawężaj filtry zamiast przeglądać kolejne strony. Gdy błąd narzędzia zawiera STOP, przestań używać tych narzędzi, niczego nie ponawiaj, nie szukaj obejścia i powiedz o tym użytkownikowi, podając powód z komunikatu. Dalsze kroki należą do użytkownika; sam niczego nie odblokowuj ani nie uruchamiaj ponownie. Błędy walidacji argumentów bywają po angielsku: popraw wskazane pole zgodnie ze schematem i ponów. Pola kończące się na _url to linki do stron deweloperuch.pl: podawaj je użytkownikowi, np. w tabeli ofert.

Summary: asking prices of developers' apartments (primary market) in Poland with price-change history; the typical tool order; the service is a community project, so ask sparingly and narrow filters instead of paging; on a STOP error stop using the tools, retry nothing, look for no workaround, report the reason to the user and unblock or restart nothing yourself; validation errors may be in English, so fix the field and retry; fields ending in `_url` are links to deweloperuch.pl pages to be shown to the user.

### Links to service pages

The results of `search_offers` (`list_url`, `investment_url` in items), `get_offer` and `get_investment` (`investment_url`, `developer_url`) contain addresses of public pages for humans (D12 in [decisions.md](../decisions.md)):

- only `*_url` fields and only three page patterns confirmed [P]: the offer list (with the same filters, sorting and page), the developer profile, the investment;
- without `_rsc` and `/api/`; no link to a single offer (its page is not confirmed);
- a missing slug means no link (the field is omitted); the `offers` items in `get_investment` have no links;
- error messages contain no addresses.

## MCP client configuration

After `uv sync` (see the [README](../../README.md#quickstart)) the script is at `.venv/bin/deweloperuch-mcp`. An example entry in the client configuration (`mcpServers` format, e.g. Claude Desktop, Claude Code `.mcp.json`):

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
- **Optional** (`price_min`, `price_max`, `area_min`, `area_max`, `sort`): `""` or `null` means "none".
- **With a default value:** `null` means the default: `page` (1), `per_page` (10), `limit` (20), `include_history` (`false`). `include_history: ""` is an error.
- **`sort`** is trimmed (`" price_asc "` works).
- Texts (`query`, `city`, slugs) are validated by the services; the error has a Polish message.

## Errors

- **Domain error:** a tool result with `isError=true` and one Polish message that says what to change or that the series stopped. The message contains no paths, prop names or service response content. Technical details (target, status, body fragment, with non-printable characters escaped) go only to the server log on stderr.
- **STOP** (401, 403, 429, Cloudflare challenge): the message starts with `STOP:`, has no domain prefix and ends with a call to stop and report to the user. The texts (for the model; without times, source, paths or how to clear the lock):
  - **the first STOP in the process:** `STOP: HTTP 403 (odmowa dostępu). Klient nie wyśle już żadnego zapytania; inne procesy też zostały wstrzymane. Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.` Analogously `HTTP 401 (brak autoryzacji)` and `HTTP 429 (limit zapytań)`. Cloudflare challenge: `STOP: challenge Cloudflare (captcha/WAF). …` (for a status that is itself a STOP, with the status label, e.g. `STOP: HTTP 403 (odmowa dostępu), challenge Cloudflare (captcha/WAF). …`);
  - **a repeated call in this process:** `STOP: seria zapytań do deweloperuch.pl jest już przerwana; zapytanie nie zostało wysłane. Powód: HTTP 403 (odmowa dostępu). Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.`;
  - **from another process's record (CLI, recon, another server), 401/403/challenge:** `STOP: seria zapytań do deweloperuch.pl jest wstrzymana po wcześniejszym STOP (HTTP 403, odmowa dostępu). Zapytanie nie zostało wysłane. Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.` (for a challenge: `(challenge Cloudflare, captcha/WAF)`);
  - **from a record, 429:** `STOP: seria zapytań do deweloperuch.pl jest wstrzymana po wcześniejszym STOP (HTTP 429, limit zapytań); wstrzymanie trwa jeszcze ok. N s. Zapytanie nie zostało wysłane. Nie ponawiaj w tej sesji; przerwij i zgłoś to użytkownikowi.`;
  - **unreadable record:** `STOP: seria zapytań do deweloperuch.pl jest wstrzymana bezterminowo, bo zapis o wcześniejszym STOP jest nieczytelny. Zapytanie nie zostało wysłane. Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.`

  Details (source, PID, times, limiter pause) go only to the server log on stderr. Other service errors (5xx, network and others) are also without details and say „Nic nie ponawiam; spróbuj później.” (I am retrying nothing; try later).
- **Unexpected exception:** `Nieoczekiwany błąd serwera MCP deweloperuch (szczegóły są w jego logu). Nie ponawiaj tego wywołania; zgłoś problem użytkownikowi.`
- **Schema validation error** (wrong type, missing field, value outside `enum`/range): generated by the SDK, in English, with the prefix `Error executing tool …`. Fix the indicated field according to `inputSchema` and retry. The server removes the line with the pydantic documentation link from the SDK message; the field, rule and value stay.
- **Known limitation, unknown arguments:** the MCP SDK silently ignores arguments that are not in the schema (a typo `max_price` instead of `price_max` gives a result without the filter and without an error). Use exactly the names from `inputSchema`. The decision on a fix awaits the user.

Service errors (`Wyszukiwanie ofert w 'warszawa': …`, `Inwestycja 'smolna': …`) get domain context; see [configuration, package errors](../configuration.md#package-errors).

### STOP: information for the person configuring the server

The model does not get this part. After STOP no tool sends requests (the server may still return responses that are still fresh in the cache):

- A STOP written by any process (CLI, recon, another MCP server) halts this server while the record is active; a 429 expires after the pause, 401, 403 and a challenge are indefinite ([configuration](../configuration.md#stop-shared-lock-between-processes)).
- A server that returned STOP once (its own or from another process's record) is **latched until restart**: it stays halted also after the record is cleared and after a 429 expires. Restart it after the cause is explained.
- You can check and clear the record only in the CLI: [`deweloperuch stop status`](../cli/commands/stop-status.md), [`deweloperuch stop clear`](../cli/commands/stop-clear.md). There is no MCP tool for clearing the lock, and for agents in Claude Code the Bash hook blocks this command.

## Result sizes

Compact JSON in the content (the same as `structuredContent`), full pages from samples:

| Call | Characters |
|---|---|
| `search_locations` | 682 |
| `search_offers`, 10 (default) | 4 487 |
| `search_offers`, 50 | 21 222 |
| `search_offers`, 50, `city=polska` | 23 270 |
| `get_investment`, 20 (default) | 6 415 |
| `get_investment`, 200 | 58 135 |

The whole `tools/list` is about 19.2k characters. Lists have `total`/`returned`/`truncated`; results contain no `null` fields, except `total` in `search_locations` (always present, `null` when truncated).

## Shutdown

- EOF on stdin: a clean exit, code 0.
- SIGINT: `KeyboardInterrupt` with a traceback on stderr.

## Note for the host (stderr)

The server logs to stderr: INFO for domain errors, and for an unexpected error a rich traceback of about 29 KB. **The host must read or drain the server's stderr**, otherwise the pipe buffer may fill up and the server will hang. The `httpx` logs on stderr contain the URLs of requests to the service (they do not reach the model).

## Recon documentation

The data and its limits: [discovery](../discovery/README.md), [endpoints](../discovery/endpoints.md), [pages-rsc](../discovery/pages-rsc.md), [entities](../discovery/entities.md). Open questions: [open-questions](../open-questions.md).

_Source: `src/deweloperuch_mcp/mcp_server.py`, `src/deweloperuch_mcp/mcp_results.py`, `tests/snapshots/mcp_tools.json`_
