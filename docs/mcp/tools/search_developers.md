# `search_developers`
> Znajduje deweloperów (rynek pierwotny) po fragmencie nazwy, np. atal albo dom development. Użyj, żeby zamienić nazwę dewelopera na developer_slug, którego wymaga get_developer (profil dewelopera; domyślnie dla całej Polski, city=polska). Nie zwraca ofert ani cen.
>
> Zwraca items (developer_slug, name, offer_count, czyli liczbę ofert dewelopera wg serwisu, i developer_url, czyli profil na deweloperuch.pl: podawaj go użytkownikowi jako link) oraz total, returned, truncated i hint. truncated=true znaczy, że pasujących deweloperów jest więcej niż pokazano: doprecyzuj nazwę albo zwiększ limit (najwyżej 20). total jest null, gdy wiadomo tylko, że jest ich więcej.

Title: „Szukaj deweloperów”. Annotations: `readOnlyHint=true`, `openWorldHint=true`. Shared rules: [MCP overview](../README.md).

## Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | yes | — | „Fragment nazwy dewelopera, 2–100 znaków, np. atal, Dom Development.” |
| `limit` | integer 1-20 | no | `5` | „Najwięcej deweloperów w wyniku, domyślnie 5, najwyżej 20. Każdy to ok. 150 znaków wyniku.” |

## Result
A structured result and the same compact JSON in the content; `null` fields are omitted.

| Field | Type | Description |
|---|---|---|
| `total` | integer or `null` | All matching developers; `null` when only "more than shown" is known. |
| `returned`, `truncated` | integer, boolean | Items returned; `true` when there are more matches than shown. |
| `hint` | string | When truncated or nothing matched (optional). |
| `items` | array | `developer_slug`, `name`, `offer_count` (offers of the developer according to the service), `developer_url` (the profile on deweloperuch.pl: give it to the user as a link). |

## Data limitations
- `offer_count` is the service's figure for the whole country; `get_developer` can narrow a profile to one city.
- The `developer_slug` returned here is the one `get_developer`, `search_investments` and the `developer_slug` fields of other results use.
- Channel and limits: [endpoints.md](../../discovery/endpoints.md), [open-questions.md](../../open-questions.md).

## Errors
| Situation | Message |
|---|---|
| `name` shorter than 2 or longer than 100 characters | `name: podaj od 2 do 100 znaków nazwy dewelopera, podano 'a'.` |
| `name` missing | `Błędny argument narzędzia search_developers: name: brak wymaganego argumentu. Popraw i ponów; nic nie zostało wysłane.` |
| `limit` outside 1-20 | `Błędny argument narzędzia search_developers: limit musi być liczbą całkowitą z zakresu 1–20, podano 21. Popraw i ponów; nic nie zostało wysłane.` |
| Unknown argument | `Nieznany argument narzędzia search_developers: '…'. Dozwolone argumenty: name, limit. Popraw nazwy i ponów; nic nie zostało wysłane.` |
| Nothing matches | Not an error: `returned=0` and a `hint`. |
| STOP, service error | As in the [MCP overview](../README.md#errors); a service error: `Wyszukiwanie deweloperów: Serwis odpowiedział błędem HTTP 500. Nic nie ponawiam; spróbuj później.` |

## Example
Call:

```json
{"name": "search_developers", "arguments": {"name": "atal"}}
```

The result from `tests/golden/mcp/developers.json`:

```json
{"total": 1, "returned": 1, "truncated": false, "items": [{"developer_slug": "atal", "name": "ATAL S.A.", "offer_count": 4265, "developer_url": "https://deweloperuch.pl/ceny-ofertowe/polska/deweloperzy/atal"}]}
```

_Source: `src/deweloperuch_mcp/consumers/mcp/tools/search_developers_tool.py`, `src/deweloperuch_mcp/consumers/mcp/presenters/search_developers_mcp_presenter.py`, `src/deweloperuch_mcp/usecases/search_developers.py`, `tests/snapshots/mcp_tools.json`_
