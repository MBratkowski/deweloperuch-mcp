"""recon/config.py works without the installed package and shares the one limiter."""

import ast
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RECON = REPO / "recon"
CONFIG = RECON / "config.py"

# TODO(U1): the user chooses the final User-Agent (D9). Changing it must be a
# deliberate decision, so the current value is pinned here.
EXPECTED_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

# Runs the way `python3 recon/<script>.py` does: recon/ first on sys.path.
PROBE = f"""
import json, sys
sys.path.insert(0, {str(RECON)!r})
import config
from deweloperuch_mcp import throttle
loaded = sorted(sys.modules)
print(json.dumps({{
    "user_agent": config.USER_AGENT,
    "base_url": config.BASE_URL,
    "limiter_is_shared": config.RequestLimiter is throttle.RequestLimiter,
    "default_lock_dir": str(config.default_lock_dir()),
    "throttle_file": throttle.__file__,
    "site_loaded": "site" in sys.modules,
    "non_stdlib": [
        m for m in loaded
        if m.split(".")[0] not in sys.stdlib_module_names
        and m.split(".")[0] not in ("config", "deweloperuch_mcp", "__main__")
    ],
}}))
"""

# The macOS system python3 is 3.9: simulate it and expect a clean exit before
# anything from the package (which needs 3.11) is imported.
OLD_PYTHON = f"""
import json, sys
sys.version_info = (3, 9, 6, "final", 0)
sys.path.insert(0, {str(RECON)!r})
try:
    import config
except SystemExit as exc:
    print(json.dumps({{
        "message": str(exc.code),
        "package_loaded": any(m.startswith("deweloperuch_mcp") for m in sys.modules),
    }}))
"""


def run_isolated(tmp_path: Path, code: str = PROBE) -> dict[str, object]:
    # -I: ignore PYTHON* env vars, user site and cwd; -S: no site-packages at all,
    # so the installed package and its dependencies are out of reach.
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data: dict[str, object] = json.loads(result.stdout)
    return data


def test_config_exposes_limiter_without_installed_package(tmp_path: Path) -> None:
    data = run_isolated(tmp_path)

    assert data["site_loaded"] is False
    assert data["limiter_is_shared"] is True
    assert Path(str(data["throttle_file"])) == REPO / "src" / "deweloperuch_mcp" / "throttle.py"
    assert str(data["default_lock_dir"]).endswith("deweloperuch-mcp")
    assert data["non_stdlib"] == []


def test_config_exposes_user_agent_and_base_url(tmp_path: Path) -> None:
    data = run_isolated(tmp_path)

    assert data["user_agent"] == EXPECTED_USER_AGENT
    base_url = str(data["base_url"])
    assert base_url.startswith("https://")
    assert base_url.endswith("deweloperuch.pl")


def test_config_refuses_old_python_before_importing_the_package(tmp_path: Path) -> None:
    data = run_isolated(tmp_path, OLD_PYTHON)

    assert data["package_loaded"] is False
    message = str(data["message"])
    assert "3.11" in message
    assert "3.9" in message


def test_config_parses_on_old_python() -> None:
    """The version check must be reachable: no newer syntax before or around it."""
    ast.parse(CONFIG.read_text(encoding="utf-8"), feature_version=(3, 9))
