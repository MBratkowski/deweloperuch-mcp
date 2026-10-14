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
GOLDEN = TESTS / "golden"
SNAPSHOT = TESTS / "snapshots" / "mcp_tools.json"
PROMPTS_SNAPSHOT = TESTS / "snapshots" / "mcp_prompts.json"
E2E = TESTS / "e2e"
THROTTLE_WORKER = TESTS / "support" / "workers" / "throttle_worker.py"
PACKAGING = REPO / "packaging"
SKILL = REPO / "skills" / "deweloperuch-cli"
"""The agent skill: the source of ``npx skills add``, the Claude Code plugin and the wheel."""
PLUGIN_MANIFESTS = REPO / ".claude-plugin"
