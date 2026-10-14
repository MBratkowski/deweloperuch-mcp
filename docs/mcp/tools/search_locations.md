# `search_locations`
> Znajduje miasta, dzielnice i ulice w Polsce po fragmencie nazwy. Użyj na początku, żeby zamienić nazwę miejsca na city_slug, którego wymaga search_offers. Nie zwraca ofert ani cen.
>
> Zwraca items (kind: city, district albo street; name, city, city_slug, opcjonalnie district, street, lat, lng i offer_count, czyli liczbę ofert wg serwisu) oraz total, returned, truncated i hint. total jest null, gdy wyników jest więcej niż pokazano; truncated=true znaczy, że pasujących może być więcej: doprecyzuj nazwę. Miejscowości z offer_count=0 nie mają ofert: nie przekazuj ich do search_offers. Dzielnica i ulica podają city_slug swojego miasta. Nazwę dzielnicy (kind=district, pole name) przekaż do search_offers jako district razem z tym city_slug; po ulicy search_offers nie filtruje.

Title: „Szukaj lokalizacji”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Rules shared by all tools (argument rules, errors, sizes): [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | yes | — | A fragment of a city, district or street name, 2-100 characters, with Polish characters. Schema text: „Fragment nazwy miasta, dzielnicy lub ulicy, 2–100 znaków, z polskimi znakami, np. Kraków, Mokotów.” The schema has no `pattern` or `minLength`: the length range is checked by the service, which returns a Polish message. |

## Result
A structured result (`structuredContent`, matching `outputSchema`) and the same JSON in the content (compact). `null` fields are omitted, except `total`.

| Field | Type | Description |
|---|---|---|
| `total` | integer or `null` | All matches; `null` when there are more results than shown. Always present. |
| `returned` | integer | The number of entries in `items`. |
| `truncated` | boolean | `true`: there may be more matches, refine the name. |
| `hint` | string | A hint when the result is truncated (optional). |
| `items` | array | Entries (below). |

An `items` entry: `kind` (`city`, `district`, `street`), `name`, `city`, `city_slug` (always); `district`, `street`, `lat`, `lng` (optional); `offer_count` (optional: the number of offers according to the service, 0 = no offers; exact for districts, approximate for streets and cities).

## Data limitations
- `offer_count` for districts is the number of active offers; for streets and cities it is inferred, not directly verified, hence "approximate". The `truncated` flag is a heuristic as well; that is why the description says "there may be more". See [endpoints.md](../../discovery/endpoints.md), section `location-search`.
- A district and a street give the `city_slug` of their city. To narrow `search_offers` to a district, pass the district's `name` (`kind=district`) as its `district` argument together with that `city_slug` (streets are not filtered); `get_building` and `estimate_property_value` can use the `lat`/`lng` of a street or district as an approximate point.

## Errors
An error is a result with `isError=true` and a Polish message (technical details only in the server log). Shared rules, including STOP: [MCP overview](../README.md#errors).

| Situation | Message |
|---|---|
| `query` shorter than 2 or longer than 100 characters (after trimming), not a string | `query: podaj od 2 do 100 znaków nazwy miasta, dzielnicy lub ulicy, podano '…'.` |
| Missing `query` argument, wrong type | `Błędny argument narzędzia search_locations: query: brak wymaganego argumentu. Popraw i ponów; nic nie zostało wysłane.` (Polish; a wrong type: `… query musi być tekstem, podano 42 …`) |
| Unknown argument | `Nieznany argument narzędzia search_locations: '…'. Dozwolone argumenty: query. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| STOP (401/403/429/challenge, also written by another process) | `STOP: HTTP 403 (odmowa dostępu). Klient nie wyśle już żadnego zapytania; inne procesy też zostały wstrzymane. Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.` (other variants: [MCP overview](../README.md#errors)) |
| Nothing matches | Not an error: a result with `returned=0` and `hint`: `Nic nie pasuje do '…'. Sprawdź pisownię (z polskimi znakami) albo podaj początek nazwy miasta, dzielnicy lub ulicy.` |
| Service error (5xx, network) | e.g. `Wyszukiwanie miast: Serwis odpowiedział błędem HTTP 500. Nic nie ponawiam; spróbuj później.` |

## Example
Call:

```json
{"name": "search_locations", "arguments": {"query": "krak"}}
```

The `structuredContent` result (`tests/golden/mcp/locations.json`; the mock does not filter by `query`: the district and street entries with Mokotów are responses from samples, not matches for "krak"; coordinates shortened):

```json
{
  "total": 5,
  "returned": 5,
  "truncated": false,
  "items": [
    {"kind": "city", "name": "Kraków", "city": "Kraków", "city_slug": "krakow", "offer_count": 8082},
    {"kind": "city", "name": "Krakowiany", "city": "Krakowiany", "city_slug": "krakowiany", "offer_count": 0},
    {"kind": "city", "name": "Krakulice", "city": "Krakulice", "city_slug": "krakulice", "offer_count": 0},
    {"kind": "district", "name": "Mokotów", "city": "Warszawa", "city_slug": "warszawa", "district": "Mokotów", "lat": 52.19, "lng": 21.05, "offer_count": 1562},
    {"kind": "street", "name": "Mokotów", "city": "Warszawa", "city_slug": "warszawa", "district": "Mokotów", "street": "Mokotów", "lat": 52.19, "lng": 21.04, "offer_count": 191}
  ]
}
```

Size: about 680 characters.

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/search_locations_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/search_locations_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/search_locations.py`, `tests/snapshots/mcp_tools.json`_
