# `deweloperuch`: command reference

<!-- Generated from the CLI by packaging/skill_reference.py (`make skill`); do not edit. -->

Every command runs as `deweloperuch …` or, without installing, as `uvx --from deweloperuch-mcp deweloperuch …`. The descriptions are the CLI's own help texts (Polish); `--help` after any group or command prints them offline. `[required]` marks what must be given, `[default: …]` the value used otherwise; `--json` prints the result as JSON. The `stop` group's command that lifts a STOP is left out on purpose: only the user lifts a STOP, after checking its cause.

## `deweloperuch locations`

Lokalizacje: miasta, dzielnice, ulice.

### `deweloperuch locations search [OPTIONS] QUERY`

Znajdź miasta, dzielnice i ulice; podaje slug miasta do `offers search`.

- `QUERY`: Fragment nazwy miasta, dzielnicy lub ulicy (2–100 znaków), np. krak. [required]
- `--json`: Wypisz wynik jako JSON (model domenowy).

## `deweloperuch offers`

Oferty mieszkań od deweloperów.

### `deweloperuch offers search [OPTIONS] CITY`

Szukaj ofert mieszkań w mieście; najwyżej 20 stron wyników.

- `CITY`: Slug miasta (np. warszawa; podaje go `locations search`) albo polska. [required]
- `--price-min <int>`: Najniższa cena w PLN.
- `--price-max <int>`: Najwyższa cena w PLN.
- `--area-min <int>`: Najmniejszy metraż w m².
- `--area-max <int>`: Największy metraż w m².
- `--price-per-m2-min <int>`: Najniższa cena za m² w PLN.
- `--price-per-m2-max <int>`: Najwyższa cena za m² w PLN.
- `--district <str>`: Dzielnica miasta jak w `locations search` (np. Mokotów); nie z polska.
- `--price-dropped`: Tylko oferty tańsze niż ich pierwsza cena.
- `--status <active|archived|all>`: active (domyślnie), archived (wycofane) albo all (obie).
- `--sort <price_asc|price_desc|price_per_m2_asc|price_per_m2_desc|area_asc|area_desc|biggest_drop>`: Kolejność: po cenie, cenie za m², metrażu albo najpierw największa obniżka od pierwszej ceny; bez opcji domyślna kolejność serwisu.
- `--page <int>`: Numer strony, 1–20. [default: 1]
- `--per-page <10|50|100>`: Liczba ofert na stronie. [default: 10]
- `--json`: Wypisz wynik jako JSON (model domenowy).

### `deweloperuch offers get [OPTIONS] OFFER_ID`

Pokaż ofertę z historią ceny.

- `OFFER_ID`: Identyfikator oferty z `offers search`. [required]
- `--investment SLUG`: Slug inwestycji oferty (investment_slug z `offers search`). [required]
- `--json`: Wypisz wynik jako JSON (model domenowy).

## `deweloperuch investments`

Inwestycje deweloperskie.

### `deweloperuch investments get [OPTIONS] SLUG`

Pokaż inwestycję z deweloperem i ofertami.

- `SLUG`: Slug inwestycji (investment_slug z `offers search`). [required]
- `--history`: Dołącz historię ceny każdej oferty (wolniej).
- `--limit <int>`: Najwięcej pokazanych ofert (najpierw aktywne); domyślnie wszystkie.
- `--json`: Wypisz wynik jako JSON (model domenowy).

### `deweloperuch investments search [OPTIONS] [CITY]`

Szukaj inwestycji w mieście albo po nazwie (w całej Polsce).

- `[CITY]`: Slug miasta (np. sopot; podaje go `locations search`). Bez CITY podaj --name.
- `--name <str>`: Fragment nazwy inwestycji (2–100 znaków); bez CITY w całej Polsce.
- `--developer SLUG`: Slug dewelopera; tylko z CITY.
- `--sort <active_offers|price_per_m2_asc|price_per_m2_desc|price_asc|price_desc|name>`: Kolejność; tylko z CITY. Domyślnie najwięcej aktywnych ofert.
- `--limit <int>`: Najwięcej pokazanych inwestycji, 1–500 (po samej nazwie do 50). [default: 10]
- `--json`: Wypisz wynik jako JSON (model domenowy).

