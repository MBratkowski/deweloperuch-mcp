# `get_investment`
> Zwraca inwestycję (projekt deweloperski): miasto, ulicę, współrzędne, dewelopera, średnie ceny aktywnych ofert, liczbę ofert i listę ofert (najpierw aktywne, potem archiwalne). Użyj, gdy chcesz zobaczyć mieszkania jednego projektu. investment_slug podaje search_offers. investment_url i developer_url to strony inwestycji i dewelopera na deweloperuch.pl: podawaj je użytkownikowi jako linki.
>
> Ograniczenia: zwraca najwyżej limit ofert (domyślnie 20); offers_returned mówi, ile ich jest na liście, truncated i offers_omitted, czy i ile pominięto. offers_total to liczba z serwisu, a pominięte oferty liczy offers_omitted. Przy dużej inwestycji nie zwiększaj limitu bez potrzeby; offers_omitted > 0 znaczy, że lista jest niepełna. include_history=true dodaje historię ceny każdej zwróconej oferty: wynik jest dłuższy i powstaje wolniej. Dla jednej oferty lepiej użyć get_offer.

Tytuł: „Inwestycja z ofertami”. Adnotacje: `readOnlyHint=true`, `openWorldHint=true`. Zasady wspólne: [przegląd MCP](../README.md).

## Parametry
| Nazwa | Typ | Wymagany | Domyślna | Opis |
|---|---|---|---|---|
| `investment_slug` | string | tak | — | investment_slug z search_offers, np. smolna. |
| `include_history` | boolean | nie | `false` | true: dołącz historię ceny każdej zwróconej oferty (dłuższy wynik). `null` = `false`. |
| `limit` | integer 0–200 | nie | `20` | Najwięcej ofert w wyniku (najpierw aktywne), domyślnie 20, 0 = tylko podsumowanie inwestycji. Ile pominięto, mówi offers_omitted. Każda oferta to ok. 300 znaków wyniku, z historią ceny kilkaset więcej. Maksimum 200 daje ok. 60 tys. znaków; zwykle wystarcza domyślne 20. `null` = 20. |

## Wynik
Wynik strukturalny i ten sam kompaktowy JSON w treści; pola `null` są pomijane.

| Pole | Typ | Opis |
|---|---|---|
| `investment_slug`, `name`, `status`, `city`, `city_slug`, `developer` | | Zawsze (`developer`: `developer_slug`, `name`, opcjonalnie `website`, `description`). |
| `street`, `lat`, `lng`, `currency` | | Opcjonalne. |
| `investment_url`, `developer_url` | string | Strona inwestycji i profil dewelopera na deweloperuch.pl: podaj je użytkownikowi jako linki (opcjonalne; brak sluga oznacza brak pola). Pozycje `offers` nie mają linków. Zasady: D12 w [decisions.md](../../decisions.md). |
| `avg_price`, `avg_area_m2`, `avg_price_per_m2`, `offers_active` | | Opcjonalne; średnie dotyczą aktywnych ofert (cena w PLN). |
| `offers_total` | integer | Wszystkie oferty inwestycji wg serwisu, także archiwalne; lista `offers` jest ucięta przez `limit`. |
| `offers` | tablica | Oferty (najpierw aktywne): `offer_id`, `name`, `status`; opcjonalnie `price`, `currency`, `area_m2`, `price_per_m2`, `price_change_since_start`, `price_change_since_start_pct`, `creation_date`, `last_event_date`, `last_change_date` i z `include_history=true` `price_history` (`kind`: `offer` – cena w ofercie, `archived`, `restored`). |
| `offers_returned` | integer | Ofert na liście `offers`. |
| `offers_omitted` | integer | Ofert pominiętych przez `limit`. |
| `truncated` | boolean | `true`: lista `offers` jest niepełna (`offers_omitted` > 0). |

Rozmiary (kompaktowy JSON, z linkami): 20 (domyślnie) ok. 6 400 znaków, 200 ok. 58 100.

## Ograniczenia danych
- `limit` max 200 (MCP); CLI `investments get` bez `--limit` pokazuje wszystkie oferty.
- `include_history=true` to dodatkowe zapytanie do serwisu (wolniejsze, gdy nie ma go w cache).
- `kind: offer` to każdy wpis ceny ofertowej w historii (pierwsza cena i każda zmiana) [P 2026-10-10]; zob. [entities.md](../../discovery/entities.md), [open-questions.md](../../open-questions.md).
- Ceny ofertowe, nie transakcyjne.

## Błędy
| Sytuacja | Komunikat |
|---|---|
| Inwestycja nie istnieje | `Nie znaleziono inwestycji '<slug>'. Slug inwestycji podaje search_offers (pole investment_slug).` |
| Brak historii cen (z `include_history`) | `Serwis nie ma historii cen ofert inwestycji '<slug>'. Pobierz inwestycję bez include_history, a historię pojedynczej oferty przez get_offer.` |
| Zły `investment_slug` | `investment_slug: oczekiwano slug inwestycji, np. smolna; podaje go search_offers (investment_slug); podano '…'.` |
| `limit` poza 0–200, `include_history` nie boolean | Błąd walidacji schematu z SDK (angielski, prefiks „Error executing tool …”) |
| STOP, błąd serwisu | Jak w [przeglądzie MCP](../README.md#błędy); błędy serwisu z przedrostkiem `Inwestycja '<slug>': …` |

## Przykład
Wywołanie:

```json
{"name": "get_investment", "arguments": {"investment_slug": "smolna", "limit": 1}}
```

Wynik z mocka testów (próbka `api.map_inv_visible`):

```json
{
  "investment_slug": "smolna",
  "name": "Smolna",
  "status": "active",
  "investment_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna",
  "city": "Sopot",
  "city_slug": "sopot",
  "street": "Świemirowo",
  "lat": 54.42735985,
  "lng": 18.55839032,
  "currency": "PLN",
  "developer": {"developer_slug": "invest-komfort-spolka-akcyjna", "name": "Invest Komfort Spółka Akcyjna Sp.K."},
  "developer_url": "https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna",
  "avg_price": 1566392.0,
  "avg_area_m2": 63.97,
  "avg_price_per_m2": 24487.63,
  "offers_active": 3,
  "offers_total": 16,
  "offers": [
    {"offer_id": 206087, "name": "C234", "status": "active", "price": 1679796.0, "currency": "PLN", "area_m2": 65.9, "price_per_m2": 25490.08, "price_change_since_start": 0.0, "price_change_since_start_pct": 0.0, "creation_date": "2026-10-03", "last_event_date": "2026-10-03", "last_change_date": "2026-10-03"}
  ],
  "offers_returned": 1,
  "offers_omitted": 2,
  "truncated": true
}
```

(Próbka ma 3 oferty, `offers_total` 16 pochodzi z danych inwestycji w próbce.)

_Źródło: `src/deweloperuch_mcp/mcp_server.py`, `src/deweloperuch_mcp/mcp_results.py`, `src/deweloperuch_mcp/services.py`, `tests/snapshots/mcp_tools.json`_
