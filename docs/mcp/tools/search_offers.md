# `search_offers`
> Wyszukuje oferty mieszkań od deweloperów (tylko rynek pierwotny, ceny ofertowe, nie transakcyjne) w jednym mieście albo w całej Polsce (city=polska), z filtrami ceny i metrażu i sortowaniem po cenie. Użyj, gdy szukasz mieszkań w budżecie albo o danym metrażu. Nie filtruje po dzielnicy, liczbie pokoi ani deweloperze.
>
> Zwraca jedną stronę: total (wszystkie pasujące), returned, page, per_page, pages_available, truncated, hint, list_url i items (offer_id, investment_slug, investment_url (strona inwestycji, nie pojedynczej oferty), name, cena w PLN, metraż w m², cena za m², status, inwestycja, deweloper, ostatnia zmiana ceny i zmiana od pierwszej ceny w procentach; miasto tylko przy city=polska). Pozycje są skrócone; szczegóły oferty i historię ceny daje get_offer. list_url to link „zobacz wszystkie na deweloperuch.pl” z tymi samymi filtrami: przydatny, gdy truncated=true albo użytkownik chce więcej ofert. Linki podawaj użytkownikowi, np. w tabeli ofert.
>
> Ograniczenia: można przejrzeć najwyżej 20 stron po per_page ofert. Gdy truncated=true, zawęź filtry zamiast przeglądać kolejne strony. Wszystkie oferty jednej inwestycji daje get_investment.

Tytuł: „Szukaj ofert mieszkań”. Adnotacje: `readOnlyHint=true`, `openWorldHint=true`. Zasady wspólne (reguły argumentów, błędy, rozmiary): [przegląd MCP](../README.md).

## Parametry
| Nazwa | Typ | Wymagany | Domyślna | Opis |
|---|---|---|---|---|
| `city` | string | tak | — | city_slug miasta z search_locations (np. warszawa, krakow) albo polska dla całego kraju. |
| `price_min` | integer 0–99 999 999 | nie | brak | Najniższa cena oferty w PLN. |
| `price_max` | integer 0–99 999 999 | nie | brak | Najwyższa cena oferty w PLN. |
| `area_min` | integer 0–9 999 | nie | brak | Najmniejszy metraż w m². |
| `area_max` | integer 0–9 999 | nie | brak | Największy metraż w m². |
| `sort` | `price_asc` \| `price_desc` | nie | brak | price_asc: od najtańszych, price_desc: od najdroższych; brak: domyślna kolejność serwisu (nie jest gwarantowana). |
| `page` | integer 1–20 | nie | `1` | Numer strony wyników, 1–20. |
| `per_page` | `10` \| `50` | nie | `10` | 10 albo 50. Pozycja to ok. 450 znaków wyniku (z linkiem), więc 50 daje ok. 22 tys.; zwykle wystarcza 10. |

