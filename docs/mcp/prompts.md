# MCP prompts

The server offers four prompts (`prompts/list`, `prompts/get`). Claude Desktop shows them as ready-made commands. A prompt sends no requests to the service: it returns one user message in Polish that tells the model which of the [13 tools](README.md#tools) to call, in what order, how to present the result and which caveats to give. All argument values are text.

Titles, descriptions and argument descriptions below are quoted verbatim from `tests/snapshots/mcp_prompts.json`.

## `znajdz_mieszkanie`: Znajdź mieszkanie
> Mieszkania od deweloperów w jednym mieście z budżetem, metrażem i dzielnicą: tabela ofert od najniższej ceny za m² z linkami do deweloperuch.pl.

| Argument | Required | Description |
|---|---|---|
| `miasto` | yes | Miasto, np. Kraków, Gdańsk. |
| `budzet_max` | no | Najwyższa cena mieszkania w PLN, np. 800000. |
| `metraz_min` | no | Najmniejszy metraż w m², np. 40. |
| `metraz_max` | no | Największy metraż w m², np. 65. |
| `dzielnica` | no | Dzielnica, np. Mokotów. |

Plan for the model: `search_locations` (the city, and with a `dzielnica` the district by its `name`, passed to `search_offers` as `district` together with the `city_slug` of its city) → `search_offers` (sorted by `price_per_m2_asc`, 10 per page) → a table with the columns „inwestycja, dzielnica, deweloper, cena, metraż, cena za m², zmiana ceny od pierwszej i link investment_url” (the district column is new: `search_offers` items carry `district`) and under it `total` and `list_url`. The note on rooms and floors says: `search_offers` does not filter by them (the offer list does not give them), so the model tells the user and narrows the area instead.

## `ocen_oferte`: Oceń ofertę
> Ocena ceny jednej oferty: historia ceny (najniższa z 30 i 90 dni, podejrzane obniżki), porównanie z rynkiem miasta i z wyceną z transakcji w okolicy; werdykt z zastrzeżeniami.

| Argument | Required | Description |
|---|---|---|
| `offer_id` | yes | offer_id oferty z wyników search_offers albo get_investment. |
| `investment_slug` | yes | investment_slug inwestycji tej oferty, np. smolna: z tych samych wyników albo ostatni człon adresu strony inwestycji na deweloperuch.pl. |

Plan for the model: `get_offer` (`price_flags`) → `get_market_statistics` → `get_investment` and `estimate_property_value` (when the investment has coordinates) → a short verdict with caveats (among them: when `estimate_property_value` returns `low_confidence=true`, pass on the caveat from `hint`, the estimate being only indicative).

## `przeswietl_dewelopera`: Prześwietl dewelopera
> Profil dewelopera: gdzie i ile buduje, jego inwestycje, aktywne oferty, ceny i ich zmiany; w całej Polsce albo w jednym mieście.

| Argument | Required | Description |
|---|---|---|
| `nazwa` | yes | Nazwa dewelopera albo jej fragment, np. Atal, Dom Development. |
| `miasto` | no | Miasto, do którego zawęzić inwestycje, np. Kraków. |

Plan for the model: `search_developers` → `get_developer` (plus `search_locations` and `search_investments` when a city is given) → `get_investment` for 1 to 3 investments to see price changes.

## `porownaj_miasta`: Porównaj miasta
> Porównanie rynku mieszkań kilku miast: ceny ofertowe deweloperów, ceny transakcyjne z RCN i opcjonalnie wynagrodzenia i bezrobocie z GUS, w jednej tabeli.

| Argument | Required | Description |
|---|---|---|
| `miasta` | yes | Nazwy miast rozdzielone przecinkami, np. Kraków, Wrocław, Gdańsk (najwyżej 5). |

Plan for the model: per city `search_locations`, `get_market_statistics`, `get_transaction_statistics` and optionally `get_government_statistics` → one table with asking and transaction prices in separate columns (the asking-price columns are the median asking price per m², the number of offers and the day the service gave them for, `as_of` of `get_market_statistics`); periods with `incomplete=true` are skipped and the cities are compared up to the earliest `last_complete_period` of them all (a city without one is marked uncertain, see its `hint`).

_Source: `src/deweloperuch_mcp/consumers/mcp/prompts/`, `tests/snapshots/mcp_prompts.json`_
