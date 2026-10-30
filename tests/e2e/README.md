# Live end-to-end tests

This suite runs the installed package against the real deweloperuch.pl: the MCP server over stdio (driven by the official MCP SDK client), the `deweloperuch` CLI and `recon/probe.py`. It is **off by default**: a plain `uv run pytest` skips it.

## Before you run it

- Live runs are opt-in and should be rare. deweloperuch.pl is a community project, and one run sends up to 120 requests. Do not run the suite alongside other live tools such as the recon scripts.
- The suite does not set a private `XDG_CACHE_HOME`, so it uses the limiter and the STOP record of your environment (`${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/`). It shares them with every process that sees the same `XDG_CACHE_HOME`, e.g. an MCP client running the server; a shell with a different value gets a separate limiter.
- An active STOP ends the run before any request. Check it with `deweloperuch stop status`, and lift it only after you have found its cause (see [Configuration](../../docs/configuration.md#stop-shared-lock-between-processes)).

## Running

```sh
DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e -rs --maxfail=3
```

- Both switches are required: the variable and `-m live`. Without either, every test is skipped with the reason „e2e na żywym serwisie…” before any fixture starts, so no process is launched. `tests/safeguards/test_e2e_gate.py` checks this in the default run.
- `--maxfail=3` stops the run after three failures instead of sending more requests.
- The run ends at once, without further requests or retries, when:

  | Exit code | Cause | What to do |
  |---|---|---|
  | 3 | STOP: 401, 403, 429 or a challenge | stop, run `deweloperuch stop status` and find the cause before anything else |
  | 4 | service unavailable: 5xx or a network error | try later |
  | 1 | request budget exceeded, or a broken request counter | check the suite |

  A broken counter means that a call which had to reach the network left no `HTTP Request:` line in the server log. Most often the MCP SDK has changed its logging.
- Logs go to pytest's temporary directory (choose it with `--basetemp`): `mcp*/server-stderr.log` and `cli*/cli-N.log`.

### Request budget

- **Limit:** at most 120 live requests per run (`MAX_REQUESTS` in `tests/support/e2e/live.py`). The plan is 87, about a minute and a half at 1 request per second.
- **Worst case:** 116. Every call meant to be served from the cache goes to the network (29 more requests), and those tests fail anyway, except the two repeats allowed to send 1 request: `get_market_statistics` with filters and the filtered list of `search_investments`.
- **Report:** at the end pytest prints the section „żywe zapytania (e2e)” with the number of requests per call.
- **Counting:** only requests that got a response are counted.
  - The MCP server logs every request (`HTTP Request:`) on stderr, and the suite reads that stream.
  - The CLI runs through its entry point (`deweloperuch_mcp.cli:main`) with the httpx log written to a file.
  - A probe run counts as 1 request unless it exited with code 2 or 5.

### Cache

Each MCP module starts its own server, so repeated requests within a module come from that server's cache, which keeps a response for at most 300 s:

- Freshness is `s-maxage`, else `max-age`, else 300 s, minus Cloudflare's `Age`.
- When `Age` already exceeds the freshness (Cloudflare serving its copy past `max-age`, e.g. the GUS page `polska` with `age: 69574` [P 2026-10-13]), the reply is kept for 300 s.
- `no-store`, `no-cache` or `max-age=0` turn the cache off.

See `_ttl` in `deweloperuch_mcp.api.http.transport`. Most pages and endpoints the tools read send `max-age=28800` without `s-maxage` [P 2026-10-10; [W] for the government statistics page and the developer profile]. During a run (minutes), a repeat of those always comes from the cache, so tests marked "cache" require exactly the stated number of requests. Two repeats are tolerated: `offer-snapshot` (cache headers not checked yet; its predecessor `city-sales` sent `s-maxage=300` [P 2026-10-10]) behind `test_market_with_filters`, and the city's investment list behind `search_investments`, whose `Cache-Control` is unknown. Each may send 1 request.

If a cache test fails, check `Age` and `Cache-Control` of that response. The computed TTL is logged at DEBUG level (`TTL cache …`).

### Reading the results

- **Warnings** (`UserWarning`) are not errors. They flag data that may change between calls, such as the price of an offer or `offers_total` not matching the list.
- **xfail** marks a known problem described in the test's reason, not a failure.
- Assertions check structure, ranges and consistency, never specific numbers. Behaviour marked [W] in the code is confirmed only by a live run.

## What every MCP result is checked for

Every tool call, in every module, is checked for a STOP, an unavailable service and backend details (`leaks` in `tests/support/e2e/live.py`):

- in text and values: `/api/`, `initialData`, `_rsc`, `invest_`, `sale_id`, `/ceny-`, `/statystyki`, `tocItems`, `sortedLocations`, `currentSlug`, `NEXT_HTTP`, `digest`, `Next-Action`, `buildId`, `Traceback`, `File "`, `httpx`, `pydantic.dev`, addresses of the service, HTML;
- in field names: `sale`, `invest` (except `investment`), `rcn`, `amount`, `rsc`.

Values such as developer names or slugs are not checked for backend words, because a real developer may be called e.g. „Invest Komfort”. The SDK checks every result against the tool's output schema.

Links to the service's public pages are the one exception. A full address is allowed only as the whole value of a `*_url` field (`list_url`, `investment_url`, `developer_url`, `stats_url`, `ranking_url`, `building_url`), and only in these shapes [P]:

- `…/ceny-ofertowe/{city}/mieszkania?…`
- `…/ceny-ofertowe/{city}/deweloperzy/{developer}`
- `…/ceny-ofertowe/{city}/deweloperzy/{developer}/{investment}`
- `…/statystyki/statystyki-rzadowe/{location}`, optionally with `#{section}` (an id from the page's table of contents: lowercase letters, digits, hyphens)
- `…/statystyki/ceny-transakcyjne/mieszkania/{city}`
- `…/ceny-transakcyjne/polska/miasta`
- `…/ceny-transakcyjne/{city}/adresy/{building}`

A segment may not contain `/`, `?` or `#`, may not be `.` or `..` and may not contain `%2e`. An address with `_rsc` or `/api/`, in any other field or in an error message is a leak.

## Scenarios

The "Requests" column gives the count when the whole module runs in file order. A fixture counts at the first test that uses it. "Cache" means the repeated part of the call comes from the server's cache. Tags: [P] confirmed by a captured response, [W] inferred, [H] an open hypothesis that the test confirms or refutes. T-numbers refer to `docs/open-questions.md`.

### MCP: `test_live_mcp.py` (74 tests, 48 requests, at most 67)

One `deweloperuch-mcp` process for the module, so repeated requests come from the server's cache. The tests check the pattern of the links:

- list: the city's path, and in the query exactly the tool's arguments, in the order they are sent to the service;
- investment and developer profile: the slugs of the result;
- statistics: the page of the location from the argument and the section of the dataset.

Only two links are opened, through `probe`: `test_the_investment_link_leads_to_its_page` and `test_the_statistics_link_leads_to_its_section`.

| Test | What it checks | Requests |
|---|---|---|
| `test_tools_list_matches_the_snapshot` | 13 tools; names, descriptions, schemas, annotations, `serverInfo` and instructions match `tests/snapshots/mcp_tools.json` | 0 |
| `test_tools_list_has_no_backend_details` | the leak filter on descriptions and schemas | 0 |
| `test_locations_a_city_gives_its_slug` | „Kraków”: `kind=city`, `city_slug` krakow (fixture) | 2 |
| `test_locations_a_district_gives_the_slug_of_its_city` | „mokot”: the district Mokotów, `city_slug` warszawa (fixture; the query of the sample `api.location_search`) | 2 |
| `test_locations_a_street_gives_the_slug_of_its_city` | the same search: the street Mokotów in Warsaw (`kind=street`) | 0 |
| `test_locations_with_polish_letters` ×2 | „Łódź”, „Gdańsk”: a city, an ASCII slug | 4 |
| `test_locations_without_results` | „zzqxv”: 0 results, a hint | 2 |
| `test_locations_a_too_short_query_is_refused_without_a_request` | „a”: `isError` | 0 |
| `test_offers_of_a_city_with_the_defaults` | D4 counters consistent, 10 items, exactly 1 request (fixture) | 1 |
| `test_offers_50_per_page` | `per_page=50`: 50 items (fixture) | 1 |
| `test_offers_50_per_page_fit_their_size_budget` | the result for 50 < 25,000 characters | 0 |
| `test_offers_page_2_has_other_offers` | other `offer_id` values than page 1 | 1 |
| `test_offers_in_a_price_range` | 400–700 thousand: every price in the range (fixture) | 1 |
| `test_offers_in_an_area_range` | 40–60 m²: every area in the range (fixture) | 1 |
| `test_offers_sorted_by_price` ×2 | `price_asc` and `price_desc` | 2 |
| `test_offers_with_filters_and_sort_together` | price, area and order together | 1 |
| `test_offers_in_the_whole_country_name_their_city` | `city=polska`: items have `city` (fixture) | 1 |
| `test_offers_of_an_unknown_city_say_so` | „nie zna miasta”, pointing to `search_locations` and `polska`, never „Serwis mógł się zmienić” | 1 |
| `test_offers_page_past_the_last_one` | [W] `sopot` (few offers, T12), then a page past the last one: an empty page with a hint; „nie zna miasta” is an xfail (T34) | 2 |
| `test_offers_price_min_above_price_max_is_refused_without_a_request` | `isError` | 0 |
| `test_offers_arguments_off_the_schema_are_refused_without_a_request` ×3 | `per_page=100`, `page=21`, `sort="rooms_asc"`: an error in Polish naming the field and what it allows, without a link to pydantic.dev | 0 |
| `test_offers_numbers_as_text_are_the_same_request` | „10” and „1” as text | 0 (cache) |
| `test_offers_filter_numbers_as_text_are_the_same_request` ×2 | `price_min="400000"`, `area_min="40"` | 0 (cache) |
| `test_offers_empty_or_null_optional_arguments_are_the_defaults` ×3 | `price_min=None`, `sort=""`, `sort=None` | 0 (cache) |
| `test_offers_result_of_10_fits_the_size_budget` | the result for 10 < 8000 characters | 0 |
| `test_offers_city_that_is_not_a_slug_is_refused_without_a_request` ×4 | „Kraków”, „Warszawa”, „KRAKOW”, „”: `isError` pointing to `search_locations` | 0 |
| `test_offers_city_with_spaces_around_is_trimmed` | „ krakow ”: the same request as the first page | 0 (cache) |
| `test_offers_district_slug_as_city_is_an_unknown_city` | [W] „mokotow” as a city: „nie zna miasta” | 1 |
| `test_investment_with_the_default_limit` | limit 20, consistent counters (fixture) | 1 |
| `test_investment_limit_0_is_the_summary` | the summary only | 0 (cache) |
| `test_investment_with_history` | `include_history`, `limit=2`: every offer has a history | 1 (investment from the cache) |
| `test_investment_lists_the_offer_found_by_search` | the offer from the search is on the list (`limit=200`) | 0 (cache) |
| `test_the_investment_link_leads_to_its_page` | `probe page <path of investment_url> --prop investments`: code 0, the page contains this investment | 1 (probe) |
| `test_investment_unknown` | „Nie znaleziono inwestycji” | 1 |
| `test_offer_with_its_price_history` | a non-empty `price_history`, known `kind` values; a price other than in the search gives a warning | 1 (investment from the cache) |
| `test_offer_outside_its_investment` | an `offer_id` outside the investment: `isError` | 0 (cache) |
| `test_offer_of_an_unknown_investment` | `isError` | 1 |
| `test_offer_from_another_city_found_in_the_whole_country` | an offer from `city=polska` in another city, then `get_investment` and `get_offer` | 2 (investment from the cache) |
| `test_government_average_area_of_poland` | `polska` + `average_area`: D4 counters, yearly periods ascending, 30–150 m², `stats_url` with `#gus-srednia-powierzchnia` (fixture) | 1 |
| `test_government_nbp_prices_of_a_city` | `warszawa` + `nbp_prices`: 4 NBP series in PLN/m², quarters, `#nbp` (fixture) | 1 |
| `test_government_average_area_of_an_aggregate` | [H] `7-miast` + `average_area`: an aggregate's page. Its `currentSlug` is unconfirmed, and a mismatch would turn every aggregate into a "service changed" error, so the failure quotes the server log line with `currentSlug` | 1 |
| `test_government_another_dataset_of_the_same_location_comes_from_the_cache` | `polska` + `unemployment`: the same page, a rate of 0–40% | 0 (cache) |
| `test_government_nbp_prices_of_poland_point_to_cities` | `polska` + `nbp_prices`: `isError` with the list of locations that have NBP prices [P 2026-10-11] | 0 (cache) |
| `test_government_dwellings_fit_the_size_budget` | `polska` + `dwellings_quarterly` (15 series, 12 periods) < 8000 characters | 0 (cache) |
| `test_government_unknown_location` | [H] an unknown location: „nie ma statystyk rządowych”, i.e. Next.js's 404 marker; „Serwis mógł się zmienić” (no marker) is an xfail whose reason records the finding | 1 |
| `test_government_location_that_is_not_a_slug_is_refused_without_a_request` ×3 | „Kraków”, „kraków”, „”: `isError` saying what to give (capitals alone are lowercased, so „Warszawa” would be a valid location) | 0 |
| `test_the_statistics_link_leads_to_its_section` | `probe page <path of stats_url without the anchor> --prop tocItems --full` (untrimmed): code 0, the table of contents contains the section of the anchor | 1 (probe) |
| `test_two_calls_at_once_go_one_by_one_through_the_limiter` | two calls at once: both correct, requests in the log ≥ 0.9 s apart | 2 |
| `test_offers_unknown_argument_is_refused_without_a_request` | `max_price`: `isError` naming the argument and the allowed ones (`price_max`) | 0 |
| `test_offers_in_a_district_cheaper_than_their_first_price` | [P 2026-10-10] `district` „Mokotów” (from the `mokot` search) and `price_dropped`: the query in `list_url`, every `price_change_since_start_pct` < 0, `total` ≤ the district's `offer_count` | 1 |
| `test_offers_archived` | [P] `status=archived`: every item archived | 1 |
| `test_offers_in_a_price_per_m2_range_by_price_per_m2_descending` | [W] `price_per_m2_min`/`max` 12,000–16,000 and `price_per_m2_desc`: every `price_per_m2` in the range (±1 PLN), `total` below the first page's, the order descending; a failure quotes the finding | 1 |
| `test_offers_by_area_descending` | [W] `area_desc`: areas descending | 1 |
| `test_offer_price_flags_agree_with_its_history` | `price_flags` of the offer from the search: the lowest prices are prices from its history, 90 days ≤ 30 days, the change count fits the history | 0 (cache) |
| `test_market_of_a_city` | `get_market_statistics` of Kraków (fixture): counts, spreads in order, plausible medians, the top developers in order with their links, `list_url`, no single offers, < 8000 characters; a total more than 2% off `search_offers` is a warning | 1 |
| `test_market_with_filters` | `price_max=700000`, `area_min=40`: fewer offers, spreads within the filters, `list_url` with them | 0 (cache; 1 if the TTL of `offer-snapshot` ran out) |
| `test_market_of_the_whole_country_is_refused_without_a_request` | `city=polska`: `isError` „tylko dla jednego miasta” | 0 |
| `test_market_of_an_unknown_city` | [H] an unknown city: „Serwis nie zna miasta” (400/404) or an empty summary with a hint; anything else is an xfail whose reason records the finding | 1 |
| `test_developer_of_the_whole_country` | `get_developer` of the first offer's developer (`city` defaults to `polska`): counters, investments by active offers, links, < 15,000 characters | 1 |
| `test_developer_in_a_city` | the same developer, `city=krakow`, `limit=100`: only investments in Kraków; the offer's investment missing is a warning | 1 |
| `test_developer_unknown` | [P 2026-10-13] „Nie znaleziono dewelopera” (the page's heading), not „Serwis mógł się zmienić” | 1 |
| `test_developer_in_an_unknown_city` | [H] a known developer in an unknown city: „Nie znaleziono dewelopera” or a profile without investments with a hint; anything else is an xfail whose reason records the finding | 1 |

### CLI: `test_live_cli.py` (13 tests, 13 requests)

Each command is a separate process, without a shared cache. Exit code 3 or „Błąd: STOP:” ends the run with code 3; exit code 4 (a service error) ends it with code 4.

| Test | What it checks | Requests |
|---|---|---|
| `test_locations_search_as_text` | `locations search Kraków`: text, the line „miasto … Kraków [krakow]” | 2 |
| `test_locations_search_as_json` | `locations search Gdańsk --json` | 2 |
| `test_offers_search_with_filters_as_json` | `offers search krakow` with filters, `--json`: ranges and order (fixture) | 1 |
| `test_offers_search_with_filters_as_text` | the same as text | 1 |
| `test_offers_get` | `offers get <id> --investment <slug>`: the price history | 2 |
| `test_investments_get_with_a_limit` | `investments get <slug> --limit 2` | 1 |
| `test_offers_search_of_an_unknown_city` | exit code 7, a message with `search_locations` and `polska`, `Szczegóły:` without HTML | 1 |
| `test_stats_government_as_text` | `stats government warszawa unemployment`: the header, a link to `#gus-bezrobocie`, a table of 12 months | 1 |
| `test_offers_search_with_a_wrong_page_size_sends_nothing` | `--per-page 7`: exit code 2 | 0 |
| `test_stop_status_is_offline` | `stop status`: exit code 0 | 0 |
| `test_the_installed_script_runs_offline` | the installed script `deweloperuch stop status`: exit code 0 | 0 |
| `test_stats_market_as_text` | `stats market sopot`: the header, the link to the list, the table of spreads, the largest developers | 1 |
| `test_developers_get_in_a_city_as_json` | `developers get <developer of the first offer> --city krakow --json`: investments in Kraków only, the profile link | 1 |

### Recon: `test_live_recon.py` (2 tests, 2 requests)

| Test | What it checks | Requests |
|---|---|---|
| `test_probe_api` | `probe.py api "/api/cities?q=krak"`: exit code 0, JSON with krakow | 1 |
| `test_probe_page_lists_the_data_props` | `probe.py page "/ceny-ofertowe/warszawa/mieszkania?perPage=10"` without `--prop`: the list of props contains `initialData` | 1 |

The bundle scanner (`recon/scan_bundles.py`, about 140 requests) is not part of the suite.

### Other tools: one module each

Each module starts its own `deweloperuch-mcp` (with its own cache); the CLI runs are separate processes. "Plan / at most" counts the module's requests in file order.

| Module | Tool, command | Tests | Plan / at most | What it checks |
|---|---|---|---|---|
| `test_live_developer_search.py` | `search_developers`, `developers search` | 8 | 4 / 8 | a known developer (slug, profile link for `polska`), the repeat from the cache, the largest limit (20), nothing found with a hint, 3 refusals without a request, the CLI with `--json` |
| `test_live_investment_search.py` | `search_investments` | 4 | 3 / 4 | the investments of Sopot ordered by active offers, the same list filtered and ordered (cache, at most 1), a search by name honouring its limit and `total` [W], the match's active offers equal to those of `get_investment` [W] |
| `test_live_transactions.py` | `get_transaction_statistics`, `stats transactions` | 6 | 3 / 5 | months of Warsaw, more months from the cache, fewer transactions in the latest months (the RCN reporting lag), the incomplete months are the newest ones and end at `last_complete_period` (cache), quarters, the CLI for another city; every result: `incomplete` only on trailing periods |
| `test_live_rankings.py` | `rank_locations`, `stats cities` | 6 | 3 / 6 | cities by transactions, by price from the cache (the most expensive with `min_transactions=50`, the cheapest with the default threshold of 20), powiats, the cheapest powiats from the cache, the CLI as text |
| `test_live_buildings.py` | `get_building`, `buildings get` | 6 | 6 / 6 | the building of the sample with its units, transactions and trend (2), the repeat from the cache, the CLI with `--json`, `cisna` with its trend (2): no average of 0, the counts of the transactions that are no regular sale match the listed ones, a trend without quarters has no radius and a hint, [H] an unknown slug (last, since a 5xx ends the run) |
| `test_live_valuation.py` | `estimate_property_value`, `valuation estimate` | 5 | 5 / 5 | `search_locations` for a street's coordinates (2), a valuation there, a valuation in Cisna (fewer than 5 transactions: `low_confidence` and the caveat in `hint`, only warned about when no longer so), a point outside Poland refused without a request, the CLI with `--json` at the sample's point; every valuation: `low_confidence` true exactly below 5 transactions |

**In total:** 125 tests, a plan of 87 live requests, at most 116, a hard limit of 120.
