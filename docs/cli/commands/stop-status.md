# `deweloperuch stop status`
Shows the STOP lock shared by all processes (CLI, MCP server, `recon/probe.py`, `recon/scan_bundles.py`): since when it has lasted, who wrote it and when it expires. Works offline, answers immediately (does not wait for the limiter lock) and creates or changes nothing. STOP rules: [docs/cli/README.md](../README.md#stop).

## Usage
```
Usage: deweloperuch stop status [OPTIONS]
```

`--help` description: „Pokaż blokadę STOP; kod 3, gdy wstrzymuje zapytania (także wygasająca), 0, gdy nie.” (code 3 when it halts requests, also an expiring one, 0 when it does not)

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | flag | off | Print the lock state as JSON instead of text. Help text: „Wypisz stan blokady jako JSON.” |
| `--help` | flag | | Show the help. |

## Output
Text, lines in order:

- `STOP aktywny: <label>.`, e.g. `HTTP 403 (odmowa dostępu)`, `HTTP 429 (limit zapytań)` or `challenge Cloudflare (captcha/WAF)`;
- `Od: <local time with offset> · źródło: <pakiet|probe|scan_bundles> (PID n)`;
- `Wygasa: nie, trwa do zdjęcia.` or (429 only) `Wygasa: <time> (za N s).`;
- `Blokadę zdejmuje użytkownik po sprawdzeniu przyczyny: deweloperuch stop clear` (only with an active lock);
- `Plik: <path to stop.json>`.

Other variants:

- no record: `Brak STOP: zapytania do deweloperuch.pl nie są wstrzymane.` and `Plik: …`;
- an expired 429: `STOP wygasł <time>: HTTP 429 (limit zapytań).`, the `Od: …` line, `Zapytania do deweloperuch.pl nie są wstrzymane.`, `Plik: …`;
- an unreadable record: `STOP aktywny bezterminowo: zapis jest nieczytelny.`, `Problem: <description>` (without the file content, at most 200 characters), the line about clearing, `Plik: …`.

`--json`:

| Field | Description |
|---|---|
| `active` | `true` when the lock halts requests (also an unreadable record). |
| `seconds_left` | The remaining 429 time in seconds; `null` for an indefinite lock or when there is no record. |
| `path` | The path of `stop.json`. |
| `record` | `{since, status, reason, until, source, pid}` (ISO 8601 UTC times; `until` is `null` except for 429) or `null`. |
| `unreadable` | A description of the problem for an unreadable record, or `null`. |

## Exit codes
| Code | Meaning |
|---|---|
| 0 | No STOP, or the record has expired (requests are not halted). |
| 3 | STOP active: also an expiring 429 and an unreadable record (indefinite). |

There is no code 1: an unreadable or inaccessible record is code 3.

## Examples
```
uv run deweloperuch stop status
uv run deweloperuch stop status --json
```

Output with an active indefinite lock (`tests/golden/cli/stop_status_403.json`, code 3):

```
STOP aktywny: HTTP 403 (odmowa dostępu).
Od: <czas> · źródło: probe (PID <n>)
Wygasa: nie, trwa do zdjęcia.
Blokadę zdejmuje użytkownik po sprawdzeniu przyczyny: deweloperuch stop clear
Plik: <ścieżka>/deweloperuch-mcp/stop.json
```

`--json` output without STOP (code 0):

```json
{
  "active": false,
  "seconds_left": null,
  "path": "<ścieżka>/deweloperuch-mcp/stop.json",
  "record": null,
  "unreadable": null
}
```

_Source: `src/deweloperuch_mcp/consumers/cli/commands/stop_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/get_stop_status_cli_presenter.py`, `src/deweloperuch_mcp/usecases/get_stop_status.py`, `src/deweloperuch_mcp/throttle.py`, `uv run deweloperuch stop status --help`, `tests/golden/cli/stop_status_*.json`_
