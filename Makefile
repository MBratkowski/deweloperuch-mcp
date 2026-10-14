# Quality gates. Every target is offline: no target sends a request to the service
# (the live e2e suite is a separate, opt-in run; see CONTRIBUTING.md and
# docs/decisions.md D10).

.PHONY: fast check lint format-check types imports test dead complexity duplicates

## fast: what to run before every hand-over (a few seconds)
fast: lint format-check types imports

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .

types:
	uv run mypy src tests recon

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
