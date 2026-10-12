# Golden outputs (characterization tests)

What the CLI and the MCP tools answered on the code before the D13 refactor, one JSON file per case. The refactor must not change any of them: not a text, a message, an exit code, a log line or a request URL.

- `cli/<case>.json`: the arguments, the exit code, stdout and stderr as lists of lines, and the requests the mocked service got. Cases: `tests/test_golden_cli.py`.
- `mcp/<case>.json`: the tool calls, each result (`is_error`, the text, `structured_content`), the server's log lines at INFO and above, and the requests. A text that is exactly the structured content as compact JSON is recorded as `"<the structured content as compact JSON>"`. Cases: `tests/test_golden_mcp.py`.
- Requests are `GET <url> [rsc: 1] [accept: …]`: the full URL with its query in the order sent, so a changed mapping of search criteria to the service's parameters fails here.

The service is mocked by respx with the samples in `docs/discovery/samples/` and the real RSC pages in `tests/fixtures/rsc/` (`tests/service_mocks.py`); no test opens a network socket. Times, PIDs, seconds left of a pause and temporary paths are replaced by placeholders (`tests/golden_support.py`, `scrub`); nothing else is.

## After an intended change

Only when the output is meant to change:

```
DEWELOPERUCH_UPDATE_GOLDEN=1 uv run pytest tests/test_golden_cli.py tests/test_golden_mcp.py
```

The switch rewrites the files of the cases that ran. `git diff --stat tests/golden` lists the cases that moved; review each diff. A case removed from the matrix leaves its file behind and fails `test_every_recorded_*_case_is_still_a_case`: delete the file on purpose.

The tool listing (names, descriptions, schemas) is not here: it is pinned by `tests/snapshots/mcp_tools.json` (`DEWELOPERUCH_UPDATE_SNAPSHOTS=1`, `tests/test_mcp_server.py`).
