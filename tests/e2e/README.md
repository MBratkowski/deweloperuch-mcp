# End-to-end tests on the live service

The suite checks the installed package against the real deweloperuch.pl: the MCP server over stdio with the official SDK client, the CLI and `recon/probe.py`. It is **off** by default.

## Before you run it

- A run is a series of live requests. Until U1 is resolved it needs the user's explicit consent in the current conversation (D9; the exception for this suite is described in D10). Do not run it in parallel with `recon-verifier` or `drift-checker`.
- The suite does not set a private `XDG_CACHE_HOME`, so it uses the limiter and the STOP record of your environment (`${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/`). It shares them with Claude Desktop and other processes only when they see the same `XDG_CACHE_HOME`. A shell with a different value than the Desktop environment has a separate limiter.
- An active STOP before the start ends the run without any request. Only the user lifts a STOP, after checking its cause ([configuration.md](../../docs/configuration.md#stop-shared-lock-between-processes)).

## Running

```
DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e -rs --maxfail=3
```

- Both switches are needed: the variable and `-m live`. Without either, every test is skipped with the reason „e2e na żywym serwisie…” before any fixture starts, so no process is launched. `tests/test_e2e_gate.py` checks this in the default `uv run pytest`.
- `--maxfail=3` stops the run after three failures instead of sending more requests.
- The run ends at once, without further requests and without retries:

  | pytest code | Reason | What to do |
  |---|---|---|
  | 3 | STOP: 401, 403, 429 or a challenge | report it to the user |
  | 4 | service unavailable: 5xx or network | try later |
  | 1 | request budget exceeded or a broken counter | check the suite |

  A broken counter is a call that had to reach the network while the server log has no `HTTP Request:` line at all. Most often it means a change of logging in the MCP SDK.
- **Budget:** at most 70 live requests per run. The plan is 51, a little under a minute at 1 request per second. The worst case is 67: each of the 16 calls served from the cache goes to the network, and those tests fail anyway. At the end pytest prints the section „żywe zapytania (e2e)” with the number of requests per call.
- **Cache:** the server keeps a response for at most 300 s. Freshness is `s-maxage`, without it `max-age`, without both 300 s, minus `Age` from Cloudflare; `no-store` or `no-cache` turns the cache off (`deweloperuch_mcp.infrastructure.deweloperuch.transport._ttl`, D2). The tools use only endpoints with `max-age=28800` and no `s-maxage` [P 2026-10-10; for the government statistics page [W]: like the other RSC pages], so during a run (about a minute) a repeat always comes from the cache. Tests marked "cache" require exactly the stated number of requests. On a failure, check `Age` and `Cache-Control` of that response: with `Age` ≥ `max-age` a TTL of 0 follows the rule. The computed TTL is in the log at DEBUG level (`TTL cache …`). There is no tolerance, because the only endpoint with a short freshness (`city-sales`, `s-maxage=300`) is not used by the tools.
- **Counting requests:**
  - the MCP server logs every request (`HTTP Request:`) on stderr, and the suite reads that stream;
  - the CLI runs through its entry point (`deweloperuch_mcp.cli:main`) with the httpx log in a file;
  - probe counts as 1 request unless it ended with code 2 or 5.

  Requests that got a response are counted.
- **Logs:** in pytest's temporary directory (`--basetemp`, if you want to choose it): `mcp*/server-stderr.log` and `cli*/cli-N.log`.
- **Warnings** (`UserWarning`) are not errors. They concern data that may change between calls: the price of an offer, or `offers_total` not matching the list.
- **xfail** marks a known problem, described in the test's reason, not a failure.
- Assertions check structure, ranges and consistency, not specific numbers. Behaviour marked [W] in the code is confirmed only by a live run.

## Scenarios

The "Requests" column gives the count when the whole module runs in file order. A fixture counts at the first test that uses it. "Cache" means the repeated part of the call comes from the server's cache.

### MCP: `test_live_mcp.py` (60 tests, 38 requests, at most 54)

One `deweloperuch-mcp` process per module, so repeated requests come from the server's cache. Every result is checked for a STOP, an unavailable service and backend details:

- in text and values: `/api/`, `initialData`, `_rsc`, `invest_`, `sale_id`, `/ceny-`, `/statystyki`, `tocItems`, `sortedLocations`, `currentSlug`, `NEXT_HTTP`, `digest`, `Next-Action`, `buildId`, `Traceback`, `File "`, `httpx`, `pydantic.dev`, addresses of the service, HTML;
- in field names: `sale`, `invest` (except `investment`), `rcn`, `amount`, `rsc`.

Values (developer names, slugs) are not checked for backend names, because a real developer is called e.g. „Invest Komfort”. The SDK checks results against the output schema.

The only exception are links to the service's public pages (D12): `list_url`, `investment_url`, `developer_url` and `stats_url`. A full address is allowed only as the whole value of a `*_url` field and only in four shapes [P]:

- `…/ceny-ofertowe/{city}/mieszkania?…`;
- `…/ceny-ofertowe/{city}/deweloperzy/{developer}`;
- `…/ceny-ofertowe/{city}/deweloperzy/{developer}/{investment}`;
- `…/statystyki/statystyki-rzadowe/{location}`, optionally with `#{section}` (an id of the page's table of contents: lowercase letters, digits, hyphens).

A segment may not contain `/`, `?` or `#`, may not be `.` or `..` and may not contain `%2e`. An address with `_rsc` or `/api/`, in another field or in an error message, is a leak. The tests check the pattern of the links:

- list: the city's path, and in the query exactly the tool's arguments, in the order the service is sent them;
- investment and developer profile: the slugs of the result;
- statistics: the page of the location from the argument and the section of the dataset.

Only two links are opened, through `probe`: `test_the_investment_link_leads_to_its_page` and `test_the_statistics_link_leads_to_its_section`.

| Test | What it checks | Requests |
|---|---|---|
| `test_tools_list_matches_the_snapshot` | 5 tools; names, descriptions, schemas, annotations, `serverInfo` and instructions match `tests/snapshots/mcp_tools.json` | 0 |
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
| `test_offers_of_an_unknown_city_say_so` | „nie zna miasta”, `search_locations`, `polska`, without „Serwis mógł się zmienić” | 1 |
| `test_offers_page_past_the_last_one` | [W] `sopot` (few offers, T12), then a page past the last one: an empty page with a hint; „nie zna miasta” is an xfail (a known problem, T34) | 2 |
| `test_offers_price_min_above_price_max_is_refused_without_a_request` | `isError` | 0 |
| `test_offers_arguments_off_the_schema_are_refused_without_a_request` ×3 | `per_page=100`, `page=21`, `sort="area_asc"`: a schema error with the field and the rule, without a link to pydantic.dev | 0 |
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
| `test_government_average_area_of_poland` | `polska` + `average_area` (the page the user showed): D4 counters, yearly periods ascending, 30–150 m², `stats_url` with `#gus-srednia-powierzchnia` (fixture) | 1 |
| `test_government_nbp_prices_of_a_city` | `warszawa` + `nbp_prices`: 4 NBP series in PLN/m², quarters, `#nbp` (fixture) | 1 |
| `test_government_average_area_of_an_aggregate` | [H] `7-miast` + `average_area`: an aggregate's page; its `currentSlug` is unconfirmed, and a mismatch would make every aggregate a "service changed" error: the failure then quotes the server log line with `currentSlug` | 1 |
| `test_government_another_dataset_of_the_same_location_comes_from_the_cache` | `polska` + `unemployment`: the same page, a rate of 0–40% | 0 (cache) |
| `test_government_nbp_prices_of_poland_point_to_cities` | `polska` + `nbp_prices`: `isError`, the list of locations with NBP prices [P 2026-10-11] | 0 (cache) |
| `test_government_dwellings_fit_the_size_budget` | `polska` + `dwellings_quarterly` (15 series, 12 periods) < 8000 characters | 0 (cache) |
| `test_government_unknown_location` | [H] an unknown location: „nie ma statystyk rządowych”, i.e. Next.js's 404 marker; the message „Serwis mógł się zmienić” (no marker) is an xfail with a finding for `docs/open-questions.md` | 1 |
| `test_government_location_that_is_not_a_slug_is_refused_without_a_request` ×3 | „Kraków”, „kraków”, „”: `isError` saying what to give (capitals alone are lowercased, so „Warszawa” would be a valid location) | 0 |
| `test_the_statistics_link_leads_to_its_section` | `probe page <path of stats_url without the anchor> --prop tocItems`: code 0, the table of contents contains the section of the anchor | 1 (probe) |
| `test_two_calls_at_once_go_one_by_one_through_the_limiter` | two calls at once: both correct, requests in the log ≥ 0.9 s apart | 2 |

### CLI: `test_live_cli.py` (11 tests, 11 requests)

Each command is a separate process, without a shared cache. Code 3 or „Błąd: STOP:” ends the run with code 3, and code 4 (a service error) with code 4.

| Test | What it checks | Requests |
|---|---|---|
| `test_locations_search_as_text` | `locations search Kraków`: text, the line „miasto … Kraków [krakow]” | 2 |
| `test_locations_search_as_json` | `locations search Gdańsk --json` | 2 |
| `test_offers_search_with_filters_as_json` | `offers search krakow` with filters, `--json`: ranges and order (fixture) | 1 |
| `test_offers_search_with_filters_as_text` | the same as text | 1 |
| `test_offers_get` | `offers get <id> --investment <slug>`: the price history | 2 |
| `test_investments_get_with_a_limit` | `investments get <slug> --limit 2` | 1 |
| `test_offers_search_of_an_unknown_city` | code 7, a message with `search_locations` and `polska`, `Szczegóły:` without HTML | 1 |
| `test_stats_government_as_text` | `stats government warszawa unemployment`: the head, a link to `#gus-bezrobocie`, a table of 12 months | 1 |
| `test_offers_search_with_a_wrong_page_size_sends_nothing` | `--per-page 7`: code 2 | 0 |
| `test_stop_status_is_offline` | `stop status`: code 0 | 0 |
| `test_the_installed_script_runs_offline` | the installed script `deweloperuch stop status`: code 0 | 0 |

### Recon: `test_live_recon.py` (2 tests, 2 requests)

| Test | What it checks | Requests |
|---|---|---|
| `test_probe_api` | `probe.py api "/api/cities?q=krak"`: code 0, JSON with krakow | 1 |
| `test_probe_page_lists_the_data_props` | `probe.py page "/ceny-ofertowe/warszawa/mieszkania?perPage=10"` without `--prop`: the list of props contains `initialData` | 1 |

The bundle scanner (`recon/scan_bundles.py`, about 140 requests) is not part of the suite.

**In total:** 73 tests, a plan of 51 live requests, at most 67, a limit of 70.
