# Raw RSC payloads

Complete `text/x-component` response bodies of three kinds of the service's pages (the offers list, the government statistics and a developer's profile), exactly as served. The samples in `docs/discovery/samples/page.*.json` keep only the value of one prop; these files hold the whole flight stream, including text rows `<id>:T<hex length in bytes>,<text>` that are not followed by a newline.

| File | Request target | Response | Size |
|---|---|---|---|
| `warszawa_perPage10.rsc` | `/ceny-ofertowe/warszawa/mieszkania?perPage=10&_rsc=fe86badc` | 200, `initialData` with 10 offers (`total` 13,324). Right before the data row are the rows `16:T5ed,` and `19:T1a27,` with JSON-LD | 46,652 B (original 46,659 B) |
| `unknown_city_perPage10.rsc` | `/ceny-ofertowe/nieistniejace-miasto/mieszkania?perPage=10&_rsc=4b97e1e1` | 200 without `initialData`, with the error row `f:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}` | 26,796 B (original 26,803 B) |
| `stats_gov_polska.rsc` | `/statystyki/statystyki-rzadowe/polska?_rsc=b3d11c70` | 200 without the 404 digest: `tocItems`, `sortedLocations` (69), `currentSlug: null`, `data` ×6, `monthlyData`, the NBP price grid of cities (`seriesList`, `tableRows`) without an NBP series for Poland itself | 415,697 B (original 415,704 B) |
| `stats_gov_warszawa.rsc` | `/statystyki/statystyki-rzadowe/warszawa?_rsc=cc0b509c` | 200 without the 404 digest: `tocItems`, `sortedLocations` (69), `currentSlug: "warszawa"`, `data` ×7 (with NBP prices), `monthlyData` | 286,578 B (original 286,585 B) |
| `developer_atal_warszawa.rsc` | `/ceny-ofertowe/warszawa/deweloperzy/atal?_rsc=682178ac` | 200: the object prop `data` (`developer`, `investments` ×4, `filteredStats` with `totalProjects` 4, `totalSales` 69, `totalCities` 1, `allCities`, `allCitiesWithSlugs` as a `$f:…` reference, `citiesStats` ×14, `allInvestmentNames`), `sale` ×227 (active and archived), `data` as a list (the daily change axis) | 134,532 B (original 134,539 B) |
| `developer_atal_polska.rsc` | `/ceny-ofertowe/polska/deweloperzy/atal?_rsc=b92176ca` | 200: the same shape for the whole country: `investments` ×42, `filteredStats` with `totalProjects` 42, `totalSales` 4,078, `totalCities` 14, `sale` ×6,587 | 1,956,906 B (original 1,956,913 B) |
| `developer_unknown_warszawa.rsc` | `/ceny-ofertowe/warszawa/deweloperzy/nieistniejacy-deweloper?_rsc=448d0288` | 200 without developer data and **without** the 404 digest (unlike the offers list); row `f` renders `h1` „Deweloper nie znaleziony” and `p` „Nie znaleziono dewelopera o podanym adresie”, and the title (row `13`) is „Deweloper nie znaleziony \| Deweloperuch” [P 2026-10-13] | 27,663 B (original 27,670 B) |

## Provenance

Each file is one request made with the package's own client (`deweloperuch_mcp`, header `RSC: 1`, a deterministic `_rsc`):

- offers lists: 2026-10-10, while diagnosing a `search_offers` failure;
- government statistics: 2026-10-11, before `get_government_statistics` was built;
- developer profiles: 2026-10-13, before `get_developer` was built, for the contract and the consistency checks of `filteredStats` and `citiesStats` (`tests/contract/api/dto/test_developer_page_dto.py`), the unknown developer and the size of a result for the whole country.

Content:

- offers lists: offer data (prices, areas, investments, developers), JSON-LD and the page layout;
- statistics pages: GUS and NBP series, the table of contents, the list of locations, texts and JSON-LD in the model row (no `T` rows);
- developer profiles: the developer (name, empty `description` and `website`), its investments with their figures, the list of its offers (name, price, area, status; no personal data) and the daily change axis.

The only change from the original is the service's contact address in the page footer (row `0:`, which ends with `\n` and comes before any `T` rows). It was replaced with `"[usunięte]"`, as in the samples, which accounts for the 7-byte difference in the Size column. No other personal data is present (e-mail addresses, phone numbers and `Person` entries were checked).

## Rules

- Byte-exact: `T` row lengths count bytes, so never edit, reformat or re-save these files. The `.gitattributes` in this folder (`*.rsc -text`) stops git from converting line endings.
- Never overwrite a file. A new observation is a new file, described in the table above with its source, date and purpose.
- Captures are live requests to the service: keep them rare. Replace personal data only in rows that end with `\n`, never inside a `T` row, where the length prefix would no longer match.

## Used by

`tests/support/providers/rsc.py` (loading, `offers_payload`) and the routes in `tests/support/providers/routes/` (the default route of the offers list, the routes of the government statistics and of the developer profiles), and through them the contract, unit, integration, characterization, safeguards and recon_scripts tests. `grep -rl support.providers.rsc tests` lists the direct users.
