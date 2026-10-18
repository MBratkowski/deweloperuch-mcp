# deweloperuch CLI: worked examples

Each workflow lists the commands in order and the `--json` fields to read. `deweloperuch …` stands for `uvx --from deweloperuch-mcp deweloperuch …` when the package is not installed. Slugs and ids below (`krakow`, `smolna`, `2377`, `atal`) are examples: take the real ones from the previous command's output. Every command sends at most a few requests; run them one at a time and keep their output.

## 1. Find a flat

The user: "Find a 2-room flat in Kraków's Podgórze up to 800 000 PLN."

```
deweloperuch locations search krak --json
deweloperuch locations search podgórze --json
deweloperuch offers search krakow --district Podgórze --price-max 800000 --area-min 38 --area-max 55 --sort price_per_m2_asc --json
```

1. `locations search`: take the item with `kind` city and `offer_count` above 0; its `city_slug` (`krakow`) goes to `offers search`. A district is an item with `kind` district; pass its `name` (`Podgórze`) as `--district`, together with its city's slug.
2. There is no rooms filter: say so and translate rooms into an area range (here 38–55 m²).
3. `offers search` result: `total` (how many offers match), `returned`, `truncated`, `hint`, `list_url` (the same list on deweloperuch.pl) and `items`. Per item: `investment_name`, `developer_name`, `price`, `area_m2`, `price_per_m2`, `price_change_since_start_pct` (negative: cheaper than its first price), `status`, `investment_url`, plus `offer_id` and `investment_slug` for the next steps.
4. Answer with a table (investment, developer, price, area, price per m², change since the first price, link) and give `total` and `list_url` below it.
5. If `truncated` is true, propose narrower filters (budget, area, district, `--price-dropped`) instead of fetching more pages.

## 2. Judge one offer

The user: "Is offer 2377 in the investment smolna a good deal?"

```
deweloperuch offers get 2377 --investment smolna --json
deweloperuch stats market warszawa --area-min 40 --area-max 60 --json
deweloperuch investments get smolna --limit 0 --json
deweloperuch valuation estimate --lat 52.2297 --lng 21.0122 --area 50 --limit 5 --json
```

1. `offers get`: `price`, `area_m2`, `price_per_m2`, `status`, `city_slug`, `price_history` (dated events) and `price_flags`:
   - `lowest_price_30d`, `lowest_price_90d`: the lowest price in the last 30 and 90 days; compare with the current `price`;
   - `price_changes`, `largest_drop_pct`, `largest_rise_pct`;
   - `suspicious_reduction`: a reduction within 30 days after a rise (a "promotion" after a price increase).
2. `stats market` for the offer's `city_slug`, with `--area-min`/`--area-max` about ±10 m² around the offer's area: where the offer's price per m² falls against `price_per_m2.p25`, `.median` and `.p75`. It covers active offers only; for an archived offer you compare its last price with today's market.
3. `investments get SLUG --limit 0`: the investment's `lat` and `lng` (no offers listed). Without coordinates skip the valuation and say so.
4. `valuation estimate` with those coordinates and the offer's area: `estimated_value`, `price_per_m2`, `stats.median_price_per_m2`, `radius_m`, `period_months`, `low_confidence` and the nearest `comparables` (RCN transactions). With `low_confidence: true` pass on the caveat from `hint`.
5. Verdict in one line (a bargain, in line with the market, or expensive) with the numbers: the offer's price per m², the city's median, the valuation. Add the history findings and `investment_url`, `developer_url`.
6. Caveats to state: offers and market statistics are asking prices; the valuation comes from transaction prices registered months late; it is an approximation, not an appraisal; never average the two kinds of price.

## 3. Check a developer

The user: "What does Atal build, and are its prices falling in Warsaw?"

```
deweloperuch developers search atal --json
deweloperuch developers get atal --json
deweloperuch investments search warszawa --developer atal --sort price_per_m2_asc --json
deweloperuch investments get nowy-targowek-vi --limit 20 --json
```

