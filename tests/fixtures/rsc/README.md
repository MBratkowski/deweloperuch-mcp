# Raw RSC responses (test fixtures)

Whole `text/x-component` response bodies of the service's pages (the offers list, the government statistics), exactly as the service sent them. The samples in `docs/discovery/samples/page.*.json` hold only the value of one prop; here is the whole flight stream, with text rows `<id>:T<hex length in bytes>,<text>` that are not followed by a newline.

| File | Request target | Response | Size |
|---|---|---|---|
| `warszawa_perPage10.rsc` | `/ceny-ofertowe/warszawa/mieszkania?perPage=10&_rsc=fe86badc` | 200, `initialData` with 10 offers (`total` 13,324). Right before the data row are the rows `16:T5ed,` and `19:T1a27,` with JSON-LD | 46,652 B (original 46,659 B) |
| `unknown_city_perPage10.rsc` | `/ceny-ofertowe/nieistniejace-miasto/mieszkania?perPage=10&_rsc=4b97e1e1` | 200 without `initialData`, with the error row `f:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}` | 26,796 B (original 26,803 B) |
| `stats_gov_polska.rsc` | `/statystyki/statystyki-rzadowe/polska?_rsc=b3d11c70` | 200 without the 404 digest: `tocItems`, `sortedLocations` (69), `currentSlug: null`, `data` ×6, `monthlyData`, the NBP price grid of cities (`seriesList`, `tableRows`) without an NBP series of Poland itself | 415,697 B (original 415,704 B) |
| `stats_gov_warszawa.rsc` | `/statystyki/statystyki-rzadowe/warszawa?_rsc=cc0b509c` | 200 without the 404 digest: `tocItems`, `sortedLocations` (69), `currentSlug: "warszawa"`, `data` ×7 (with NBP prices), `monthlyData` | 286,578 B (original 286,585 B) |

- Source: the package's client (`deweloperuch_mcp`, header `RSC: 1`, a deterministic `_rsc`), one request per file.
  - The offers lists were fetched by the main thread on 2026-10-10 while diagnosing the `search_offers` failure.
  - The government statistics pages were fetched by the main thread on 2026-10-11, with the user's consent, before `get_government_statistics` was built.
- Content of the offers lists: offer data (prices, areas, investments, developers), JSON-LD and the page layout. Content of the statistics pages: GUS and NBP series, the table of contents, the list of locations, texts and JSON-LD in the model row (no `T` rows).
- The only change from the original is the service's contact address in the footer (row `0:`, ending with `\n`, before the `T` rows, if there are any). It was replaced with `"[usunięte]"` according to the samples rule. There is no other personal data there (e-mails, phone numbers and `Person` were checked).
- `T` row lengths count bytes, so the files must stay untouched byte for byte. `.gitattributes` turns off line-ending conversion. A new observation is a new file; existing ones are not overwritten.
- Used by `tests/rsc_fixtures.py`, `tests/service_mocks.py` (the default route of the offers list, the routes of the government statistics) and by the tests in `tests/test_flight.py`, `test_client_adapters.py`, `test_client_statistics.py`, `test_services.py`, `test_params.py`, `test_cli.py`, `test_mcp_server.py`, `test_golden_cli.py`, `test_golden_mcp.py`, `test_e2e_gate.py` and `test_probe.py`.