## `deweloperuch developers`

Deweloperzy.

### `deweloperuch developers get [OPTIONS] SLUG`

Pokaż dewelopera z jego inwestycjami i miastami.

- `SLUG`: Slug dewelopera (z `developers search` albo pole developer_slug z `offers search`). [required]
- `--city <str>`: Slug miasta (np. krakow) albo polska, czyli cała Polska. [default: polska]
- `--limit <int>`: Najwięcej pokazanych inwestycji (najpierw z największą liczbą ofert). [default: 20]
- `--json`: Wypisz wynik jako JSON (model domenowy).

### `deweloperuch developers search [OPTIONS] NAME`

Znajdź deweloperów po nazwie; podaje slug dewelopera do `developers get`.

- `NAME`: Fragment nazwy dewelopera (2–100 znaków), np. atal. [required]
- `--limit <int>`: Najwięcej pokazanych deweloperów (1–20). [default: 5]
- `--json`: Wypisz wynik jako JSON (model domenowy).

## `deweloperuch buildings`

Budynki z rejestru cen transakcyjnych (RCN): lokale i ich transakcje.

### `deweloperuch buildings get [OPTIONS] SLUG`

Pokaż budynek z lokalami i ich transakcjami (ceny transakcyjne, nie ofertowe).

Lokale od tego z najnowszą transakcją, transakcje każdego lokalu od najstarszej.

- `SLUG`: Slug budynku, np. 23-marca-79c-sopot: ostatni człon adresu strony budynku z cenami transakcyjnymi na deweloperuch.pl. [required]
- `--limit <int>`: Najwięcej pokazanych lokali (tych z najnowszymi transakcjami); domyślnie wszystkie.
- `--trend`: Dołącz średnią cenę za m² transakcji w okolicy budynku, kwartał po kwartale (jedno zapytanie więcej).
- `--json`: Wypisz wynik jako JSON (model domenowy).

## `deweloperuch valuation`

Wycena mieszkania z cen transakcyjnych (RCN) w okolicy.

### `deweloperuch valuation estimate [OPTIONS]`

Oszacuj wartość mieszkania z transakcji w okolicy punktu (przybliżenie, nie operat).

- `--lat <float>`: Szerokość geograficzna punktu w Polsce, np. 52.2297. [required]
- `--lng <float>`: Długość geograficzna punktu w Polsce, np. 21.0122. [required]
- `--area <float>`: Metraż mieszkania w m², 10–500, np. 48.5. [required]
- `--address <str>`: Opcjonalny opis adresu; położenie wyznaczają --lat i --lng.
- `--limit <int>`: Najwięcej pokazanych transakcji porównawczych (najbliższe); domyślnie wszystkie.
- `--json`: Wypisz wynik jako JSON (model domenowy).

## `deweloperuch stats`

Statystyki: rynek ofert miasta, ceny transakcyjne (RCN) miasta, ranking miast i powiatów oraz statystyki rządowe GUS i NBP.

### `deweloperuch stats government [OPTIONS] LOCATION DATASET`

Pokaż statystyki GUS i NBP lokalizacji jako tabelę okresów i wartości.

- `LOCATION`: polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo miasto na prawach powiatu bez polskich znaków, np. warszawa, bielsko-biala. [required]
- `DATASET <dwellings_quarterly|dwellings_monthly|average_area|demography|population|unemployment|wages|nbp_prices>`: Zestaw danych. [required]
- `--periods <int>`: Ile ostatnich okresów pokazać (lat, kwartałów, miesięcy). [default: 12]
- `--json`: Wypisz wynik jako JSON (model domenowy).