Reguły argumentów (liczby jako tekst z samych cyfr, `""`/`null`, przycinanie `sort`): [przegląd MCP](../README.md#reguły-argumentów). `price_min` większe niż `price_max` (analogicznie metraż) to błąd walidacji usługi.

## Wynik
Wynik strukturalny i ten sam kompaktowy JSON w treści; pola `null` są pomijane.

| Pole | Typ | Opis |
|---|---|---|
| `total` | integer | Wszystkie pasujące oferty. |
| `returned` | integer | Pozycji na tej stronie. |
| `truncated` | boolean | `true`: pasujących ofert jest więcej, niż można przejrzeć (najwyżej 20 stron); zawęź filtry. |
| `page`, `per_page`, `pages_available` | integer | Strona, jej rozmiar i liczba stron możliwych do przejrzenia. |
| `hint` | string | Przy obcięciu: ile ofert pasuje, ile stron po ile można przejrzeć i rada, żeby zawęzić filtry (opcjonalne). |
| `list_url` | string | Ta lista ofert na deweloperuch.pl (te same filtry, sortowanie i strona): podaj ją użytkownikowi jako link (opcjonalne). |
| `items` | tablica | Pozycje skrócone. |

Pozycja: `offer_id`, `investment_slug`, `name`, `status` (`active` albo `archived`), `investment_name`, `developer_name` (zawsze); `investment_url` (strona inwestycji na deweloperuch.pl, nie pojedynczej oferty: podaj ją użytkownikowi jako link; brak sluga oznacza brak pola), `price` (PLN, cena ofertowa), `area_m2`, `price_per_m2`, `last_price_change_kind` (`increase`, `decrease`, `no_change`), `last_price_change_pct`, `price_change_since_start_pct` (ujemna = tańsza) (opcjonalne); `city`, `city_slug` tylko przy `city=polska`.

Rozmiary (pełne strony z próbek, z linkami): 10 pozycji ok. 4 500 znaków, 50 ok. 21 200, 50 przy `polska` ok. 23 300.

Linki (`*_url`): tylko trzy wzorce stron potwierdzone [P], bez `_rsc` i `/api/`, bez linku do pojedynczej oferty (jej strona nie jest potwierdzona). Zasady: D12 w [decisions.md](../../decisions.md).

## Ograniczenia danych
- Można przejrzeć najwyżej 20 stron (`page` 1–20) po `per_page` ofert; reszta jest nieosiągalna, trzeba zawęzić filtry. Zob. [pages-rsc.md](../../discovery/pages-rsc.md), „Wspólne reguły list”.
- `per_page` w MCP to 10 i 50 ([P] w pages-rsc.md); CLI przyjmuje także 100.
- Maksima `price_*` (99 999 999 PLN) i `area_*` (9 999 m²) to wartownicy zakresu [P z kodu] klienta serwisu, nie dane o rynku.
- Sortowanie po cenie (`amount`, rosnąco i malejąco) jest potwierdzone [P 2026-10-10]; bez `sort` serwis sortuje rosnąco po identyfikatorze oferty, a nieznana wartość sortowania nie daje błędu (T3 w [open-questions.md](../../open-questions.md)).
- Ceny ofertowe z rynku pierwotnego, nie transakcyjne.

## Błędy
| Sytuacja | Komunikat |
|---|---|
| `price_min` > `price_max` | `price_min (7) jest większe niż price_max (5); zamień je miejscami.` (analogicznie `area_`) |
| Liczba poza zakresem | `<pole> musi być liczbą całkowitą z zakresu <od>–<do> …, podano <wartość>.` (lub błąd schematu z SDK) |
| Nieznane miasto (slug poprawny, ale nieznany serwisowi) | `Serwis nie zna miasta '<city>'. Podaj city_slug z search_locations albo polska (cały kraj).` |
| Zły `city`: nazwa zamiast sluga (np. `Warszawa`, `Kraków`), wielkie litery, pusty tekst | `city: oczekiwano slug miasta (np. warszawa) albo polska; slug podaje search_locations; podano '…'.` Bez zapytania do serwisu; spacje na brzegach są przycinane, slug to małe litery ASCII, cyfry i myślniki. |
| `sort`/`per_page` spoza listy | Błąd walidacji schematu z SDK (angielski, prefiks „Error executing tool …”) |
| STOP, błąd serwisu | Jak w [przeglądzie MCP](../README.md#błędy); błędy serwisu z przedrostkiem `Wyszukiwanie ofert w '<city>': …` |

## Przykład
Wywołanie (domyślne `per_page` 10, bez filtrów):

```json
{"name": "search_offers", "arguments": {"city": "warszawa"}}
```

Wynik z mocka testów (`tests/service_mocks.offers_page(count=10)`): pozycje są kopiami ofert z próbki `page.offers_list` z syntetycznymi `offer_id` (900000+), a `total` pochodzi z próbki. Pokazano 2 pierwsze pozycje z 10, pozostałe 8 pominięto:

```json
{
  "total": 13324,
  "returned": 10,
  "truncated": true,
  "page": 1,
  "per_page": 10,
  "pages_available": 20,
  "hint": "Pasujących ofert jest 13324, a można przejrzeć najwyżej 20 stron po 10 (200). Zawęź filtry (cena, metraż).",
  "list_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/mieszkania?page=1&perPage=10",
  "items": [
    {"offer_id": 900000, "investment_slug": "nowy-targowek-vi", "name": "D1.1.1.4", "price": 994012.0, "area_m2": 55.25, "price_per_m2": 17991.17, "status": "active", "investment_name": "Nowy Targówek VI", "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi", "developer_name": "ATAL S.A.", "last_price_change_kind": "increase", "last_price_change_pct": 5.89, "price_change_since_start_pct": -0.6},
    {"offer_id": 900001, "investment_slug": "nowy-targowek-vi", "name": "D1.2.0.1", "price": 659315.0, "area_m2": 36.49, "price_per_m2": 18068.37, "status": "active", "investment_name": "Nowy Targówek VI", "investment_url": "https://deweloperuch.pl/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi", "developer_name": "ATAL S.A.", "last_price_change_kind": "decrease", "last_price_change_pct": -3.21, "price_change_since_start_pct": -4.45}
  ]
}
```

_Źródło: `src/deweloperuch_mcp/mcp_server.py`, `src/deweloperuch_mcp/mcp_results.py`, `src/deweloperuch_mcp/services.py`, `tests/snapshots/mcp_tools.json`_
