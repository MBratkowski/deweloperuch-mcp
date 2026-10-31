# Raw RSC payloads

Complete `text/x-component` response bodies of the service's pages (the offers list of a city or a district, the government statistics, the transaction statistics and a developer's profile), exactly as served. The samples in `docs/discovery/samples/page.*.json` keep only the value of one prop; these files hold the whole flight stream, including text rows `<id>:T<hex length in bytes>,<text>` that are not followed by a newline.

Files without a date are captures of the 1.0 service (before the relaunch of 2026-10-29); the `*_20261030.rsc` files (from PR #15) and the `*_20261031.rsc` files are captures of 2.0, whose props differ (docs/discovery/pages-rsc.md, the 2.0 sections).

| File | Request target | Response | Size |
|---|---|---|---|
| `warszawa_perPage10.rsc` | `/ceny-ofertowe/warszawa/mieszkania?perPage=10&_rsc=fe86badc` | 200, `initialData` with 10 offers (`total` 13,324). Right before the data row are the rows `16:T5ed,` and `19:T1a27,` with JSON-LD | 46,652 B (original 46,659 B) |
| `unknown_city_perPage10.rsc` | `/ceny-ofertowe/nieistniejace-miasto/mieszkania?perPage=10&_rsc=4b97e1e1` | 200 without `initialData`, with the error row `f:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}` | 26,796 B (original 26,803 B) |
| `stats_gov_polska.rsc` | `/statystyki/statystyki-rzadowe/polska?_rsc=b3d11c70` | 200 without the 404 digest: `tocItems`, `sortedLocations` (69), `currentSlug: null`, `data` ×6, `monthlyData`, the NBP price grid of cities (`seriesList`, `tableRows`) without an NBP series for Poland itself | 415,697 B (original 415,704 B) |
| `stats_gov_warszawa.rsc` | `/statystyki/statystyki-rzadowe/warszawa?_rsc=cc0b509c` | 200 without the 404 digest: `tocItems`, `sortedLocations` (69), `currentSlug: "warszawa"`, `data` ×7 (with NBP prices), `monthlyData` | 286,578 B (original 286,585 B) |
| `developer_atal_warszawa.rsc` | `/ceny-ofertowe/warszawa/deweloperzy/atal?_rsc=682178ac` | 200: the object prop `data` (`developer`, `investments` ×4, `filteredStats` with `totalProjects` 4, `totalSales` 69, `totalCities` 1, `allCities`, `allCitiesWithSlugs` as a `$f:…` reference, `citiesStats` ×14, `allInvestmentNames`), `sale` ×227 (active and archived), `data` as a list (the daily change axis) | 134,532 B (original 134,539 B) |
| `developer_atal_polska.rsc` | `/ceny-ofertowe/polska/deweloperzy/atal?_rsc=b92176ca` | 200: the same shape for the whole country: `investments` ×42, `filteredStats` with `totalProjects` 42, `totalSales` 4,078, `totalCities` 14, `sale` ×6,587 | 1,956,906 B (original 1,956,913 B) |
| `developer_unknown_warszawa.rsc` | `/ceny-ofertowe/warszawa/deweloperzy/nieistniejacy-deweloper?_rsc=448d0288` | 200 without developer data and **without** the 404 digest (unlike the offers list); row `f` renders `h1` „Deweloper nie znaleziony” and `p` „Nie znaleziono dewelopera o podanym adresie”, and the title (row `13`) is „Deweloper nie znaleziony \| Deweloperuch” [P 2026-10-13] | 27,663 B (original 27,670 B) |
| `offers_warszawa_20261031.rsc` | `/ceny-ofertowe/warszawa/mieszkania?_rsc=` | 200 (2.0): `sales` ×25, `serverPaginationData` `{currentPage 1, perPage 25, totalCount 11672, totalPages 20, startItem 1, endItem 25}`, `items` ×18 district links `{name, slug, href}` (first: Bemowo, `bemowo`) | 73,045 B (original 73,057 B) |
| `offers_unknown_city_20261031.rsc` | `/ceny-ofertowe/nieistniejace-miasto/mieszkania?_rsc=` | 200 without `sales`, with the digest `NEXT_HTTP_ERROR_FALLBACK;404` (2 occurrences) | 25,189 B |
| `offers_warszawa_mokotow_20261031.rsc` | `/ceny-ofertowe/warszawa/mokotow/mieszkania?_rsc=` | 200, the district list: `sales` ×25, `serverPaginationData` with `totalCount` 959 and `totalPages` 20, `items` ×18 as on the city list | 76,255 B (original 76,267 B) |
| `offers_warszawa_unknown_district_20261031.rsc` | `/ceny-ofertowe/warszawa/nieistniejaca-dzielnica/mieszkania?_rsc=` | 200 without `sales`, with the digest (2 occurrences); `items` ×18 | 28,341 B |
| `developer_atal_warszawa_20261031.rsc` | `/ceny-ofertowe/warszawa/deweloperzy/atal?_rsc=` | 200 (2.0): `developer` null; the props of the `hero` element: `investments` ×4, `developerSlug` `atal`, `developerName` „ATAL S.A.”, `developerId` 43; four `spec` props, the first `ceny-w-miastach` (cities); `timeline`, `sparseBySize`. No summary prop (`filteredStats` and `citiesStats` are gone) | 152,424 B (original 152,436 B) |
| `developer_atal_polska_20261031.rsc` | `/ceny-ofertowe/polska/deweloperzy/atal?_rsc=` | 200, the same shape for the whole country: `investments` ×42 | 223,465 B (original 223,477 B) |
| `developer_unknown_warszawa_20261031.rsc` | `/ceny-ofertowe/warszawa/deweloperzy/nieistniejacy-deweloper?_rsc=` | 200 without developer data, **with** the digest `NEXT_HTTP_ERROR_FALLBACK;404` (1 occurrence) and without the 1.0 text „Deweloper nie znaleziony” | 17,814 B |
| `stats_gov_warszawa_20261031.rsc` | `/statystyki/warszawa/dane-rzadowe?_rsc=` | 200 (2.0): `blocks` with `govSections` ×8 (`gus-mieszkania`, `gus-formy-budownictwa`, `gus-srednia-powierzchnia`, `gus-demografia`, `gus-wiek`, `gus-bezrobocie`, `gus-wynagrodzenia`, `nbp`), three `data` props (87 quarterly construction rows, 21 age cohorts, 80 NBP quarters), `monthlyData` ×260, `spec`, `info`; neither `tocItems` nor `sortedLocations` | 376,977 B (original 376,989 B) |
| `stats_gov_polska_20261031.rsc` | `/statystyki/polska/dane-rzadowe?_rsc=` | 200: `govSections` ×9 (`gus-mieszkania`, `gus-formy-budownictwa`, `gus-srednia-powierzchnia`, `gus-prs`, `eurostat-demografia`, `gus-wiek`, `gus-bezrobocie`, `gus-wynagrodzenia`, `nbp-grid`), two `data` props (87, 21), `monthlyData` ×260, the NBP grid of cities (`seriesList` 4, `tableRows` 7, `miniCharts`, `mobileTop3`) and no 80-row NBP `data` | 625,422 B (original 625,434 B) |
| `stats_gov_7_miast_20261031.rsc` | `/statystyki/7-miast/dane-rzadowe?_rsc=` | 200: `govSections` ×8 (`gus-mieszkania`, `gus-formy-budownictwa`, `gus-srednia-powierzchnia`, `gus-prs`, `gus-demografia`, `gus-wiek`, `gus-bezrobocie`, `nbp`: with `gus-prs`, without `gus-wynagrodzenia`), `monthlyData` ×260, no `seriesList` | 389,677 B (original 389,689 B) |
| `stats_tx_warszawa_20261031.rsc` | `/statystyki/warszawa/transakcje?_rsc=` | 200 (2.0): `view.monthly` ×118, 2017-01..2026-10, one row a month (`month, transaction_count, secondary_count, unknown_count, med_price_sqm, avg_price_sqm, med_size, avg_size, med_amount, avg_amount`); `latestSummary` 2026-04 (986 transactions); `items` ×18 district links | 151,114 B (original 151,126 B) |
| `stats_tx_karpacz_20261031.rsc` | `/statystyki/karpacz/transakcje?_rsc=` | 200, a small town: `view.monthly` ×118, 2017-01..2026-10; `latestSummary` null | 100,728 B (original 100,740 B) |
| `developer_ceres_warszawa_20261031.rsc` | `/ceny-ofertowe/warszawa/deweloperzy/ceres-development?_rsc=` | 200: a developer active in one city only (1 investment in Warszawa in the developer list of the 2026-10-30 scan): `hero` props with `developerName` „Ceres Development Sp. z o.o.” and `investments`, but **no `ceny-w-miastach` chart** | 95,732 B (original 95,744 B) |
| `developer_dom_development_warszawa_20261031.rsc` | `/ceny-ofertowe/warszawa/deweloperzy/dom-development?_rsc=` | 200: a large developer; the `ceny-w-miastach` chart has 3 rows (Warszawa, Kraków, Wrocław), and a count of 1,000 or more is written with a no-break space: Warszawa `"extra":"1 816"`, `"sub":"28 inwestycji"`, `"value":18568`, `"href":null` for the current city | 166,572 B (original 166,584 B) |
| `developer_unknown_polska_20261031.rsc` | `/ceny-ofertowe/polska/deweloperzy/nieistniejacy-deweloper?_rsc=` | 200 without developer data, with the digest `NEXT_HTTP_ERROR_FALLBACK;404` (1 occurrence), as on a city's page | 17,810 B |
| `offers_wroclaw_perPage10_20261030.rsc` | `/ceny-ofertowe/wroclaw/mieszkania?perPage=10&_rsc` | 200 from the 2.0 build: no `initialData`; `sales` with 10 offers (the fields of the old `initialData.data`) and `serverPaginationData` (`currentPage` 1, `perPage` 10, `totalCount` 5,836, `totalPages` 20) | 66,731 B (original 66,743 B) |
| `developer_archicom_polska_20261030.rsc` | `/ceny-ofertowe/polska/deweloperzy/archicom?_rsc` | 200 from the 2.0 build: no `data`; `developerName` „Archicom S.A.”, `developerId` 86, `investments` ×6 (all active), chart specs `spec` with `ceny-w-miastach` (3 cities: Warszawa 22,196, Wrocław 15,490, Iwiny 11,855 PLN/m²), `timeline` | 165,117 B (original 165,129 B) |
| `stats_gov_wroclaw_20261030.rsc` | `/statystyki/wroclaw/dane-rzadowe?_rsc` | 200 from the 2.0 build: no `tocItems`, `sortedLocations` or `currentSlug`; `blocks.govSections` (8 sections), `citySlug` `wroclaw`, `cityName` „Wrocław”, `data` rows of dwellings (87 quarters), population (21 years) and NBP (80 quarters), `monthlyData` (260 months), chart specs for average area, demography, unemployment and yearly wages | 386,092 B (original 386,104 B) |
| `stats_gov_polska_20261030.rsc` | `/statystyki/polska/dane-rzadowe?_rsc` | 200 from the 2.0 build: as Wrocław without `citySlug` and without NBP rows (`nbp-grid` instead of `nbp`); monthly wages and monthly demography (`eurostat-demografia`) as chart specs | 625,422 B (original 625,434 B) |

## Provenance

Each file is one request made with the package's own client (`deweloperuch_mcp`, header `RSC: 1`, a deterministic `_rsc`):

- offers lists: 2026-10-10, while diagnosing a `search_offers` failure;
- government statistics: 2026-10-11, before `get_government_statistics` was built;
- developer profiles: 2026-10-13, before `get_developer` was built, for the contract and the consistency checks of `filteredStats` and `citiesStats` (`tests/contract/api/dto/test_developer_page_dto.py`), the unknown developer and the size of a result for the whole country.
- the four `*_20261030.rsc` files: 2026-10-30, after the redesign of 2026-10-29, with an empty `_rsc` (the deterministic token gets a 307 since then), to repair `search_offers`, `get_developer` and `get_government_statistics`.

Content:

- offers lists: offer data (prices, areas, investments, developers), JSON-LD and the page layout;
- statistics pages: GUS and NBP series, the table of contents, the list of locations, texts and JSON-LD in the model row (no `T` rows);
- developer profiles: the developer (name, empty `description` and `website`), its investments with their figures, the list of its offers (name, price, area, status; no personal data) and the daily change axis.

The only change from the original is the service's contact address in the page footer (row `0:`, which ends with `\n` and comes before any `T` rows). It was replaced with `"[usunięte]"`, as in the samples, which accounts for the 7-byte difference in the Size column (12 bytes in the `*_20261030.rsc` files, where the address sits in a model row in the middle of the stream, also ending with `\n`). No other personal data is present (e-mail addresses, phone numbers and `Person` entries were checked).

2.0 captures (`*_20261031.rsc`): 2026-10-31, after the recon of the same day (T63, T70) and before the 2.0 repairs of the tools, with the package's own client (`HttpClient`, header `RSC: 1` and an empty `_rsc`, as the package sends them since 2.0). Twelve requests in one sequential series through the shared limiter, together with the five `*_20261031.json` files of `tests/fixtures/api/`; no STOP before or after. Cloudflare served the pages from its cache (HIT, ages of 24 to 28 minutes) except the Karpacz transactions page and the developer page for Poland (MISS). In the ten files that have it, the service's contact address in the page footer (in a row that ends with `\n`, never in a `T` row) was replaced with `"[usunięte]"`, which accounts for the 12-byte difference in the Size column; the three unknown-entity pages have no footer address and are byte-exact. No other personal data is present (e-mail addresses, phone numbers and `email`, `phone`, `telefon` and `additionalInfo` values were checked by script).

## Rules

- Byte-exact: `T` row lengths count bytes, so never edit, reformat or re-save these files. The `.gitattributes` in this folder (`*.rsc -text`) stops git from converting line endings.
- Never overwrite a file. A new observation is a new file, described in the table above with its source, date and purpose.
- Captures are live requests to the service: keep them rare. Replace personal data only in rows that end with `\n`, never inside a `T` row, where the length prefix would no longer match.

## Used by

`tests/support/providers/rsc.py` (loading, `offers_payload`) and the routes in `tests/support/providers/routes/` (the default route of the offers list, the routes of the government statistics and of the developer profiles), and through them the contract, unit, integration, characterization, safeguards and recon_scripts tests. `grep -rl support.providers.rsc tests` lists the direct users.

The three developer pages `developer_ceres_warszawa_20261031.rsc`, `developer_dom_development_warszawa_20261031.rsc` and `developer_unknown_polska_20261031.rsc` came later the same day. They are a second series of three requests made the same way (no STOP), after the review of the `get_developer` repair asked three questions:
- how a single-city developer's page looks;
- how the chart writes counts of 1,000 or more;
- how the page for the whole country answers an unknown developer.

Both pages with a footer address had it replaced, which accounts for the 12-byte difference.

The four `*_20261030.rsc` files came with PR #15. No test reads them for now. They were merged in together with that PR, but its code for the three page tools was not taken: the 2.0 repairs bring their own code and add their tests on these files.

The `*_20261031.rsc` files are for the 2.0 repairs of `search_offers`, `get_developer`, `get_government_statistics` and `get_transaction_statistics`; each repair lists its users here.

- The shared core (`RscPage.props`, several props of one page in one request): `tests/unit/api/http/test_rsc_page.py` reads `offers_warszawa_20261031.rsc`, `offers_unknown_city_20261031.rsc`, `developer_atal_warszawa_20261031.rsc`, `stats_tx_warszawa_20261031.rsc` and `stats_tx_karpacz_20261031.rsc`; `tests/unit/test_flight.py` reads `developer_atal_warszawa_20261031.rsc` (the props of a client element nested in another's props). `tests/support/providers/rsc.py` names all twelve (`*_20261031`).
