---
name: deweloperuch-cli
description: Query Polish new-build apartment data with the read-only deweloperuch CLI (data of deweloperuch.pl) - developers' asking prices with price history and price-drop flags, investments and developers, RCN transaction prices, flat valuations from nearby transactions, offer-market statistics of a city, and official GUS and NBP statistics. Use it when the user asks about buying a flat in Poland, new flats from developers, an offer and its price history, whether a price is good, a developer and its projects, transaction prices, valuing a flat, or comparing cities. Triggers in Polish - ceny mieszkań, nowe mieszkania, mieszkanie od dewelopera, deweloper, inwestycja, oferty mieszkań, historia ceny, obniżka ceny, cena za m2, ceny transakcyjne, RCN, wycena mieszkania, rynek pierwotny, GUS, NBP, wynagrodzenia, bezrobocie. In English - Poland new-build apartment prices, flat prices in Polish cities, asking vs transaction prices, property valuation in Poland.
license: MIT
compatibility: Needs uv (uvx) or the deweloperuch-mcp Python package (Python 3.11+), macOS, Linux or Windows, and network access to deweloperuch.pl. Windows needs a version newer than 0.1.2 or a current source checkout.
---

# deweloperuch CLI

`deweloperuch` is an unofficial, read-only command line over the public data of deweloperuch.pl: asking prices of developers' flats (primary market) with their price history, transaction prices from the Polish price register (RCN), and GUS and NBP statistics. It never changes anything on the service. Its help texts and output are in Polish.

- Every command and option: [REFERENCE.md](REFERENCE.md) (generated from the CLI).
- Worked workflows with the fields to read: [EXAMPLES.md](EXAMPLES.md).

## Running it

