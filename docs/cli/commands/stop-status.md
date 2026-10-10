# `deweloperuch stop status`
Pokazuje blokadę STOP wspólną dla wszystkich procesów (CLI, serwer MCP, `recon/probe.py`, `recon/scan_bundles.py`): od kiedy trwa, kto ją zapisał i kiedy wygasa. Działa offline, odpowiada od razu (nie czeka na zamek limitera) i niczego nie tworzy ani nie zmienia. Zasady STOP: [docs/cli/README.md](../README.md#stop).

## Użycie
```
Usage: deweloperuch stop status [OPTIONS]
```

Opis z `--help`: „Pokaż blokadę STOP; kod 3, gdy wstrzymuje zapytania (także wygasająca), 0, gdy nie.”

## Opcje
| Flaga | Typ | Domyślna | Opis |
|---|---|---|---|
| `--json` | flaga | wyłączona | Wypisuje stan blokady jako JSON zamiast tekstu. |

## Wyjście
Tekst, linie po kolei:

- `STOP aktywny: <etykieta>.`, np. `HTTP 403 (odmowa dostępu)`, `HTTP 429 (limit zapytań)` albo `challenge Cloudflare (captcha/WAF)`;
- `Od: <czas lokalny z offsetem> · źródło: <pakiet|probe|scan_bundles> (PID n)`;
- `Wygasa: nie, trwa do zdjęcia.` albo (tylko 429) `Wygasa: <czas> (za N s).`;
- `Blokadę zdejmuje użytkownik po sprawdzeniu przyczyny: deweloperuch stop clear` (tylko przy aktywnej blokadzie);
- `Plik: <ścieżka do stop.json>`.

Pozostałe warianty:

- bez zapisu: `Brak STOP: zapytania do deweloperuch.pl nie są wstrzymane.` i `Plik: …`;
- wygasły 429: `STOP wygasł <czas>: HTTP 429 (limit zapytań).`, linia `Od: …`, `Zapytania do deweloperuch.pl nie są wstrzymane.`, `Plik: …`;
- nieczytelny zapis: `STOP aktywny bezterminowo: zapis jest nieczytelny.`, `Problem: <opis>` (bez treści pliku, najwyżej 200 znaków), linia o zdejmowaniu, `Plik: …`.

`--json`:

| Pole | Opis |
|---|---|
| `active` | `true`, gdy blokada wstrzymuje zapytania (także nieczytelny zapis). |
| `seconds_left` | Pozostały czas 429 w sekundach; `null` dla blokady bezterminowej lub gdy brak zapisu. |
| `path` | Ścieżka `stop.json`. |
| `record` | `{since, status, reason, until, source, pid}` (czasy ISO 8601 UTC; `until` to `null` poza 429) albo `null`. |
| `unreadable` | Opis problemu przy nieczytelnym zapisie albo `null`. |

## Kody wyjścia
| Kod | Znaczenie |
|---|---|
| 0 | Brak STOP albo zapis wygasły (zapytania nie są wstrzymane). |
| 3 | STOP aktywny: także wygasający 429 i nieczytelny zapis (bezterminowy). |

Kodu 1 nie ma: nieczytelny lub niedostępny zapis to kod 3.

## Przykłady
```
uv run deweloperuch stop status
uv run deweloperuch stop status --json
```

Wynik przy aktywnej blokadzie bezterminowej (z testów `tests/test_cli.py`, kod 3):

```
STOP aktywny: HTTP 403 (odmowa dostępu).
Od: <czas> · źródło: probe (PID <n>)
Wygasa: nie, trwa do zdjęcia.
Blokadę zdejmuje użytkownik po sprawdzeniu przyczyny: deweloperuch stop clear
Plik: <ścieżka>/deweloperuch-mcp/stop.json
```

Wynik `--json` bez STOP (kod 0):

```json
{
  "active": false,
  "seconds_left": null,
  "path": "<ścieżka>/deweloperuch-mcp/stop.json",
  "record": null,
  "unreadable": null
}
```

_Źródło: `src/deweloperuch_mcp/cli.py` (`stop_status`, `format_stop_status`), `src/deweloperuch_mcp/throttle.py`, `uv run deweloperuch stop status --help`, `tests/test_cli.py`_
