# `deweloperuch investments get`
Shows an investment (a development project) with its developer, the average prices of active offers and a list of offers (active first). Equivalent to the MCP tool [`get_investment`](../../mcp/tools/get_investment.md).

## Usage
```
deweloperuch investments get [OPTIONS] SLUG
```

`--help` description: „Pokaż inwestycję z deweloperem i ofertami.”

## Options
| Flag | Type | Default | Description |
|---|---|---|---|
| `SLUG` (argument, required) | text | — | The investment slug (investment_slug from `offers search`). Help text: „Slug inwestycji (investment_slug z `offers search`).” |
| `--history` | flag | off | Attach the price history of each offer. It costs no extra request and is not slower: the events come in the same reply of the service as the investment. Help text: „Dołącz historię ceny każdej oferty.” |
| `--limit` | int | none (all offers) | The maximum number of offers shown (active first); all by default. In MCP `limit` defaults to 20 with a maximum of 200; the CLI without `--limit` shows all offers. Help text: „Najwięcej pokazanych ofert (najpierw aktywne); domyślnie wszystkie.” |
| `--json` | flag | off | Print the result as JSON (the domain model; with the links `investment_url` and `developer_url`, the `offers` entries without links). Help text: „Wypisz wynik jako JSON (model domenowy).” |
| `--help` | flag | | Show the help. |

## Exit codes
See the [exit code table](../README.md#exit-codes). Most common: 0, 2 (bad slug or `--limit` outside 0–100000), 3 STOP, 6 the service moved or removed the route (`Błąd: Inwestycja 'smolna': Narzędzie nie może pobrać tych danych, …`) or, with `--history`, the histories are off the contract (`Błąd: Historia cen inwestycji 'smolna': Dane z serwisu nie pasują do kontraktu klienta (inny format). Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to użytkownikowi. Zamiast tego możesz pobrać inwestycję bez include_history albo historię jednej oferty przez get_offer.`), 7 no such investment.

The histories are read strictly: if the events of one offer are off the contract, `--history` fails for the whole investment (exit code 6, nothing printed), and the message points to the call without `--history` or to the history of one offer. The message is shared with the MCP tool, so it names `include_history` and `get_offer`; in the CLI that is `investments get SLUG` without `--history`, and `offers get OFFER_ID --investment SLUG`.

## Examples
```
deweloperuch investments get smolna
deweloperuch investments get smolna --limit 2
deweloperuch investments get smolna --history --json
```

Text output with `--limit 2` (derived from `tests/golden/cli/investments_get.json`, sample `api.map_inv_visible`):

```
Smolna [smolna] · aktywna
Strona inwestycji: https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna
Miejsce: Sopot [sopot], Świemirowo · 54.42736, 18.55839
Deweloper: Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]
Profil dewelopera: https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna
Średnio (aktywne oferty): 1 566 392 PLN · 63,97 m² · 24 487,63 PLN/m²
Oferty: aktywne 3 z 16 · pokazano 2 · pominięto 1 (zwiększ --limit).
[206087] C234 · 1 679 796 PLN · 65,9 m² · 25 490,08 PLN/m² · aktywna
[2377] C224 · 1 620 175 PLN · 69,5 m² · 23 311,87 PLN/m² · aktywna · od pierwszej ceny +175 PLN (+0,01%)
```

The lines „Strona inwestycji” (investment page) and „Profil dewelopera” (developer profile) are omitted when the slug is missing.

With `--history` (`tests/golden/cli/investments_get_history_limit_1.json`, `investments get smolna --history --limit 1`, the real answer captured on 2026-10-31) each offer is followed by its events, oldest first; the call sends one request:

```
Smolna [smolna] · aktywna
Strona inwestycji: https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna
Miejsce: Sopot [sopot], Świemirowo · 54.42736, 18.55839
Deweloper: Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]
Profil dewelopera: https://deweloperuch.pl/ceny-ofertowe/sopot/deweloperzy/invest-komfort-spolka-akcyjna
Średnio (aktywne oferty): 2 108 801 PLN · 70,31 m² · 29 992,91 PLN/m²
Oferty: aktywne 4 z 17 · pokazano 1 · pominięto 16 (zwiększ --limit).
[206523] C121 · 3 735 107 PLN · 95,49 m² · 39 115,16 PLN/m² · aktywna
  2026-10-24  cena          3 735 107 PLN
```

An offer with a withdrawal and a return (`tests/golden/cli/investments_get_history.json`, the same call without `--limit`):

```
[2377] C224 · 1 620 768 PLN · 66,36 m² · 24 423,87 PLN/m² · aktywna · od pierwszej ceny +768 PLN (+0,05%)
  2025-02-25  cena          1 620 000 PLN
  2025-02-25  wycofanie     1 620 000 PLN
  2026-10-03  przywrócenie  1 620 175 PLN
  2026-10-03  cena          1 620 175 PLN
  2026-10-24  cena          1 620 768 PLN
```

_Source: `src/deweloperuch_mcp/consumers/cli/commands/investments_commands.py`, `src/deweloperuch_mcp/consumers/cli/presenters/get_investment_cli_presenter.py`, `uv run deweloperuch investments get --help`_
