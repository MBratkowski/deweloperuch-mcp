# Quality gates and packaging. No target sends a request to the service (the live e2e
# suite is a separate, opt-in run; see CONTRIBUTING.md and docs/decisions.md D10). The
# quality gates are offline; package, mcpb and smoke fetch tools and dependencies from
# npm and PyPI.

.PHONY: fast check lint format-check types imports test dead complexity duplicates \
	package mcpb smoke

## fast: what to run before every hand-over (a few seconds)
fast: lint format-check types imports

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .

types:
	uv run mypy src tests recon packaging

imports:
	uv run lint-imports

## check: fast + the offline tests + dead code + reports (complexity, duplication)
check: fast test dead complexity duplicates

# DEWELOPERUCH_LIVE is dropped so tests/e2e stays skipped whatever the shell has set.
test:
	env -u DEWELOPERUCH_LIVE uv run pytest -q

# Unused code at 80% confidence; the whitelist is [tool.vulture] in pyproject.toml.
dead:
	uv run vulture

# Report, not a gate (stage 2 gates it): blocks above rank B (radon cyclomatic
# complexity, which also counts boolean operators), modules above A.
complexity:
	@echo "== complexity report: blocks ranked C or worse (not a gate yet)"
	-@uv run xenon --max-absolute B --max-modules A --max-average A src recon

# Report, not a gate (stage 3 gates it): similar blocks of at least 4 lines.
duplicates:
	@echo "== duplicate-code report (not a gate yet)"
	@uv run pylint --disable=all --enable=duplicate-code --exit-zero --score=n src recon

## package: the wheel, the sdist and the Claude Desktop extension (.mcpb) in dist/
package:
	uv build --clear
	uv run python packaging/mcpb/build.py

## mcpb: only the extension, dist/deweloperuch-mcp-<version>.mcpb (needs Node.js for npx)
mcpb:
	uv run python packaging/mcpb/build.py

## smoke: start the built wheel and the unpacked extension as an MCP client does
## (initialize + tools/list, no tool call, so no request to the service); run `package` first
WHEEL = dist/deweloperuch_mcp-$(shell uv version --short)-py3-none-any.whl
smoke:
	uv run python packaging/smoke.py -- \
		uvx --isolated --refresh-package deweloperuch-mcp --from $(WHEEL) deweloperuch-mcp
	uvx --isolated --from $(WHEEL) deweloperuch --help > /dev/null
	uv run python packaging/smoke.py -- uv run --directory build/mcpb-unpacked src/server.py
