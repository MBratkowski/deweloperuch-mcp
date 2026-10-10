# Testy e2e na żywym serwisie

Zestaw sprawdza zainstalowany pakiet na prawdziwym deweloperuch.pl: serwer MCP przez stdio z oficjalnym klientem SDK, CLI i `recon/probe.py`. Domyślnie jest **wyłączony**.

## Zanim uruchomisz

- Przebieg to seria żywych zapytań. Dopóki U1 nie jest rozstrzygnięte, wymaga jawnej zgody użytkownika w bieżącej rozmowie (D9; wyjątek dla tego zestawu opisuje D10). Nie uruchamiaj go równolegle z `recon-verifier` ani `drift-checker`.
- Zestaw nie ustawia prywatnego `XDG_CACHE_HOME`: korzysta z limitera i zapisu STOP z twojego środowiska (`${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/`). Z Claude Desktop i innymi procesami dzieli je tylko wtedy, gdy widzą ten sam `XDG_CACHE_HOME`. Shell z inną wartością niż środowisko Desktop ma osobny limiter.
- Aktywny STOP przed startem kończy przebieg bez żadnego zapytania. STOP zdejmuje wyłącznie użytkownik, po sprawdzeniu przyczyny ([configuration.md](../../docs/configuration.md#stop-blokada-między-procesami)).

## Uruchomienie

```
DEWELOPERUCH_LIVE=1 uv run pytest -m live tests/e2e -rs --maxfail=3
```

- Potrzebne są oba przełączniki: zmienna i `-m live`. Bez któregokolwiek wszystkie testy są pomijane z powodem „e2e na żywym serwisie…”, zanim ruszy jakikolwiek fixture, więc nie startuje żaden proces. Pilnuje tego `tests/test_e2e_gate.py` w domyślnym `uv run pytest`.
- `--maxfail=3` przerywa przebieg po trzech porażkach, zamiast wysyłać kolejne zapytania.
- Przebieg kończy się od razu, bez dalszych zapytań i bez ponowień:

  | Kod pytest | Powód | Co zrobić |
  |---|---|---|
  | 3 | STOP: 401, 403, 429 albo challenge | zgłosić użytkownikowi |
  | 4 | serwis niedostępny: 5xx albo sieć | spróbować później |
  | 1 | przekroczony budżet zapytań albo zepsuty licznik | sprawdzić zestaw |

  Zepsuty licznik to wywołanie, które musiało trafić do sieci, a w logu serwera nie ma żadnej linii `HTTP Request:`. Najczęściej oznacza zmianę logowania w SDK MCP.
- **Budżet:** najwyżej 60 żywych zapytań na przebieg. Plan to 46, czyli ok. 1,5–2 minuty przy 1 zapytaniu na sekundę. Pozostałe 14 to zapas na wygasły cache, który może dołożyć do 13 zapytań (najgorszy przypadek: 59). Na końcu pytest wypisuje sekcję „żywe zapytania (e2e)” z liczbą zapytań na wywołanie.
- **Cache:** serwer trzyma odpowiedź przez `s-maxage` (bez niego 300 s) minus `Age` z Cloudflare, więc wpis może wygasnąć w trakcie przebiegu. Testy oznaczone w tabeli „cache” przyjmują wtedy pełną liczbę zapytań, zgłaszają ostrzeżenie i nie porównują wyniku z wcześniejszym wywołaniem. Walidacja i błędy schematu zawsze muszą mieć 0 zapytań.
- **Liczenie zapytań:**
  - serwer MCP loguje każde zapytanie (`HTTP Request:`) na stderr, a zestaw czyta ten potok;
  - CLI działa przez swój punkt wejścia (`deweloperuch_mcp.cli:main`) z logiem httpx w pliku;
  - probe liczy się jako 1 zapytanie, chyba że skończył się kodem 2 albo 5.

  Liczone są zapytania, na które przyszła odpowiedź.
- **Logi:** w katalogu tymczasowym pytest (`--basetemp`, jeśli chcesz go wskazać): `mcp*/server-stderr.log` i `cli*/cli-N.log`.
- **Ostrzeżenia** (`UserWarning`) nie są błędami. Dotyczą danych, które mogą się zmienić między wywołaniami, np. ceny albo `offers_total` niezgodnego z listą, oraz wygasłego cache.
- **xfail** oznacza znany problem, opisany w powodzie testu, a nie porażkę.
- Asercje sprawdzają strukturę, zakresy i spójność, nie konkretne liczby. Zachowania oznaczone w kodzie [W] potwierdza dopiero pierwszy przebieg na żywo.

## Scenariusze

Kolumna „Zapytania” podaje liczbę przy uruchomieniu całego modułu w kolejności z pliku. Fixture liczy się przy pierwszym teście, który go używa. „Cache” oznacza 0 zapytań, a po wygaśnięciu cache liczbę w nawiasie.

### MCP: `test_live_mcp.py` (48 testów, 34 zapytania, najwyżej 47)

Jeden proces `deweloperuch-mcp` na moduł, więc powtórzone zapytania idą z cache serwera. Każdy wynik jest sprawdzany pod kątem STOP, niedostępności serwisu i szczegółów backendu:

- w tekście i wartościach: `/api/`, `initialData`, `_rsc`, `invest_`, `sale_id`, `/ceny-`, `NEXT_HTTP`, `digest`, `Next-Action`, `buildId`, `Traceback`, `File "`, `httpx`, `pydantic.dev`, adresy serwisu, HTML;
- w nazwach pól: `sale`, `invest` (poza `investment`), `rcn`, `amount`, `rsc`.

Wartości (nazwy deweloperów, slugi) nie są sprawdzane pod kątem nazw backendu, bo prawdziwy deweloper nazywa się np. „Invest Komfort”. SDK sprawdza wyniki ze schematem wyjścia.

| Test | Co sprawdza | Zapytania |
|---|---|---|
| `test_tools_list_matches_the_snapshot` | 4 narzędzia; nazwy, opisy, schematy, adnotacje, `serverInfo` i instrukcje zgodne z `tests/snapshots/mcp_tools.json` | 0 |
| `test_tools_list_has_no_backend_details` | filtr wycieków na opisach i schematach | 0 |
| `test_locations_a_city_gives_its_slug` | „Kraków”: `kind=city`, `city_slug` krakow (fixture) | 2 |
| `test_locations_a_district_gives_the_slug_of_its_city` | „Mokotów”: dzielnica, `city_slug` warszawa | 2 |
| `test_locations_a_street` | „Marszałkowska”: ulica (`skip`, gdy jej brak) | 2 |
| `test_locations_with_polish_letters` ×2 | „Łódź”, „Gdańsk”: miasto, slug ASCII | 4 |
| `test_locations_without_results` | „zzqxv”: 0 wyników, podpowiedź | 2 |
| `test_locations_a_too_short_query_is_refused_without_a_request` | „a”: `isError` | 0 |
| `test_offers_of_a_city_with_the_defaults` | liczniki D4 spójne, 10 pozycji, dokładnie 1 zapytanie (fixture) | 1 |
| `test_offers_50_per_page` | `per_page=50`: 50 pozycji (fixture) | 1 |
| `test_offers_50_per_page_fit_their_size_budget` | wynik dla 50 < 25 000 znaków | 0 |
| `test_offers_page_2_has_other_offers` | inne `offer_id` niż strona 1 | 1 |
| `test_offers_in_a_price_range` | 400–700 tys.: każda cena w zakresie (fixture) | 1 |
| `test_offers_in_an_area_range` | 40–60 m²: każdy metraż w zakresie (fixture) | 1 |
| `test_offers_sorted_by_price` ×2 | `price_asc` i `price_desc` | 2 |
| `test_offers_with_filters_and_sort_together` | cena, metraż i sortowanie razem | 1 |
| `test_offers_in_the_whole_country_name_their_city` | `city=polska`: pozycje mają `city` (fixture) | 1 |
| `test_offers_of_an_unknown_city_say_so` | „nie zna miasta”, `search_locations`, `polska`, bez „Serwis mógł się zmienić” | 1 |
| `test_offers_page_past_the_last_one` | [W] strona za ostatnią przy małym wyniku daje pustą stronę z podpowiedzią; „nie zna miasta” to xfail (znany problem) | 2 |
| `test_offers_price_min_above_price_max_is_refused_without_a_request` | `isError` | 0 |
| `test_offers_arguments_off_the_schema_are_refused_without_a_request` ×3 | `per_page=100`, `page=21`, `sort="area_asc"`: błąd schematu; xfail, gdy SDK dołącza odnośnik do pydantic.dev (znany problem) | 0 |
| `test_offers_numbers_as_text_are_the_same_request` | „10” i „1” jako tekst | cache (1) |
| `test_offers_filter_numbers_as_text_are_the_same_request` ×2 | `price_min="400000"`, `area_min="40"` | cache (2) |
| `test_offers_empty_or_null_optional_arguments_are_the_defaults` ×3 | `price_min=None`, `sort=""`, `sort=None` | cache (3) |
| `test_offers_result_of_10_fits_the_size_budget` | wynik dla 10 < 8000 znaków | 0 |
| `test_offers_city_that_is_not_a_slug_is_refused_without_a_request` ×4 | „Kraków”, „Warszawa”, „KRAKOW”, „”: `isError` ze wskazaniem `search_locations` | 0 |
| `test_offers_city_with_spaces_around_is_trimmed` | „ krakow ”: to samo żądanie co pierwsza strona | cache (1) |
| `test_offers_district_slug_as_city_is_an_unknown_city` | [W] „mokotow” jako miasto daje „nie zna miasta” | 1 |
| `test_investment_with_the_default_limit` | limit 20, spójne liczniki (fixture) | 1 |
| `test_investment_limit_0_is_the_summary` | samo podsumowanie | cache (1) |
| `test_investment_with_history` | `include_history`, `limit=2`: każda oferta ma historię | 1 (2) |
| `test_investment_lists_the_offer_found_by_search` | oferta z wyszukiwania na liście (`limit=200`) | cache (1) |
| `test_investment_unknown` | „Nie znaleziono inwestycji” | 1 |
| `test_offer_with_its_price_history` | niepusta `price_history`, znane `kind`; inna cena niż w wyszukiwaniu daje ostrzeżenie | 1 (2) |
| `test_offer_outside_its_investment` | `offer_id` spoza inwestycji: `isError` | cache (1) |
| `test_offer_of_an_unknown_investment` | `isError` | 1 |
| `test_offer_from_another_city_found_in_the_whole_country` | oferta z `city=polska` z innego miasta, potem `get_investment` i `get_offer` | 2 (3) |
| `test_two_calls_at_once_go_one_by_one_through_the_limiter` | dwa wywołania naraz: oba poprawne, zapytania w logu co ≥ 0,9 s | 2 |

### CLI: `test_live_cli.py` (10 testów, 10 zapytań)

Każde polecenie to osobny proces, bez wspólnego cache. Kod 3 albo „Błąd: STOP:” kończy przebieg z kodem 3, a kod 4 (błąd serwisu) z kodem 4.

| Test | Co sprawdza | Zapytania |
|---|---|---|
| `test_locations_search_as_text` | `locations search Kraków`: tekst, linia „miasto … Kraków [krakow]” | 2 |
| `test_locations_search_as_json` | `locations search Gdańsk --json` | 2 |
| `test_offers_search_with_filters_as_json` | `offers search krakow` z filtrami, `--json`: zakresy i sortowanie (fixture) | 1 |
| `test_offers_search_with_filters_as_text` | to samo jako tekst | 1 |
| `test_offers_get` | `offers get <id> --investment <slug>`: historia ceny | 2 |
| `test_investments_get_with_a_limit` | `investments get <slug> --limit 2` | 1 |
| `test_offers_search_of_an_unknown_city` | kod 7, komunikat z `search_locations` i `polska`, `Szczegóły:` bez HTML | 1 |
| `test_offers_search_with_a_wrong_page_size_sends_nothing` | `--per-page 7`: kod 2 | 0 |
| `test_stop_status_is_offline` | `stop status`: kod 0 | 0 |
| `test_the_installed_script_runs_offline` | zainstalowany skrypt `deweloperuch stop status`: kod 0 | 0 |

### Recon: `test_live_recon.py` (2 testy, 2 zapytania)

| Test | Co sprawdza | Zapytania |
|---|---|---|
| `test_probe_api` | `probe.py api "/api/cities?q=krak"`: kod 0, JSON z krakow | 1 |
| `test_probe_page_lists_the_data_props` | `probe.py page "/ceny-ofertowe/warszawa/mieszkania?perPage=10"` bez `--prop`: lista propsów zawiera `initialData` | 1 |

Skaner bundli (`recon/scan_bundles.py`, ok. 140 zapytań) nie wchodzi do zestawu.

**Łącznie:** 60 testów, plan 46 żywych zapytań, najwyżej 59, limit 60.