### `deweloperuch stats market [OPTIONS] CITY`

Pokaż statystyki aktywnych ofert miasta: ceny, metraże, największych deweloperów.

- `CITY`: Slug jednego miasta (np. krakow; podaje go `locations search`), nie polska. [required]
- `--price-min <int>`: Najniższa cena w PLN.
- `--price-max <int>`: Najwyższa cena w PLN.
- `--area-min <int>`: Najmniejszy metraż w m².
- `--area-max <int>`: Największy metraż w m².
- `--top <int>`: Ilu największych deweloperów pokazać (1–30). [default: 10]
- `--json`: Wypisz wynik jako JSON (model domenowy).

### `deweloperuch stats transactions [OPTIONS] CITY`

Pokaż ceny transakcyjne mieszkań (RCN) w mieście, miesiąc po miesiącu albo kwartałami.

- `CITY`: Slug miasta bez polskich znaków, np. warszawa, krakow (podaje go deweloperuch locations search). Bez dzielnic, ulic i całej Polski. [required]
- `--granularity <month|quarter>`: month: miesiące (mediany i średnie); quarter: kwartały (średnia cena za m², dłuższa historia). [default: month]
- `--periods <int>`: Ile ostatnich okresów pokazać (miesięcy, kwartałów). [default: 12]
- `--json`: Wypisz wynik jako JSON (model domenowy).

### `deweloperuch stats cities [OPTIONS]`

Pokaż ranking miejscowości albo powiatów według transakcji RCN.

- `--level <city|powiat>`: city: miejscowości (także małe); powiat: powiaty. [default: city]
- `--sort <transactions_desc|price_per_m2_desc|price_per_m2_asc>`: Najwięcej transakcji albo po cenie za m² (malejąco, rosnąco). [default: transactions_desc]
- `--limit <int>`: Ile pierwszych pozycji pokazać, 1–100. [default: 20]
- `--min-transactions <int>`: Pomiń miejsca z mniejszą liczbą transakcji; domyślnie 20 przy sortowaniu po cenie, 0 po liczbie transakcji (0: wszystkie miejsca).
- `--json`: Wypisz wynik jako JSON (model domenowy).

## `deweloperuch stop`

Blokada STOP: po 401, 403, 429 albo challenge Cloudflare żaden proces (CLI, serwer MCP, recon) nie wysyła zapytań. Działa offline.

### `deweloperuch stop status [OPTIONS]`

Pokaż blokadę STOP; kod 3, gdy wstrzymuje zapytania (także wygasająca), 0, gdy nie.

- `--json`: Wypisz stan blokady jako JSON.

## `deweloperuch skill`

Skill deweloperuch-cli dla agentów AI (Claude Code, Codex, Cursor i innych): jak używać tego CLI. Zalecana instalacja: npx skills add MBratkowski/deweloperuch-mcp (wybierasz agenta); bez Node.js: deweloperuch skill install. Działa offline.

### `deweloperuch skill install [OPTIONS]`

Zainstaluj skill deweloperuch-cli w katalogu skilli agenta (bez Node.js).

- `--agent <claude-code|codex|cursor|gemini-cli|github-copilot>`: Agent, w którego katalogu skilli zapisać (nazwy jak w npx skills add --agent); domyślnie claude-code.
- `--project / --user`: --project: skille bieżącego projektu (np. ./.claude/skills); --user: skille użytkownika (np. ~/.claude/skills). [default: user]
- `--dir PATH`: Inny katalog skilli: zapisz do PATH/deweloperuch-cli (bez --agent i --project).
- `--force`: Zastąp kopię skilla, która różni się od tej z pakietu.

### `deweloperuch skill show [OPTIONS]`

Wypisz SKILL.md: instrukcje skilla dla agenta.

### `deweloperuch skill path [OPTIONS]`

Pokaż katalog skilla w zainstalowanym pakiecie.