Without installing anything (needs uv, <https://docs.astral.sh/uv/>; Windows support requires a version newer than 0.1.2 or a current source checkout):

```
uvx --from deweloperuch-mcp deweloperuch --help
```

Below, `deweloperuch …` stands for `uvx --from deweloperuch-mcp deweloperuch …`. Call an installed `deweloperuch` directly only if `deweloperuch --help` lists this package's groups: `locations`, `offers`, `investments`, `developers`, `buildings`, `valuation`, `stats`, `stop` and `skill`. A successful help exit alone does not identify the package.

If those groups are missing (for example, the legacy Node `deweloperuch-poc` lists `overview` and `mcp-config`), keep the existing installation and use `uvx --from deweloperuch-mcp deweloperuch …` for every command below. Without uv: `pip install deweloperuch-mcp` (Python 3.11+). The first `uvx` run downloads the package; its notes on stderr are not errors.

On Windows before a release newer than 0.1.2, use a current source checkout for every command instead: `uv run --directory C:\path\to\deweloperuch-mcp deweloperuch …`. This replaces the whole `uvx` prefix above; the published 0.1.2 package does not support Windows.

- `--help` on any group or command is offline and free: use it when unsure of an option.
- Add `--json` to parse a result: the full domain model, `null` included. Without it the output is Polish text for people.
- List results carry `total`, `returned` and `truncated`; `hint` says what to narrow when the list was cut.
- Fields ending in `_url` are links to the service's public pages: give them to the user (for example in a table of offers).
- If the `deweloperuch` MCP tools (`search_offers`, `get_offer`…) are already connected, you may use them instead; do not ask both for the same data.

## Be a polite client

The service is a community project run by other people. The CLI already limits every process on the machine to 1 request per second, one at a time; do not work around it.

- Narrow filters (`--price-max`, `--area-min`, `--area-max`, `--district`, `--sort`) instead of paging through results. One page of `--per-page 50` beats five pages of 10.
- No loops, no bulk downloads, no scraping every investment or city. Ask for what answers the question, usually 2–6 commands.
- Run commands one after another, never in parallel.
- Each run is a new process with its own cache: keep the output you got (or save `--json` to a file) instead of running the same command again.

## Exit codes and what to do

| Code | Meaning | What to do |
|---|---|---|
| 0 | Success. | Use the output. |
| 1 | Another error (also files that `skill install` could not write). | Report the message to the user. |
| 2 | Bad argument or usage. | Read `Błąd: …` on stderr, fix the argument as it says, run again. |
| 3 | STOP: the service refused (401, 403, 429 or a challenge), or a STOP recorded earlier by any process. | **Stop.** Run no more `deweloperuch` commands, no retries, no workarounds. Tell the user the reason from stderr. |
| 4 | Service error (5xx, network, timeout). | Do not retry in a loop. Tell the user; at most one retry later. |
| 5 | The shared limiter asks for a longer pause than allowed; nothing was sent. | Wait the time the message gives before the next command, or tell the user. |
| 6 | The answer did not match the expected shape; the service may have changed. | Tell the user; retrying will not help. |
| 7 | Not found: no such city, investment, offer, developer or building, or no data for the place. | Check the slug with a search command; do not guess slugs. |

After exit code 3 every process on the machine (CLI, MCP server) sends nothing while the STOP holds. A STOP after a 429 ends by itself after its pause; any other STOP is lifted **only by the user**, after checking the cause. Never lift it yourself (the `stop` group has a command for that, meant for people only) and never delete the package's cache folder. You may check the state with `deweloperuch stop status` (offline; exit code 3 while a STOP holds).

## Identifiers come from search commands

Never guess a slug; take it from a command's output.

| You need | Get it from |
|---|---|
| city slug (`krakow`, `warszawa`, `bielsko-biala`) | `deweloperuch locations search krak` (`kind` city, field `city_slug`) |
| district name for `--district` | `locations search` (`kind` district, field `name`, e.g. `Mokotów`) |
| investment slug | `offers search` or `investments search` (field `investment_slug`) |
| offer id | `offers search` or `investments get` (field `offer_id`) |
| developer slug | `deweloperuch developers search atal` (or `developer_slug` of an offer) |
| coordinates for `valuation estimate` | `investments get` (`lat`, `lng`) or a district or street from `locations search` |
| building slug for `buildings get` | the last part of the address of a building page on deweloperuch.pl |

`polska` means the whole country where a command allows it (`offers search`, `developers get --city`, `stats government`); `stats market` and `stats transactions` take one city.

## Know which price you are showing

- **Asking prices** (what developers want): `offers`, `investments`, `developers`, `stats market`. `stats market` covers active offers only.
- **Transaction prices** (what flats sold for, from RCN): `stats transactions`, `stats cities`, `buildings get`, `valuation estimate`. They reach the register months late, so the newest periods are incomplete: read the `note` field and compare full periods; a drop in the last months is not a trend.
- **Official statistics** (GUS and NBP: dwellings completed and started, NBP prices, wages, unemployment, population): `stats government`. They need no earlier search.

Asking and transaction prices are different measures: show them in separate columns and never average them together. A valuation is an approximation from nearby transactions, not an appraisal („przybliżenie, nie operat”).

Other limits:

- There is no filter by number of rooms or floor: when the user asks for rooms, say so and filter by area instead (for example 2 rooms ≈ 38–55 m²).
- `offers search` shows at most 20 pages; when `truncated` is true, narrow the filters.
- Amounts are whole PLN (`--price-max 800000`), areas whole m² in filters (`--area-min 40`).
- Data accuracy is not guaranteed and nothing here is financial advice; say so when you give a verdict.

## Recipes

Each recipe mirrors one of the MCP server's prompts. Full versions with the fields to read: [EXAMPLES.md](EXAMPLES.md).

**Find a flat** (city, budget, area, district):

```
deweloperuch locations search krak --json
deweloperuch offers search krakow --district Podgórze --price-max 800000 --area-min 40 --area-max 60 --sort price_per_m2_asc --json
```

Show a table: investment, developer, price, area, price per m², change since the first price, `investment_url`; below it `total` and `list_url`.

**Judge one offer** (price history, the city's market, a valuation):

```
deweloperuch offers get 2377 --investment smolna --json
deweloperuch stats market warszawa --area-min 40 --area-max 60 --json
deweloperuch investments get smolna --limit 0 --json
deweloperuch valuation estimate --lat 52.2297 --lng 21.0122 --area 50 --limit 5 --json
```

`--lat` and `--lng` come from `investments get`, `--area` is the offer's area. Compare the price with `price_flags` (`lowest_price_30d`, `lowest_price_90d`, `suspicious_reduction`: a reduction within 30 days after a rise), with the city's p25, median and p75 price per m², and with the valuation. Give a short verdict with numbers and the caveats above.

**Check a developer**:

```
deweloperuch developers search atal --json
deweloperuch developers get atal --json
deweloperuch investments search krakow --developer atal --sort price_per_m2_asc --json
```

Summarise the scale (active offers, investments, cities), the investments with their average price per m² and links, and the price changes of 1–3 of the largest investments (`investments get SLUG`). Offer prices say nothing about a developer's finances or reliability.

**Compare cities** (at most 5 at once):

```
deweloperuch stats market krakow --json
deweloperuch stats transactions krakow --json
deweloperuch stats government krakow wages --json
```

Repeat per city; one table with a row per city: median asking price per m², number of offers, transaction price per m² with its period, number of transactions (and wages or unemployment if asked). Write „brak” where data is missing instead of guessing.
