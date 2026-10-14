"""Builds the Claude Desktop extension ``dist/deweloperuch-mcp-<version>.mcpb`` (``make mcpb``).

1. Checks ``packaging/mcpb/manifest.json`` against ``pyproject.toml`` (the version) and
   against ``tests/snapshots/mcp_tools.json`` (the tool names, in the server's order).
2. Stages a clean copy in ``build/mcpb``: the package, the entry script as
   ``src/server.py``, the manifest with an ``icons`` array written from
   ``assets/icons/icon-<N>.png`` (copied to ``icons/``; ``icon`` stays for hosts that do
   not read ``icons``), the licence files, and ``pyproject.toml`` without the ``dev``
   dependency group with ``uv.lock`` relocked to match, so the host installs only the
   runtime dependencies (server type ``uv``: no vendored packages).
3. Validates and packs it with the official CLI, unpacks the result into
   ``build/mcpb-unpacked`` and checks that copy again (``make smoke`` then starts it).
4. Writes ``dist/server.json`` for the MCP Registry: ``packaging/registry/server.json``
   (checked against the version) with the bundle's SHA-256, which exists only once the
   bundle is packed. The release workflow attaches that copy to the GitHub Release; it is
   the one to publish (the committed placeholder fails the registry's schema on purpose).

Sends nothing to deweloperuch.pl: npx fetches the CLI from npm and ``uv lock`` may ask PyPI.
"""

import hashlib
import json
import shutil
import struct
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
SERVER_JSON = ROOT / "packaging" / "registry" / "server.json"
# Rendered from assets/icon-tiny.svg, icon-small.svg and icon.svg by `make icons`.
ICONS = ROOT / "assets" / "icons"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
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
    bundle = DIST / f"deweloperuch-mcp-{version}.mcpb"
    server = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
    check_server_json(server, version, bundle.name)
    stage()
    run(*MCPB, "validate", str(STAGE / "manifest.json"))
    run(*MCPB, "pack", str(STAGE), str(bundle))
    check_bundle(bundle)
    mcpb_package(server)["fileSha256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
    write_json(DIST / "server.json", server)
    print(f"OK: {bundle.relative_to(ROOT)} ({bundle.stat().st_size / 1024:.0f} KiB), server.json")


def check_manifest(manifest: dict[str, Any], version: str) -> None:
    """The manifest carries the package's version and lists exactly the server's tools."""
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    tools = [tool["name"] for tool in snapshot["tools"]]
    listed = [tool["name"] for tool in manifest["tools"]]
    if manifest["version"] != version:
        fail(f"manifest.json version {manifest['version']!r} != pyproject.toml {version!r}")
    if listed != tools:
        fail(f"manifest.json tools {listed} != the server's tools {tools} ({SNAPSHOT.name})")


def check_server_json(server: dict[str, Any], version: str, bundle_name: str) -> None:
    """``server.json`` names this version for the server, the PyPI package and the .mcpb URL."""
    name = SERVER_JSON.relative_to(ROOT)
    download = f"{server['repository']['url']}/releases/download/v{version}/{bundle_name}"
    pypi = [
        package["version"] for package in server["packages"] if package["registryType"] == "pypi"
    ]
    if server["version"] != version or pypi != [version]:
        fail(f"{name}: the server and its pypi package must have version {version!r}")
    if mcpb_package(server)["identifier"] != download:
        fail(f"{name}: the mcpb package identifier must be {download}")


def mcpb_package(server: dict[str, Any]) -> dict[str, Any]:
    """The one ``mcpb`` entry of ``server.json``'s ``packages``."""
    packages: list[dict[str, Any]] = server["packages"]
    (package,) = [package for package in packages if package["registryType"] == "mcpb"]
    return package


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
        (SOURCES / ".mcpbignore", ".mcpbignore"),
        (ROOT / "assets" / "icon.png", "icon.png"),
    ):
        shutil.copy2(source, STAGE / target)
    manifest = json.loads((SOURCES / "manifest.json").read_text(encoding="utf-8"))
    manifest["icons"] = stage_icons()
    write_json(STAGE / "manifest.json", manifest)
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    (STAGE / "pyproject.toml").write_text(without_dev_group(pyproject), encoding="utf-8")
    run("uv", "lock", "--directory", str(STAGE))


def stage_icons() -> list[dict[str, str]]:
    """Copies ``assets/icons/*.png`` to ``icons/`` and lists them for ``icons``, smallest first.

    The size comes from each file's PNG header, not from its name.
    """
    sized = sorted((png_size(path), path) for path in ICONS.glob("*.png"))
    if not sized:
        fail(f"no PNG icons in {ICONS.relative_to(ROOT)} (run `make icons`)")
    (STAGE / "icons").mkdir()
    for _, path in sized:
        shutil.copy2(path, STAGE / "icons" / path.name)
    return [
        {"src": f"icons/{path.name}", "size": f"{width}x{height}"}
        for (width, height), path in sized
    ]


def png_size(path: Path) -> tuple[int, int]:
    """Width and height from the IHDR chunk, which directly follows the PNG signature."""
    header = path.read_bytes()[:24]
    if header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        fail(f"{path.relative_to(ROOT)} is not a PNG file")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


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
    """The packed bundle unpacks to a valid manifest, the files it needs and nothing else.

    ``mcpb validate`` checks the ``icon`` file but not the ``icons`` ones, so they count
    as required files here.
    """
    shutil.rmtree(UNPACKED, ignore_errors=True)
    run(*MCPB, "unpack", str(bundle), str(UNPACKED))
    run(*MCPB, "validate", str(UNPACKED / "manifest.json"))
    manifest = json.loads((UNPACKED / "manifest.json").read_text(encoding="utf-8"))
    required = [*REQUIRED, *(icon["src"] for icon in manifest["icons"])]
    missing = [name for name in required if not (UNPACKED / name).is_file()]
    unwanted = [name for name in FORBIDDEN if (UNPACKED / name).exists()]
    unwanted += [str(path.relative_to(UNPACKED)) for path in UNPACKED.rglob("__pycache__")]
    if missing or unwanted:
        fail(f"{bundle.name}: missing {missing}, unwanted {unwanted}")


def write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(*command: str) -> None:
    print("$", " ".join(command), flush=True)
    subprocess.run(command, check=True, cwd=ROOT)


def fail(message: str) -> NoReturn:
    sys.exit(f"mcpb build: {message}")


if __name__ == "__main__":
    main()
