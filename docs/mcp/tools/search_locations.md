# `search_locations`
> Znajduje miasta, dzielnice i ulice w Polsce po fragmencie nazwy. Użyj na początku, żeby zamienić nazwę miejsca na city_slug, którego wymaga search_offers. Nie zwraca ofert ani cen.
>
> Zwraca items (kind: city, district albo street; name, city, city_slug, opcjonalnie district, street, lat, lng i offer_count, czyli liczbę ofert wg serwisu) oraz total, returned, truncated i hint. total jest null, gdy wyników jest więcej niż pokazano; truncated=true znaczy, że pasujących może być więcej: doprecyzuj nazwę. Miejscowości z offer_count=0 nie mają ofert: nie przekazuj ich do search_offers. Dzielnica i ulica podają city_slug swojego miasta; search_offers filtruje tylko po mieście.

Tytuł: „Szukaj lokalizacji”. Adnotacje: `readOnlyHint=true`, `openWorldHint=true`. Zasady wspólne dla wszystkich narzędzi (reguły argumentów, błędy, rozmiary): [przegląd MCP](../README.md).

## Parametry
| Nazwa | Typ | Wymagany | Domyślna | Opis |
|---|---|---|---|---|
| `query` | string | tak | — | Fragment nazwy miasta, dzielnicy lub ulicy, 2–100 znaków, z polskimi znakami, np. Kraków, Mokotów. Schemat nie ma `pattern` ani `minLength`: zakres długości sprawdza usługa i zwraca polski komunikat. |

## Wynik
Wynik strukturalny (`structuredContent`, zgodny z `outputSchema`) i ten sam JSON w treści (kompaktowy). Pola `null` są pomijane, poza `total`.

| Pole | Typ | Opis |
|---|---|---|
| `total` | integer albo `null` | Wszystkie pasujące; `null`, gdy wyników jest więcej niż pokazano. Zawsze obecne. |
| `returned` | integer | Liczba pozycji w `items`. |
| `truncated` | boolean | `true`: pasujących może być więcej, doprecyzuj nazwę. |
| `hint` | string | Wskazówka, gdy wynik jest obcięty (opcjonalna). |
| `items` | tablica | Pozycje (poniżej). |

Pozycja `items`: `kind` (`city`, `district`, `street`), `name`, `city`, `city_slug` (zawsze); `district`, `street`, `lat`, `lng` (opcjonalne); `offer_count` (opcjonalne: liczba ofert wg serwisu, 0 = brak ofert; dla dzielnic dokładna, dla ulic i miast przybliżona).

## Ograniczenia danych
- `offer_count` dla dzielnic to liczba aktywnych ofert [P 2026-10-10]; dla ulic i miast nadal [W] (wniosek bez bezpośredniego testu, T32), stąd „przybliżona”. Heurystyka `truncated` także [W]; dlatego opis mówi „może być więcej”. Zob. [endpoints.md](../../discovery/endpoints.md), sekcja `location-search`.
- Tylko miasto daje `city_slug` do `search_offers`; dzielnica i ulica podają slug swojego miasta, a `search_offers` nie filtruje po dzielnicy.

## Błędy
Błąd to wynik z `isError=true` i polskim komunikatem (szczegóły techniczne tylko w logu serwera). Wspólne zasady, w tym STOP: [przegląd MCP](../README.md#błędy).

| Sytuacja | Komunikat |
|---|---|
| `query` krótsze niż 2 albo dłuższe niż 100 znaków (po przycięciu), nie tekst | `query: podaj od 2 do 100 znaków nazwy miasta, dzielnicy lub ulicy, podano '…'.` |
| Brak argumentu `query`, zły typ | Błąd walidacji schematu z SDK (angielski, prefiks „Error executing tool …”) |
| STOP (401/403/429/challenge, także zapisany przez inny proces) | `STOP: HTTP 403 (odmowa dostępu). Klient nie wyśle już żadnego zapytania; inne procesy też zostały wstrzymane. Przerwij, niczego nie ponawiaj i zgłoś to użytkownikowi.` (pozostałe warianty: [przegląd MCP](../README.md#błędy)) |
| Nic nie pasuje | Nie błąd: wynik z `returned=0` i `hint`: `Nic nie pasuje do '…'. Sprawdź pisownię (z polskimi znakami) albo podaj początek nazwy miasta, dzielnicy lub ulicy.` |
| Błąd serwisu (5xx, sieć) | np. `Wyszukiwanie miast: Serwis odpowiedział błędem HTTP 500. Nic nie ponawiam; spróbuj później.` |

## Przykład
Wywołanie:

```json
{"name": "search_locations", "arguments": {"query": "krak"}}
```

Wynik `structuredContent` (mock nie filtruje po `query`: pozycje dzielnicy i ulicy z Mokotowem to odpowiedzi z próbek, nie dopasowania do „krak”; odpowiedzi z próbek `docs/discovery/samples/` podstawione do mocków testów, `tests/service_mocks.py`; współrzędne skrócone):

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

Rozmiar: ok. 680 znaków.

_Źródło: `src/deweloperuch_mcp/mcp_server.py`, `src/deweloperuch_mcp/mcp_results.py`, `tests/snapshots/mcp_tools.json`_
