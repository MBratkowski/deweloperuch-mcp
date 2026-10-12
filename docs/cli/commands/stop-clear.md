# `deweloperuch stop clear`
Clears the STOP lock (removes `stop.json` under the limiter lock) and prints what was cleared. Works offline.

> **For humans only, after checking the cause** (`deweloperuch stop status`). An agent (model) does not run this command: the Bash hook in Claude Code (`.claude/hooks/guard_live_calls.py`) and a rule in `CLAUDE.md` block it. There is also no MCP tool for clearing the lock. After a 401, 403 or challenge do not clear the lock until you know why the service refused. STOP rules: [docs/cli/README.md](../README.md#stop).

## Usage
```
Usage: deweloperuch stop clear [OPTIONS]
```

`--help` description: „Zdejmij blokadę STOP. Tylko człowiek, po sprawdzeniu przyczyny (`stop status`).”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| (none) | | | Only `--help`. No `--json` and no confirmation prompt. |

## Behavior
- Waits for the limiter lock at most 300 s. After 2 s of waiting it writes to stderr: `Czekam na zamek limitera: inny proces wysyła zapytanie albo czeka na swoją kolej.` After 300 s it ends with code 1 and clears nothing (`Błąd: Nie udało się uzyskać zamka limitera w ciągu 300 s: … Nic nie zostało zdjęte.`).
- Also removes orphaned `.stop-*.tmp` files (after an interrupted write). It touches no other files.
- **It does not shorten the pause after a 429** recorded in the limiter: the service's `Retry-After` still applies. Therefore right after clearing a 429 record the data commands may still end with code 5 (the limiter requires waiting).
- It does not create the directory when it does not exist.
- **Restart the MCP server after clearing.** A server that returned STOP once (its own or from another process's record) stays latched until restart and will still send nothing after `stop clear`. CLI commands and recon (new processes) work immediately.

## Output
- `Zdjęto STOP: <label>, <time>, źródło: <source>.` (for an expired one: `Zdjęto STOP (już wygasł): …`);
- for an active 429: `Pauza po 429 zapisana w limiterze nadal obowiązuje.`;
- `Działający serwer MCP, który trafił na STOP, wyśle zapytania dopiero po ponownym uruchomieniu.`;
- an unreadable record: `Zdjęto nieczytelny zapis STOP (<problem>).` and the same information about MCP;
- no record: `Brak STOP: nie było czego zdejmować.`

## Exit codes
| Code | Meaning |
|---|---|
| 0 | The record was cleared or there was none. |
| 1 | The lock was not obtained within 300 s or the record cannot be removed (`Błąd: nie udało się zdjąć zapisu STOP: …`); nothing was cleared. |

## Examples
```
uv run deweloperuch stop status     # first check the cause and the source
uv run deweloperuch stop clear      # only then clear the lock (a human)
```

Output after a 403 record from `probe` (from the tests `tests/test_cli.py`):

```
Zdjęto STOP: HTTP 403 (odmowa dostępu), <czas>, źródło: probe.
Działający serwer MCP, który trafił na STOP, wyśle zapytania dopiero po ponownym uruchomieniu.
```

_Source: `src/deweloperuch_mcp/cli.py` (`stop_clear`, `format_stop_clear`), `src/deweloperuch_mcp/throttle.py` (`clear_stop`), `uv run deweloperuch stop clear --help`, `tests/test_cli.py`_
