# `deweloperuch skill`
The agent skill `deweloperuch-cli`: instructions that teach AI coding agents (Claude Code, Codex, Cursor and others) how to use this CLI. Three subcommands install, print and locate the skill. They work offline: no request to the service, no limiter, no STOP check.

The recommended install is the `skills` CLI from GitHub (`npx skills add MBratkowski/deweloperuch-mcp`, you choose the agent, needs Node.js) or, in Claude Code, the plugin marketplace (see below). `skill install` is the way without Node.js.

## Usage
```
Usage: deweloperuch skill [OPTIONS] COMMAND [ARGS]...
Usage: deweloperuch skill install [OPTIONS]
Usage: deweloperuch skill show [OPTIONS]
Usage: deweloperuch skill path [OPTIONS]
```

`--help` description of the group: „Skill deweloperuch-cli dla agentów AI (Claude Code, Codex, Cursor i innych): jak używać tego CLI. Zalecana instalacja: npx skills add MBratkowski/deweloperuch-mcp (wybierasz agenta); bez Node.js: deweloperuch skill install. Działa offline.”

| Subcommand | `--help` description |
|---|---|
| `install` | „Zainstaluj skill deweloperuch-cli w katalogu skilli agenta (bez Node.js).” |
| `show` | „Wypisz SKILL.md: instrukcje skilla dla agenta.” |
| `path` | „Pokaż katalog skilla w zainstalowanym pakiecie.” |

## Options
Only `skill install` has options (`show` and `path` have only `--help`).

| Flag | Type | Default | Description |
|---|---|---|---|
| `--agent` | `claude-code`, `codex`, `cursor`, `gemini-cli`, `github-copilot` | `claude-code` | The agent whose skills folder is used (names as in `npx skills add --agent`). Help text: „Agent, w którego katalogu skilli zapisać (nazwy jak w npx skills add --agent); domyślnie claude-code.” |
| `--project` / `--user` | flag | `--user` | `--project`: the current project's skills folder (for Claude Code `./.claude/skills`); `--user`: the user's folder (`~/.claude/skills`). |
| `--dir` | `PATH` | none | Another skills folder: writes to `PATH/deweloperuch-cli`. Cannot be combined with `--agent` or `--project`. |
| `--force` | flag | off | Replace a copy of the skill that differs from the packaged one. Without it a different copy is never overwritten. |
| `--help` | flag | | Show the help. |

Skills folders per agent (project / user): `claude-code` `.claude/skills` / `.claude/skills`; `codex` `.agents/skills` / `.agents/skills`; `cursor` `.agents/skills` / `.cursor/skills`; `gemini-cli` `.agents/skills` / `.gemini/skills`; `github-copilot` `.agents/skills` / `.copilot/skills`. The skill goes into the `deweloperuch-cli` subfolder.

## Behavior
- `install` copies the skill's `*.md` files (`SKILL.md`, `EXAMPLES.md`, `REFERENCE.md`) from the installed package, or from `skills/deweloperuch-cli/` in a source checkout. Other files in the target folder stay.
- It never writes through a symbolic link, and refuses to overwrite a copy that differs (edited, from another version, or a link) unless `--force` is given. An identical copy is left untouched.
- `show` prints `SKILL.md` as it is. `path` prints one line, the folder of the skill in the installed package (for scripts).
- `REFERENCE.md` is generated from the CLI by `make skill` (`packaging/skill_reference.py`); a test fails when it is stale.

## Output
`install`, then the usage hint:

- `Zainstalowano skill deweloperuch-cli w <folder> (pliki: <list>).`
- an identical copy: `Skill deweloperuch-cli w <folder> jest już aktualny; nic nie zapisano.`
- `--force` over a different copy: `Zastąpiono skill deweloperuch-cli w <folder> wersją z pakietu (pliki: <list>).`
- followed by `Agent wczyta go w nowej sesji i sam użyje przy pytaniach o ceny mieszkań, oferty deweloperów albo ceny transakcyjne.` and `Treść skilla: deweloperuch skill show · polecenia CLI bez instalacji: uvx --from deweloperuch-mcp deweloperuch --help`.

## Exit codes
| Code | Meaning |
|---|---|
| 0 | Success. |
| 1 | A file could not be read or written (`Błąd: nie udało się zainstalować skilla: …` or `Błąd: nie udało się odczytać skilla z pakietu: …`). |
| 2 | Refused, nothing written: `--dir` together with `--agent`/`--project` („Podaj --dir albo --agent/--project, nie razem: --dir to już katalog skilli.”), an empty `--dir`, a different copy without `--force` („W <folder> jest już inna wersja skilla deweloperuch-cli (zmieniona, z innej wersji pakietu albo jako dowiązanie); nic nie zapisano. Żeby ją zastąpić, dodaj --force.”), or an unknown `--agent` (a click usage error). |

## Examples
```
uvx --from deweloperuch-mcp deweloperuch skill install                  # ~/.claude/skills/deweloperuch-cli
uvx --from deweloperuch-mcp deweloperuch skill install --project        # ./.claude/skills/deweloperuch-cli
uvx --from deweloperuch-mcp deweloperuch skill install --agent codex --force
uvx --from deweloperuch-mcp deweloperuch skill install --dir ~/my-skills
uv run deweloperuch skill show
uv run deweloperuch skill path
```

Other install paths (the GitHub ones work once the release is pushed):

```
npx skills add MBratkowski/deweloperuch-mcp
/plugin marketplace add MBratkowski/deweloperuch-mcp
/plugin install deweloperuch@deweloperuch-mcp
```

The last two are Claude Code commands: marketplace `deweloperuch-mcp`, plugin `deweloperuch` (`.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`).

_Source: `src/deweloperuch_mcp/consumers/cli/commands/skill_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/agent_skill_cli_presenter.py`, `src/deweloperuch_mcp/tooling/agent_skill_installer.py`, `uv run deweloperuch skill --help`_
