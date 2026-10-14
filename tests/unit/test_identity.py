"""The version in the User-Agent: the installed package's, or a marker without metadata."""

from importlib import metadata

import pytest

from deweloperuch_mcp import identity


def test_version_comes_from_the_package_metadata() -> None:
    assert identity.installed_version() == metadata.version("deweloperuch-mcp")


def test_version_without_package_metadata_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """``python3 recon/<script>.py`` imports the sources, but no package is installed."""

    def not_installed(name: str) -> str:
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", not_installed)

    assert identity.installed_version() == "0+unknown"


def test_user_agent_carries_the_installed_version() -> None:
    product = identity.USER_AGENT.split(" ", 1)[0]

    assert product == f"deweloperuch-mcp/{identity.installed_version()}"