1. `developers search`: the matching developers with their slugs. If several match and the name does not decide, ask the user which one.
2. `developers get SLUG` (whole country by default, `--city` for one city): `summary` (active offers, investments, cities, average prices), `investments` (each with `investment_url`) and `cities`.
3. `investments search CITY --developer SLUG`: the developer's investments in one city with streets and average price per m².
4. Price changes: `investments get` for 1–3 investments with the most active offers (not all of them); per offer `price_change_since_start_pct` shows reductions (negative) and rises since the first price.
5. Summary: scale, a table of investments (name, city, active offers, average price per m², link), how many offers got cheaper or dearer, and `developer_url`. Offer prices say nothing about a developer's finances or reliability.

## 4. Compare cities

The user: "Compare flat prices in Kraków, Wrocław and Gdańsk."

For each city (at most 5 at once):

```
deweloperuch stats market krakow --json
deweloperuch stats transactions krakow --json
deweloperuch stats government krakow wages --json
```

1. City slugs: lowercase ASCII with hyphens (`krakow`, `wroclaw`, `gdansk`, `bielsko-biala`); check an unsure one with `locations search`.
2. `stats market`: asking prices of active offers: `price_per_m2.median` (with `p25`, `p75`), `price.median`, `area_m2.median`, `offers`, `investments`, `developers`, `list_url`.
3. `stats transactions`: RCN transaction prices per month (`--granularity quarter` for a longer history): per period `period`, `transactions`, `median_price_per_m2`. The newest months are incomplete because transactions reach the register months late: skip periods with `incomplete: true` and compare the cities on the same periods, no newer than the earliest `last_complete_period` of them; a city without `last_complete_period` has too few transactions to judge (read `hint`).
4. `stats government LOCATION wages` (or `unemployment`) only when the question is about affordability or the job market; it needs no search and covers `polska`, the aggregates `7-miast`, `10-miast`, `6-miast-bez-warszawy` and cities with powiat rights.
5. One table, a row per city: median asking price per m², offers, transaction price per m² with its period, transactions (and wages or unemployment if asked). Asking and transaction prices in separate columns; write „brak” where data is missing.

## 5. The market as a whole

```
deweloperuch stats cities --sort price_per_m2_desc --min-transactions 200 --limit 10 --json
deweloperuch stats government polska nbp_prices --json
deweloperuch stats government polska dwellings_quarterly --periods 8 --json
```

- `stats cities`: places (or powiats with `--level powiat`) ranked by RCN transactions or by price per m²; `--min-transactions` drops places with too few transactions to rank by price (20 by default when sorting by price; `--min-transactions 0` ranks every place).
- `stats government`: official series as periods and values (`series[].points`), with `source`, `frequency` and `stats_url`. Datasets: `dwellings_quarterly`, `dwellings_monthly`, `average_area`, `demography`, `population`, `unemployment`, `wages`, `nbp_prices`.

## 6. One building's transactions

```
deweloperuch buildings get 23-marca-79c-sopot --limit 5 --trend --json
```

The slug is the last part of the address of a building page with transaction prices on deweloperuch.pl. The result lists units (newest transaction first) with their transactions (transaction prices, not asking prices); `--trend` adds the neighbourhood's average price per m² by quarter (one more request).

## When a command fails

- Exit code 2 (`Błąd: …` on stderr): the message names the argument and what it expects, for example a city that is not a slug („city: oczekiwano slug miasta…”). Fix it and run again.
- Exit code 7: the service does not know the slug or has no data for the place. Look the slug up with `locations search`, `developers search` or `investments search`; do not guess another one.
- Exit code 3 (STOP): stop at once. Do not run another `deweloperuch` command, do not retry, do not look for a workaround. Tell the user what stderr says; only the user lifts a STOP, after checking its cause.
- Exit codes 4, 5 and 6: tell the user; never retry in a loop.
