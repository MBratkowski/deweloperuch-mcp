"""Builds the Claude Desktop extension ``dist/deweloperuch-mcp-<version>.mcpb`` (``make mcpb``).

1. Checks ``packaging/mcpb/manifest.json`` against ``pyproject.toml`` (the version) and
   against ``tests/snapshots/mcp_tools.json`` (the tool names, in the server's order).
2. Stages a clean copy in ``build/mcpb``: the package, the entry script as
   ``src/server.py``, the manifest, the icon, the licence files, and ``pyproject.toml``
   without the ``dev`` dependency group with ``uv.lock`` relocked to match, so the host
   installs only the runtime dependencies (server type ``uv``: no vendored packages).
3. Validates and packs it with the official CLI, unpacks the result into
   ``build/mcpb-unpacked`` and checks that copy again (``make smoke`` then starts it).

Sends nothing to deweloperuch.pl: npx fetches the CLI from npm and ``uv lock`` may ask PyPI.
"""

import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "packaging" / "mcpb"
STAGE = ROOT / "build" / "mcpb"
UNPACKED = ROOT / "build" / "mcpb-unpacked"
DIST = ROOT / "dist"
SNAPSHOT = ROOT / "tests" / "snapshots" / "mcp_tools.json"
# The CLI version the bundle was validated with; bump it deliberately.
MCPB = ("npx", "-y", "@anthropic-ai/mcpb@2.1.2")
COPIED = ("uv.lock", "README.md", "LICENSE", "NOTICE", ".python-version")
REQUIRED = (
    "manifest.json",
    "icon.png",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "LICENSE",
    "NOTICE",
    "src/server.py",
    "src/deweloperuch_mcp/__init__.py",
)
FORBIDDEN = ("server/lib", "server/venv", ".venv", "tests", "docs", "recon")


def main() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    check_manifest(json.loads((SOURCES / "manifest.json").read_text(encoding="utf-8")), version)
    stage()
    run(*MCPB, "validate", str(STAGE / "manifest.json"))
    bundle = DIST / f"deweloperuch-mcp-{version}.mcpb"
    run(*MCPB, "pack", str(STAGE), str(bundle))
    check_bundle(bundle)
    print(f"OK: {bundle.relative_to(ROOT)} ({bundle.stat().st_size / 1024:.0f} KiB)")


def check_manifest(manifest: dict[str, Any], version: str) -> None:
    """The manifest carries the package's version and lists exactly the server's tools."""
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    tools = [tool["name"] for tool in snapshot["tools"]]
    listed = [tool["name"] for tool in manifest["tools"]]
    if manifest["version"] != version:
        fail(f"manifest.json version {manifest['version']!r} != pyproject.toml {version!r}")
    if listed != tools:
        fail(f"manifest.json tools {listed} != the server's tools {tools} ({SNAPSHOT.name})")


def stage() -> None:
    shutil.rmtree(STAGE, ignore_errors=True)
    shutil.copytree(
        ROOT / "src" / "deweloperuch_mcp",
        STAGE / "src" / "deweloperuch_mcp",
        ignore=shutil.ignore_patterns("__pycache__", "*.py[cod]"),
    )
    for name in COPIED:
        shutil.copy2(ROOT / name, STAGE / name)
    for source, target in (
        (SOURCES / "server.py", "src/server.py"),
        (SOURCES / "manifest.json", "manifest.json"),
        (SOURCES / ".mcpbignore", ".mcpbignore"),
        (ROOT / "assets" / "icon.png", "icon.png"),
    ):
        shutil.copy2(source, STAGE / target)
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    (STAGE / "pyproject.toml").write_text(without_dev_group(pyproject), encoding="utf-8")
    run("uv", "lock", "--directory", str(STAGE))


def without_dev_group(pyproject: str) -> str:
    """``pyproject.toml`` without its ``[dependency-groups]`` table (the dev tools).

    Drops the lines from that header to the next table header; the result must parse
    to the same document minus that table.
    """
    kept: list[str] = []
    skipping = False
    for line in pyproject.splitlines(keepends=True):
        if line.startswith("["):
            skipping = line.strip() == "[dependency-groups]"
        if not skipping:
            kept.append(line)
    trimmed = "".join(kept)
    expected = tomllib.loads(pyproject)
    expected.pop("dependency-groups", None)
    if tomllib.loads(trimmed) != expected:
        fail("removing [dependency-groups] from pyproject.toml changed other tables")
    return trimmed


def check_bundle(bundle: Path) -> None:
    """The packed bundle unpacks to a valid manifest, the files it needs and nothing else."""
    shutil.rmtree(UNPACKED, ignore_errors=True)
    run(*MCPB, "unpack", str(bundle), str(UNPACKED))
    run(*MCPB, "validate", str(UNPACKED / "manifest.json"))
    missing = [name for name in REQUIRED if not (UNPACKED / name).is_file()]
    unwanted = [name for name in FORBIDDEN if (UNPACKED / name).exists()]
    unwanted += [str(path.relative_to(UNPACKED)) for path in UNPACKED.rglob("__pycache__")]
    if missing or unwanted:
        fail(f"{bundle.name}: missing {missing}, unwanted {unwanted}")


def run(*command: str) -> None:
    print("$", " ".join(command), flush=True)
    subprocess.run(command, check=True, cwd=ROOT)


def fail(message: str) -> NoReturn:
    sys.exit(f"mcpb build: {message}")


if __name__ == "__main__":
    main()
