"""Tests of ``deweloperuch_mcp.cli``."""

import tomllib
from importlib import import_module

import deweloperuch_mcp.cli
from deweloperuch_mcp.consumers.cli import app as cli_app
from support.paths import REPO

ROOT = REPO


def test_project_scripts_point_to_the_adapters() -> None:
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]

    assert scripts == {
        "deweloperuch": "deweloperuch_mcp.cli:main",
        "deweloperuch-mcp": "deweloperuch_mcp.mcp_server:main",
    }
    for target in scripts.values():
        module, name = target.split(":")
        assert callable(getattr(import_module(module), name))


def test_the_script_module_is_a_shim_of_the_interface() -> None:
    assert deweloperuch_mcp.cli.main is cli_app.main
    assert deweloperuch_mcp.cli.__all__ == ["main"]
