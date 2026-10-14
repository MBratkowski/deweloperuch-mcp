# `deweloperuch developers search`
Finds developers by a name fragment and prints the developer slug for `developers get`. Equivalent to the MCP tool [`search_developers`](../../mcp/tools/search_developers.md).

## Usage
```
deweloperuch developers search [OPTIONS] NAME
```

`--help` description: „Znajdź deweloperów po nazwie; podaje slug dewelopera do `developers get`.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `NAME` (argument, required) | text | — | A fragment of the developer name (2–100 characters), e.g. atal. Help text: „Fragment nazwy dewelopera (2–100 znaków), np. atal.” |
| `--limit` | int | `5` | The maximum number of developers shown (1–20). Help text: „Najwięcej pokazanych deweloperów (1–20).” |
| `--json` | flag | off | Print the result as JSON (the domain model). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0 (also when nothing matches), 2 (`NAME` missing or outside 2–100 characters, `--limit` outside 1–20), 3 STOP, 4 service error.

## Examples
```
deweloperuch developers search atal
deweloperuch developers search "dom development" --limit 10
deweloperuch developers search atal --json
```

Output of the first call (`tests/golden/cli/developers_search.json`):

```
Deweloperzy: 1.
ATAL S.A. [atal] · ofert: 4 265
    https://deweloperuch.pl/ceny-ofertowe/polska/deweloperzy/atal
W nawiasach [] slug dewelopera dla: deweloperuch developers get SLUG
```

_Source: `src/deweloperuch_mcp/consumers/cli/commands/developers_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/search_developers_cli_presenter.py`, `uv run deweloperuch developers search --help`_
