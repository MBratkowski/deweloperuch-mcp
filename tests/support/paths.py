"""Where the repository's code, test data and test scripts are."""

from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent
REPO = TESTS.parent
SRC = REPO / "src"
PACKAGE_SOURCE = SRC / "deweloperuch_mcp"
RECON = REPO / "recon"
SAMPLES = REPO / "docs" / "discovery" / "samples"
FIXTURES = TESTS / "fixtures"
RSC_FIXTURES = FIXTURES / "rsc"
API_FIXTURES = FIXTURES / "api"
REPO_STATS_FIXTURES = FIXTURES / "repo_stats"
"""GitHub's and pypistats.org's responses about this repository (not the service's)."""
STATS_SCRIPT = REPO / ".github" / "scripts" / "archive_stats.py"
"""The daily archive of the project's statistics (.github/workflows/stats.yml)."""
GOLDEN = TESTS / "golden"
SNAPSHOT = TESTS / "snapshots" / "mcp_tools.json"
PROMPTS_SNAPSHOT = TESTS / "snapshots" / "mcp_prompts.json"
E2E = TESTS / "e2e"
THROTTLE_WORKER = TESTS / "support" / "workers" / "throttle_worker.py"
PACKAGING = REPO / "packaging"
SKILL = REPO / "skills" / "deweloperuch-cli"
"""The agent skill: the source of ``npx skills add``, the Claude Code plugin and the wheel."""
PLUGIN_MANIFESTS = REPO / ".claude-plugin"
