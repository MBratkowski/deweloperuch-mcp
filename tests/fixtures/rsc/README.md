# Surowe odpowiedzi RSC (fiksy testowe)

Całe ciała odpowiedzi `text/x-component` stron listy ofert, tak jak przysłał je serwis. Próbki w `docs/discovery/samples/page.*.json` zawierają tylko wartość propsa; tu jest cały strumień flight, z wierszami tekstowymi `<id>:T<hex długość w bajtach>,<tekst>`, po których nie ma znaku nowej linii.

| Plik | Cel zapytania | Odpowiedź | Rozmiar |
|---|---|---|---|
| `warszawa_perPage10.rsc` | `/ceny-ofertowe/warszawa/mieszkania?perPage=10&_rsc=fe86badc` | 200, `initialData` z 10 ofertami (`total` 13 324). Tuż przed wierszem z danymi są wiersze `16:T5ed,` i `19:T1a27,` z JSON-LD | 46 652 B (oryginał 46 659 B) |
| `unknown_city_perPage10.rsc` | `/ceny-ofertowe/nieistniejace-miasto/mieszkania?perPage=10&_rsc=4b97e1e1` | 200 bez `initialData`, z wierszem błędu `f:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}` | 26 796 B (oryginał 26 803 B) |

- Źródło: klient pakietu (`deweloperuch_mcp`, nagłówek `RSC: 1`), po jednym zapytaniu na plik. Pobrał je główny wątek 2026-10-10 przy diagnozie błędu `search_offers`.
- Zawartość: dane ofert (ceny, metraże, inwestycje, deweloperzy), JSON-LD i układ strony. Jedyna zmiana względem oryginału to adres kontaktowy serwisu w stopce (wiersz `0:`, przed wierszami `T`). Zastąpiono go `"[usunięte]"` zgodnie z regułą próbek. Nie ma tam innych danych osobowych.
- Długości wierszy `T` liczą bajty, więc pliki muszą zostać nietknięte bajt po bajcie. `.gitattributes` wyłącza konwersję końców linii. Nowa obserwacja to nowy plik, istniejących się nie nadpisuje.
- Używają ich `tests/rsc_fixtures.py`, `tests/service_mocks.py` (domyślna trasa listy ofert) i testy w `tests/test_flight.py`, `test_client_adapters.py`, `test_services.py`, `test_cli.py`, `test_mcp_server.py` i `test_probe.py`.
