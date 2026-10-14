# Golden outputs

Characterization tests pin what the CLI and the MCP tools return, one JSON file per case: texts, error messages, exit codes, log lines and the exact requests sent to the mocked service. A refactor must leave every file unchanged.

## Layout

- `cli/<case>.json`: the arguments, the exit code, stdout and stderr as lists of lines, and the requests the mocked service received. Cases are defined in `tests/support/golden/cli_cases/` (one module per operation) and run by `tests/characterization/cli/`.
- `mcp/<case>.json`: the tool calls; for each result `is_error`, the text and `structured_content`; the server's log lines at INFO and above; and the requests. A text that is exactly the structured content as compact JSON is stored as the placeholder `"<the structured content as compact JSON>"`. Cases are defined in `tests/support/golden/mcp_cases/` (one module per tool) and run by `tests/characterization/mcp/`.
- Each request is recorded as `GET <url> [rsc: 1] [accept: …]`: the full URL with its query parameters in the order sent, so any change in how search criteria map to the service's parameters fails here.

## How the service is mocked

respx serves the samples from `docs/discovery/samples/` and the raw payloads from `tests/fixtures/` (`tests/support/providers/network.py` and the routes in `tests/support/providers/routes/`). No test opens a network socket.

Only volatile values are replaced by placeholders: timestamps, PIDs, the seconds left of a pause and temporary paths (`scrub` in `tests/support/checks/golden.py`). Nothing else is normalised.

## Updating after an intended change

Only when the output is meant to change:

```sh
DEWELOPERUCH_UPDATE_GOLDEN=1 uv run pytest tests/characterization
```

The switch rewrites the files of the cases that ran. `git diff --stat tests/golden` then lists the cases that changed; review every diff before committing. A case removed from the matrix leaves its file behind, and `test_every_recorded_cli_case_is_still_a_case` (or its MCP twin) fails until you delete that file deliberately.

The MCP tool listing (names, descriptions, schemas, annotations) is not stored here. It is pinned by `tests/snapshots/mcp_tools.json`:

```sh
DEWELOPERUCH_UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/consumers/mcp/test_server.py
```
