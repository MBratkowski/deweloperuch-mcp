"""recon/config.py works without the installed package and shares the one limiter."""

import ast
import json
import subprocess
import sys
from pathlib import Path

from support.paths import REPO

RECON = REPO / "recon"
CONFIG = RECON / "config.py"
SRC = REPO / "src"

# Runs the way `python3 recon/<script>.py` does: recon/ first on sys.path.
PROBE = f"""
import json, sys
sys.path.insert(0, {str(RECON)!r})
import config
from deweloperuch_mcp import allowlist, flight, http_policy, identity, retry_after, throttle
loaded = sorted(sys.modules)
print(json.dumps({{
    "user_agent_is_shared": config.USER_AGENT is identity.USER_AGENT,
    "user_agent": config.USER_AGENT,
    "base_url_is_shared": config.BASE_URL is identity.BASE_URL,
    "limiter_is_shared": config.RequestLimiter is throttle.RequestLimiter
        and config.StoppedError is throttle.StoppedError,
    "retry_after_is_shared": config.parse_retry_after is retry_after.parse_retry_after,
    "policy_is_shared": config.stop_reason is http_policy.stop_reason
        and config.stop_cause is http_policy.stop_cause,
    "flight_is_shared": config.component_props is flight.component_props
        and config.with_rsc_token is flight.with_rsc_token,
    "allowlist_is_shared": config.match_api is allowlist.match_api
        and config.API_PATHS is allowlist.API_PATHS,
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
    assert data["retry_after_is_shared"] is True
    assert data["policy_is_shared"] is True
    assert data["flight_is_shared"] is True
    assert data["allowlist_is_shared"] is True
    assert Path(str(data["throttle_file"])) == REPO / "src" / "deweloperuch_mcp" / "throttle.py"
    assert str(data["default_lock_dir"]).endswith("deweloperuch-mcp")
    assert data["non_stdlib"] == []


def test_config_reexports_user_agent_and_base_url(tmp_path: Path) -> None:
    """One definition (D9): the values are pinned in tests/architecture/test_identity.py."""
    data = run_isolated(tmp_path)

    assert data["user_agent_is_shared"] is True
    assert data["base_url_is_shared"] is True


def test_config_user_agent_without_package_metadata(tmp_path: Path) -> None:
    """A bare python3 sees no installed package: the project still names itself."""
    data = run_isolated(tmp_path)

    assert data["user_agent"] == (
        "deweloperuch-mcp/0+unknown (+https://github.com/MBratkowski/deweloperuch-mcp)"
    )


def test_config_refuses_old_python_before_importing_the_package(tmp_path: Path) -> None:
    data = run_isolated(tmp_path, OLD_PYTHON)

    assert data["package_loaded"] is False
    message = str(data["message"])
    assert "3.11" in message
    assert "3.9" in message


def test_config_parses_on_old_python() -> None:
    """The version check must be reachable: no newer syntax before or around it."""
    ast.parse(CONFIG.read_text(encoding="utf-8"), feature_version=(3, 9))


def test_config_does_not_redefine_identity_constants() -> None:
    """Re-export only; unlike the ``is`` check above, string interning cannot fool this."""
    tree = ast.parse(CONFIG.read_text(encoding="utf-8"))
    from_identity = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "deweloperuch_mcp.identity"
        for alias in node.names
    }
    bound_here = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }

    assert {"BASE_URL", "USER_AGENT"} <= from_identity
    assert bound_here.isdisjoint({"BASE_URL", "USER_AGENT"})


def package_files_loaded_by_config() -> list[Path]:
    """The package's ``__init__.py`` (runs first) and every submodule config.py imports."""
    tree = ast.parse(CONFIG.read_text(encoding="utf-8"))
    submodules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("deweloperuch_mcp.")
    }
    assert submodules, "recon/config.py imports no deweloperuch_mcp.<module>"
    return [SRC / "deweloperuch_mcp" / "__init__.py"] + sorted(
        SRC.joinpath(*module.split(".")).with_suffix(".py") for module in submodules
    )


def test_shared_parsers_are_checked_for_stdlib_imports() -> None:
    """recon gets the Retry-After parser, the response policy, the RSC decoder and the
    allowlist through config, so the check below covers them."""
    names = {path.name for path in package_files_loaded_by_config()}

    assert {
        "identity.py",
        "retry_after.py",
        "throttle.py",
        "http_policy.py",
        "flight.py",
        "allowlist.py",
    } <= names


def test_recon_loaded_modules_import_only_stdlib() -> None:
    """recon/ scripts import these files without the package's dependencies."""
    imported: dict[str, list[str]] = {}
    for path in package_files_loaded_by_config():
        name = str(path.relative_to(SRC))
        imported[name] = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported[name] += [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, f"{name}: relative imports pull in the package"
                assert node.module is not None
                imported[name].append(node.module)

    assert any(imported.values()), "parser found no imports at all"
    # A module of the package counts only if it is one of these files, checked here too
    # (throttle takes the STOP texts from http_policy).
    checked = {
        "deweloperuch_mcp." + str(path.relative_to(SRC / "deweloperuch_mcp").with_suffix(""))
        for path in package_files_loaded_by_config()
        if path.name != "__init__.py"
    }
    non_stdlib = {
        name: [
            m
            for m in modules
            if m.split(".")[0] not in sys.stdlib_module_names and m not in checked
        ]
        for name, modules in imported.items()
    }
    assert non_stdlib == {name: [] for name in imported}
