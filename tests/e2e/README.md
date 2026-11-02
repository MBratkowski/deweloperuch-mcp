# Live end-to-end tests

This suite runs the installed package against the real deweloperuch.pl: the MCP server over stdio (driven by the official MCP SDK client), the `deweloperuch` CLI and `recon/probe.py`. It is **off by default**: a plain `uv run pytest` skips it.

## Before you run it

- Live runs are opt-in and should be rare. deweloperuch.pl is a community project, and one run sends up to 170 requests. Do not run the suite alongside other live tools such as the recon scripts.
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

- **Limit:** at most 170 live requests per run (`MAX_REQUESTS` in `tests/support/e2e/live.py`; raised from 140 on 2026-11-02, user's decision, for the integration routes of 0.2.0). The plan is 114, about two minutes at 1 request per second.
- **Worst case:** 157. Every call meant to be served from the cache goes to the network (43 more requests), and those tests fail anyway, except the two repeats allowed to send 1 request: `get_market_statistics` with filters and the filtered list of `search_investments`.
- **Report:** at the end pytest prints the section „żywe zapytania (e2e)” with the number of requests per call.
- **Counting:** only requests that got a response are counted.
  - The MCP server logs every request (`HTTP Request:`) on stderr, and the suite reads that stream.
  - The CLI runs through its entry point (`deweloperuch_mcp.cli:main`) with the httpx log written to a file.
  - A probe run counts as 1 request unless it exited with code 2 or 5.

### Cache

Each MCP module starts its own server, so repeated requests within a module come from that server's cache, which keeps a response for at most 300 s, or at most 24 h on the nine dictionary and index routes of D19 (`allowlist.LONG_CACHE_PATHS`: `cities`, `city-lookup`, `city-districts`, `investments`, `developers`, `map/tx-cities`, `avg-price-trend/city/{citySlug}`, `statystyki/powiat-map-stats`, `statystyki/gov-map-stats`):

- Freshness is `s-maxage`, else `max-age`, else 300 s, minus Cloudflare's `Age`.
- When `Age` already exceeds the freshness (Cloudflare serving its copy past `max-age`, e.g. the GUS page `polska` with `age: 69574` [P 2026-10-13]), the reply is kept for 300 s; on the D19 routes for the freshness itself, at most 24 h (`powiat-map-stats` with `age` 112,792 at `s-maxage=86400` [P 2026-11-01] is kept 24 h).
- `no-store`, `no-cache` or `max-age=0` turn the cache off.

See `_ttl` in `deweloperuch_mcp.api.http.transport`. The 2.0 pages the tools read send `private, max-age=172800, must-revalidate` [P 2026-10-31] and the JSON endpoints `max-age=28800` with an `s-maxage` of 300 to 86,400 s, depending on the endpoint [P 2026-10-30] (docs/discovery/endpoints.md). During a run (minutes), a repeat of those comes from the cache unless the first reply's `Age` was just under its freshness, so tests marked "cache" require exactly the stated number of requests. Two repeats are tolerated: `offer-snapshot` (`s-maxage=3600` [P 2026-10-31]; an `Age` just under it leaves seconds of TTL) behind `test_market_with_filters`, and the city's investment list behind `search_investments`, whose `Cache-Control` is unknown. Each may send 1 request.

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
- `…/ceny-ofertowe/{city}/{district}/mieszkania?…` (the list of a district, since 2026-10-31; the district a slug of `[a-z0-9]` words joined by single hyphens)
- `…/ceny-ofertowe/{city}/deweloperzy/{developer}`
- `…/ceny-ofertowe/{city}/deweloperzy/{developer}/{investment}`
- `…/statystyki/{location}/dane-rzadowe`, optionally with `#{section}` (an id of a section of the page: lowercase letters, digits, hyphens)
- `…/statystyki/{city}/transakcje`
- `…/ceny-transakcyjne/polska/miasta`
- `…/ceny-transakcyjne/{city}/adresy/{building}`

A segment may not contain `/`, `?` or `#`, may not be `.` or `..` and may not contain `%2e`. An address with `_rsc` or `/api/`, in any other field or in an error message is a leak.

## Scenarios

The "Requests" column gives the count when the whole module runs in file order. A fixture counts at the first test that uses it. "Cache" means the repeated part of the call comes from the server's cache. Tags: [P] confirmed by a captured response, [W] inferred, [H] an open hypothesis that the test confirms or refutes. T-numbers refer to `docs/open-questions.md`.

### MCP: `test_live_mcp.py` (97 tests, 65 requests, at most 94)

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
| `test_offers_50_per_page` | [W] `per_page=50` on 2.0 (T29): 50 items (fixture) | 1 |
| `test_offers_50_per_page_fit_their_size_budget` | the result for 50 < 25,000 characters | 0 |
| `test_offers_page_2_has_other_offers` | other `offer_id` values than page 1 | 1 |
| `test_offers_in_a_price_range` | 400–700 thousand: every price in the range (fixture) | 1 |
| `test_offers_in_an_area_range` | 40–60 m²: every area in the range (fixture) | 1 |
| `test_offers_sorted_by_price` ×2 | `price_asc` and `price_desc` | 2 |
| `test_offers_with_filters_and_sort_together` | price, area and order together | 1 |
| `test_offers_of_the_whole_country_are_refused_without_a_request` | [P 2026-10-29] `city=polska`: `isError` „city=polska nie działa”, pointing to `search_locations` | 0 |
| `test_offers_of_an_unknown_city_say_so` | [P 2026-11-02] the list's 404 marker, then one lookup of the place (`city-lookup`, transactions dictionary: both fields null): „Nie znaleziono miejscowości o city_slug …” pointing to `search_locations`, without `polska`, never „Serwis mógł się zmienić” | 2 |
| `test_offers_page_past_the_last_one` | [P 2026-10-31] `sopot` (few offers, T12), then a page past the last one: „nie ma strony N tej listy albo nie zna miasta”, pointing to `page=1` (T34); an empty page with a hint would also pass | 2 |
| `test_offers_price_min_above_price_max_is_refused_without_a_request` | `isError` | 0 |
| `test_offers_arguments_off_the_schema_are_refused_without_a_request` ×3 | `per_page=100`, `page=21`, `sort="rooms_asc"`: an error in Polish naming the field and what it allows, without a link to pydantic.dev | 0 |
| `test_offers_numbers_as_text_are_the_same_request` | „10” and „1” as text | 0 (cache) |
| `test_offers_filter_numbers_as_text_are_the_same_request` ×2 | `price_min="400000"`, `area_min="40"` | 0 (cache) |
| `test_offers_empty_or_null_optional_arguments_are_the_defaults` ×3 | `price_min=None`, `sort=""`, `sort=None` | 0 (cache) |
| `test_offers_result_of_10_fits_the_size_budget` | the result for 10 < 8000 characters | 0 |
| `test_offers_city_that_is_not_a_slug_is_refused_without_a_request` ×4 | „Kraków”, „Warszawa”, „KRAKOW”, „”: `isError` pointing to `search_locations` | 0 |
| `test_offers_city_with_spaces_around_is_trimmed` | „ krakow ”: the same request as the first page | 0 (cache) |
| `test_offers_district_slug_as_city_is_an_unknown_city` | [W] „mokotow” as a city: „Nie znaleziono miejscowości” after the place lookup [P 2026-11-02] | 2 |
| `test_investment_with_the_default_limit` | limit 20, consistent counters (fixture) | 1 |
| `test_investment_limit_0_is_the_summary` | the summary only | 0 (cache) |
| `test_investment_with_history` | `include_history`, `limit=2`: every offer has a history, oldest first, from the price minus its change since the start to the current price, ending with a price (active) or the withdrawal (archived) [P 2026-10-30] | 0 (cache: the histories come in the investment's answer) |
| `test_investment_history_agrees_with_the_offer_history` | every offer's history (`include_history`, `limit=200`, from the cache); of the offers other than the search's, the one with the most kinds of events (a return first, then a withdrawal): `get_offer` gives the same events, the shorter list being the start of the longer one (a different length is a warning); checks the event types the investment's answer gives by position (D21) | 1 (both investments from the cache) |
| `test_investment_lists_the_offer_found_by_search` | the offer from the search is on the list (`limit=200`) | 0 (cache) |
| `test_the_investment_link_leads_to_its_page` | `probe page <path of investment_url> --prop investments`: code 0, the page contains this investment | 1 (probe) |
| `test_investment_unknown` | „Nie znaleziono inwestycji” | 1 |
| `test_offer_with_its_price_history` | a non-empty `price_history`, known `kind` values; a price other than in the search gives a warning | 1 (investment from the cache) |
| `test_offer_outside_its_investment` | an `offer_id` outside the investment: `isError` | 0 (cache) |
| `test_offer_of_an_unknown_investment` | `isError` | 1 |
| `test_government_average_area_of_poland` | `polska` + `average_area`: D4 counters, yearly periods ascending, 30–150 m², `stats_url` with `#gus-srednia-powierzchnia` (fixture) | 1 |
| `test_government_nbp_prices_of_a_city` | `warszawa` + `nbp_prices`: 4 NBP series in PLN/m², quarters, `#nbp` (fixture) | 1 |
| `test_government_average_area_of_an_aggregate` | [P 2026-10-31] `7-miast` + `average_area`: an aggregate's page (its `citySlug` is the aggregate's): D4 counters, years, 30–150 m², `#gus-srednia-powierzchnia`, the page's name (fixture) | 1 |
| `test_government_an_aggregate_has_no_wages_nor_a_rate_of_its_own` ×2 | [P 2026-10-31] `7-miast` + `wages`, `unemployment`: `isError` „nie publikuje” pointing to `polska`, never „Serwis mógł się zmienić” | 0 (cache) |
| `test_government_another_dataset_of_the_same_location_comes_from_the_cache` | `polska` + `unemployment`: the same page, a rate of 0–40% | 0 (cache) |
| `test_government_nbp_prices_of_poland_point_to_cities` | `polska` + `nbp_prices`: `isError` naming the aggregates and big cities with NBP prices [P 2026-10-31] | 0 (cache) |
| `test_government_demography_of_poland_comes_from_eurostat` | [P 2026-10-31] `polska` + `demography`: months, source Eurostat, `#eurostat-demografia` | 0 (cache) |
| `test_government_dwellings_fit_the_size_budget` | `polska` + `dwellings_quarterly` (15 series, 12 periods) < 8000 characters | 0 (cache) |
| `test_government_unknown_location` | [P 2026-10-31] an unknown location, a 404 `text/x-component`: „nie ma statystyk rządowych” with `polska` and `7-miast`, never „Serwis mógł się zmienić” (that would mean the adapter's 404 opt-in is not wired) | 1 |
| `test_government_a_small_city_has_the_page_of_a_city` ×3 | [W] `sopot`, one page (fixture, `average_area`), then `wages` and `dwellings_quarterly` from the cache: the data with the section of `warszawa`, or „nie publikuje” (a warning, a finding for T74), never „Serwis mógł się zmienić” | 1, then 0 (cache) |
| `test_government_nbp_prices_of_a_city_without_them` | [W] `sopot` + `nbp_prices`: „NBP nie publikuje cen mieszkań” with the aggregates and big cities; NBP prices of `sopot` are an xfail whose reason records the finding | 0 (cache) |
| `test_government_wages_of_a_city_have_their_ratio_to_the_country` | [P 2026-10-31] `warszawa` + `wages`: `relative_to_poland` (read from the notes of the chart) present, 50–400 %; its absence quotes the WARNING of the server log | 0 (cache) |
| `test_government_nbp_prices_of_another_aggregate` | [W] `10-miast` + `nbp_prices`: the page of an aggregate other than `7-miast`, 4 NBP series, `#nbp` | 1 |
| `test_government_a_city_whose_slug_has_a_hyphen` | [W] `jastrzebie-zdroj` (`jastrzebie` on 1.0) + `population`: the slug the 2.0 pages link, `#gus-wiek`, the page's name | 1 |
| `test_government_nbp_prices_of_a_city_outside_the_grid` | [W] `lodz` + `nbp_prices`: NBP prices of a city outside the grid of six on the page of `polska` (its text names the price of `lodz`); none is a failure recording the finding | 1 |
| `test_government_location_that_is_not_a_slug_is_refused_without_a_request` ×3 | „Kraków”, „kraków”, „”: `isError` saying what to give (capitals alone are lowercased, so „Warszawa” would be a valid location) | 0 |
| `test_the_statistics_link_leads_to_its_section` | `probe page <path of stats_url without the anchor> --prop govSections --full` (untrimmed): code 0, the page's section ids contain the section of the anchor | 1 (probe) |
| `test_two_calls_at_once_go_one_by_one_through_the_limiter` | two calls at once (Kraków page 3, Warszawa page 2): both correct, requests in the log ≥ 0.9 s apart | 2 |
| `test_offers_unknown_argument_is_refused_without_a_request` | `max_price`: `isError` naming the argument and the allowed ones (`price_max`) | 0 |
| `test_offers_in_a_district_cheaper_than_their_first_price` | [P 2026-10-31] the list of the district „Mokotów” (the name from the `mokot` search, [W] its slug `mokotow`) and [W] `price_dropped` on it (T73): the district's path and the query in `list_url`, every item's `district` „Mokotów” (as on every district list below), every `price_change_since_start_pct` < 0, `total` ≤ the district's `offer_count` | 1 |
| `test_offers_archived` | [P 2026-10-31] `status=archived`: every item archived ([W] on 2.0) | 1 |
| `test_offers_in_a_price_per_m2_range_by_price_per_m2_descending` | [P 2026-10-31] `price_per_m2_min`/`max` 12,000–16,000 and [W] `price_per_m2_desc`: every `price_per_m2` in the range (±1 PLN), `total` below the first page's, the order descending; a failure quotes the finding | 1 |
| `test_offers_by_area_descending` | [W] `area_desc`: areas descending | 1 |
| `test_offers_in_a_district_of_two_words_with_polish_letters` | [W] „Praga-Południe” as `district`: the list at `praga-poludnie`, offers found | 1 |
| `test_offers_in_a_district_within_ranges_cheapest_first_on_page_2` | [W] T73: Mokotów with 600–1200 thousand, `area_min=40`, `price_per_m2_max=30000`, `price_asc` and `page=2`: every price in the range and ascending, every area ≥ 40, every price per m² ≤ 30,000 (±1 PLN), `total` ≤ the district's `offer_count` | 1 |
| `test_offers_archived_in_a_district_by_area_descending_50_per_page` | [W] T73: Mokotów with `status=archived`, `area_desc` and `per_page=50`: every item archived, areas descending | 1 |
| `test_offers_in_an_unknown_district_say_so` | [P 2026-10-31] an unknown district: „nie zna dzielnicy”, never „Serwis mógł się zmienić”; [P 2026-11-01] the city's districts (`city-districts`) read once and listed after „Znane dzielnice tego miasta” (up to 25, without their counts), each one of the 18 of `tests/fixtures/api/city_districts_warszawa_20261102.json` | 2 |
| `test_offers_with_ranges_open_above_keep_their_starts` | [W] T33: `price_min`, `area_min`, `price_per_m2_min` only (the sentinels in the query): offers found, each from every start (±1 PLN/m²) | 1 |
| `test_offers_in_the_other_orders` ×3 | [W] `price_per_m2_asc` (±1 PLN), `area_asc` on `page=20` (the last page served [P 2026-10-31]: a full page of 10, `pages_available` 20), `biggest_drop`: ascending by their values | 3 |
| `test_offers_without_a_match_are_an_empty_list` | [W] `price_min=99000000`: no error, `total` 0, no items, the hint „Brak ofert spełniających kryteria.” | 1 |
| `test_offers_active_and_archived_together` | [W] T72: `status=all`: every item active or archived, `total` ≥ the first page's | 1 |
| `test_offer_price_flags_agree_with_its_history` | `price_flags` of the offer from the search: the lowest prices are prices from its history, 90 days ≤ 30 days, the change count fits the history | 0 (cache) |
| `test_market_of_a_city` | `get_market_statistics` of Kraków (fixture), from the offer snapshot (D20): `as_of` no later than tomorrow (older than yesterday is a warning), counts, spreads in order, plausible medians ([W] a city other than the two captured has their snapshot shape), the top developers in order with their names and links, `list_url`, no single offers, < 8000 characters; a total more than 25% off `search_offers` fails (archived offers in the snapshot, T72), more than 2% is a warning | 1 |
| `test_market_with_filters` | `price_max=700000`, `area_min=40`: fewer offers, spreads within the filters, `list_url` with them | 0 (cache; 1 if the TTL of `offer-snapshot` ran out) |
| `test_market_of_the_whole_country_is_refused_without_a_request` | `city=polska`: `isError` „tylko dla jednego miasta” | 0 |
| `test_market_of_an_unknown_city` | [P 2026-10-31] an unknown city (a 404 JSON `Unknown city`), then the place's lookup from the cache (D19): „Nie znaleziono miejscowości o city_slug …” with „Statystyki rynku są tylko dla jednego miasta …”, never „Serwis mógł się zmienić” | 1 (cache; 2 if the lookup is not cached) |
| `test_market_of_a_known_place_without_offers` | [P 2026-11-02] `krakowiany` (in the transactions dictionary, no offers): an empty snapshot, not a 404, so an empty market with the hint and no lookup | 1 |
| `test_developer_of_the_whole_country` | `get_developer` of the first offer's developer (`city` defaults to `polska`): counters, investments by active offers, links, < 15,000 characters; every city has both counts (read from display text, a missing one means a changed chart), the cities by active offers then price per m², without truncation each city sums up its investments | 1 |
| `test_developer_in_a_city` | the same developer, `city=krakow`, `limit=100`: only investments in Kraków, the city's row of `cities` equal to the summary (price per m² within 1 PLN), the same cities as the whole country's profile ([W] a page without the chart of cities is a developer in one city); the offer's investment missing is a warning | 1 |
| `test_developer_unknown` | [P 2026-10-31] „Nie znaleziono dewelopera” (Next.js's 404 marker, for the default `polska` as for a city), not „Serwis mógł się zmienić” | 1 |
| `test_developer_in_an_unknown_city` | [P 2026-11-02] T39, D21 (exception for T39): the page redirects to the developer's page for the whole country, read as „not found”; the place's lookup from the cache: „Nie znaleziono miejscowości o city_slug …” with „Potem sprawdź developer_slug (search_developers).”, never „Serwis mógł się zmienić” | 1 (cache; 2 if the lookup is not cached) |
| `test_developer_in_a_known_place_without_its_offers` | [P 2026-11-02] the same developer in `krakowiany`: „not found”, then the place's first lookup: „Miejscowość 'Krakowiany' istnieje, ale serwis nie ma …” with `city=polska` | 2 |

### CLI: `test_live_cli.py` (16 tests, 16 requests)

Each command is a separate process, without a shared cache. Exit code 3 or „Błąd: STOP:” ends the run with code 3; exit code 4 (a service error) ends it with code 4.

| Test | What it checks | Requests |
|---|---|---|
| `test_locations_search_as_text` | `locations search Kraków`: text, the line „miasto … Kraków [krakow]” | 2 |
| `test_locations_search_as_json` | `locations search Gdańsk --json` | 2 |
| `test_offers_search_with_filters_as_json` | `offers search krakow` with filters, `--json`: ranges and order (fixture) | 1 |
| `test_offers_search_with_filters_as_text` | the same as text | 1 |
| `test_offers_get` | `offers get <id> --investment <slug>`: the price history | 2 |
| `test_investments_get_with_a_limit_and_history` | `investments get <slug> --limit 2 --history`: each offer followed by its price events | 1 |
| `test_offers_search_of_an_unknown_city` | exit code 7, „Nie znaleziono miejscowości o city_slug …” (after the place's lookup) without `polska`, `Szczegóły:` without HTML | 2 |
| `test_offers_search_of_the_whole_country_sends_nothing` | [P 2026-10-29] `offers search polska`: exit code 2, „city=polska nie działa” | 0 |
| `test_stats_government_as_text` | `stats government warszawa unemployment`: the header, a link to `#gus-bezrobocie`, a table of 12 months | 1 |
| `test_offers_search_with_a_wrong_page_size_sends_nothing` | `--per-page 7`: exit code 2 | 0 |
| `test_stop_status_is_offline` | `stop status`: exit code 0 | 0 |
| `test_the_installed_script_runs_offline` | the installed script `deweloperuch stop status`: exit code 0 | 0 |
| `test_stats_market_as_text` | `stats market sopot`: the header ending with the day of the data („stan na …”), the link to the list, the table of spreads, the largest developers (the first by its name and slug) | 1 |
| `test_developers_get_in_a_city_as_json` | `developers get <developer of the first offer> --city krakow --json`: investments in Kraków only, the profile link | 1 |
| `test_developers_get_of_an_unknown_developer` | [P 2026-10-31] `developers get nieistniejacy-deweloper-e2e --city warszawa`: exit code 7; the place's lookup finds Warsaw [P 2026-11-02], so „Miejscowość 'Warszawa' istnieje, ale serwis nie ma …” with `search_developers` and `city=polska`, never „Serwis mógł się zmienić” | 2 |

### Recon: `test_live_recon.py` (2 tests, 2 requests)

| Test | What it checks | Requests |
|---|---|---|
| `test_probe_api` | `probe.py api "/api/cities?q=krak"`: exit code 0, JSON with krakow | 1 |
| `test_probe_page_lists_the_data_props` | `probe.py page "/ceny-ofertowe/warszawa/mieszkania?perPage=10"` without `--prop`: the list of props contains `sales` (10) and `serverPaginationData` (6 keys) [P 2026-10-31] | 1 |

The bundle scanner (`recon/scan_bundles.py`, about 140 requests) is not part of the suite.

### Other tools: one module each

Each module starts its own `deweloperuch-mcp` (with its own cache); the CLI runs are separate processes. "Plan / at most" counts the module's requests in file order.

| Module | Tool, command | Tests | Plan / at most | What it checks |
|---|---|---|---|---|
| `test_live_developer_search.py` | `search_developers`, `developers search` | 8 | 4 / 8 | a known developer (slug, profile link for `polska`), the repeat from the cache, the largest limit (20), nothing found with a hint, 3 refusals without a request, the CLI with `--json` |
| `test_live_investment_search.py` | `search_investments` | 5 | 4 / 6 | the investments of Sopot ordered by active offers, the same list filtered and ordered (cache, at most 1), a search by name honouring its limit and `total` [W], the match's active offers equal to those of `get_investment` [W], an unknown city (last: an empty list with the hint and no lookup [P 2026-11-02], or its own „not found” and the place's lookup) |
| `test_live_transactions.py` | `get_transaction_statistics`, `stats transactions` | 9 | 5 / 7 | months of Warsaw from its statistics page (since 2017, ending with a month with transactions: the page's empty padding is dropped), more months from the cache, fewer transactions in the latest months (the RCN reporting lag), the incomplete months are the newest ones and end at `last_complete_period` (cache), quarters, the price of a quarter is a median (cache), the CLI for another city (every month of the secondary market, or the adapter refuses it), an aggregate (`7-miast`) refused without a request, an unknown city is "not found", then the place's lookup (last); every result: `incomplete` only on trailing periods; `total` is never pinned |
| `test_live_rankings.py` | `rank_locations`, `stats cities` | 11 | 4 / 10 | cities by transactions, by price from the cache (the most expensive with `min_transactions=50`, the cheapest with the default threshold of 20), powiats on the secondary market over a 12-month period (every powiat named by the packaged table), the primary and both markets from the cache (no powiat with 0 transactions), the cheapest powiats from the cache, the 66 cities by the unemployment rate (every city named, each linked to its government statistics), NBP prices from the cache (only the cities that have them), a market for cities refused without a request, the CLI as text |
| `test_live_buildings.py` | `get_building`, `buildings get` | 6 | 6 / 6 | the building of the sample with its units, transactions and trend (2), the repeat from the cache, the CLI with `--json`, `cisna` with its trend (2): no average of 0, the counts of the transactions that are no regular sale match the listed ones, a trend without quarters has no radius and a hint, [H] an unknown slug (last, since a 5xx ends the run) |
| `test_live_districts.py` | `search_offers` | 1 | 3 / 3 | [P 2026-11-01] a district written otherwise than the service's slug (`PragaPołudnie`): the client's slug is unknown, the city's districts are read and the list is asked once more by the service's slug `praga-poludnie`: no error, offers, `list_url` of that list; its own server, so nothing comes from the cache of `test_live_mcp.py` |
| `test_live_valuation.py` | `estimate_property_value`, `valuation estimate` | 5 | 5 / 5 | `search_locations` for a street's coordinates (2), a valuation there, a valuation in Cisna (fewer than 5 transactions: `low_confidence` and the caveat in `hint`, only warned about when no longer so), a point outside Poland refused without a request, the CLI with `--json` at the sample's point; every valuation: `low_confidence` true exactly below 5 transactions |

**In total:** 160 tests, a plan of 114 live requests, at most 157, a hard limit of 170.
