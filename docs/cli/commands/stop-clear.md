# `deweloperuch stop clear`
Zdejmuje blokadę STOP (usuwa `stop.json` pod zamkiem limitera) i wypisuje, co zdjęto. Działa offline.

> **Tylko dla człowieka, po sprawdzeniu przyczyny** (`deweloperuch stop status`). Agent (model) tej komendy nie uruchamia: blokuje ją hook Bash w Claude Code (`.claude/hooks/guard_live_calls.py`) i reguła w `CLAUDE.md`. Nie ma też narzędzia MCP do zdejmowania blokady. Po 401, 403 lub challenge nie zdejmuj blokady, dopóki nie wiesz, dlaczego serwis odmówił. Zasady STOP: [docs/cli/README.md](../README.md#stop).

## Użycie
```
Usage: deweloperuch stop clear [OPTIONS]
```

Opis z `--help`: „Zdejmij blokadę STOP. Tylko człowiek, po sprawdzeniu przyczyny (`stop status`).”

## Opcje
| Flaga | Typ | Domyślna | Opis |
|---|---|---|---|
| (brak) | | | Tylko `--help`. Bez `--json` i bez pytania o potwierdzenie. |

## Zachowanie
- Czeka na zamek limitera najwyżej 300 s. Po 2 s oczekiwania pisze na stderr: `Czekam na zamek limitera: inny proces wysyła zapytanie albo czeka na swoją kolej.` Po 300 s kończy się kodem 1 i niczego nie zdejmuje (`Błąd: Nie udało się uzyskać zamka limitera w ciągu 300 s: … Nic nie zostało zdjęte.`).
- Usuwa też osierocone pliki `.stop-*.tmp` (po przerwanym zapisie). Innych plików nie rusza.
- **Nie skraca pauzy po 429** zapisanej w limiterze: `Retry-After` serwisu nadal obowiązuje. Dlatego zaraz po zdjęciu zapisu 429 komendy danych mogą jeszcze skończyć się kodem 5 (limiter wymaga czekania).
- Nie tworzy katalogu, gdy go nie ma.
- **Po zdjęciu zrestartuj serwer MCP.** Serwer, który raz zwrócił STOP (własny albo z zapisu innego procesu), pozostaje zatrzaśnięty do restartu i po `stop clear` nadal niczego nie wyśle. Komendy CLI i recon (nowe procesy) działają od razu.

## Wyjście
- `Zdjęto STOP: <etykieta>, <czas>, źródło: <źródło>.` (dla wygasłego: `Zdjęto STOP (już wygasł): …`);
- dla aktywnego 429: `Pauza po 429 zapisana w limiterze nadal obowiązuje.`;
- `Działający serwer MCP, który trafił na STOP, wyśle zapytania dopiero po ponownym uruchomieniu.`;
- nieczytelny zapis: `Zdjęto nieczytelny zapis STOP (<problem>).` i ta sama informacja o MCP;
- bez zapisu: `Brak STOP: nie było czego zdejmować.`

## Kody wyjścia
| Kod | Znaczenie |
|---|---|
| 0 | Zdjęto zapis albo go nie było. |
| 1 | Zamek nie został uzyskany w 300 s albo zapisu nie da się usunąć (`Błąd: nie udało się zdjąć zapisu STOP: …`); nic nie zdjęto. |

## Przykłady
```
uv run deweloperuch stop status     # najpierw sprawdź przyczynę i źródło
uv run deweloperuch stop clear      # dopiero potem zdejmij blokadę (człowiek)
```

Wynik po zapisie 403 z `probe` (z testów `tests/test_cli.py`):

```
Zdjęto STOP: HTTP 403 (odmowa dostępu), <czas>, źródło: probe.
Działający serwer MCP, który trafił na STOP, wyśle zapytania dopiero po ponownym uruchomieniu.
```

_Źródło: `src/deweloperuch_mcp/cli.py` (`stop_clear`, `format_stop_clear`), `src/deweloperuch_mcp/throttle.py` (`clear_stop`), `uv run deweloperuch stop clear --help`, `tests/test_cli.py`_
