"""The CLI in-process (Typer's runner), every run with its session on the test's fast
limiter.

Fixtures (registered in tests/conftest.py): ``run``.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.consumers.cli import app as cli_app
from deweloperuch_mcp.consumers.cli.app import app
from deweloperuch_mcp.throttle import (
    RequestLimiter,
)


class Cli:
    """Runs the CLI in-process; every run opens its session through ``factory``.

    ``prefix`` goes before the arguments of every run (e.g. a command group)."""

    def __init__(self, limiter: RequestLimiter, prefix: tuple[str, ...] = ()) -> None:
        self.limiter = limiter
        self.prefix = prefix
        self.sessions: list[bootstrap.Session] = []

    def factory(self) -> bootstrap.Session:
        session = bootstrap.Session(limiter=self.limiter)
        self.sessions.append(session)
        return session

    def __call__(self, *args: str) -> Any:
        return CliRunner().invoke(cli_app.app, [*self.prefix, *args], obj=self.factory)


def ok(result: Any) -> str:
    assert result.exit_code == 0, (result.exit_code, result.stderr, result.exception)
    assert result.stderr == ""
    text: str = result.stdout
    return text


@pytest.fixture
def run(limiter: RequestLimiter) -> Cli:
    """``deweloperuch ARGS`` in-process: ``run("offers", "search", "warszawa")``."""
    return Cli(limiter)


def buildings_cli(tmp_path: Path, *args: str) -> Any:
    limiter = RequestLimiter(tmp_path, min_interval=0, testing_only_allow_fast_interval=True)
    with bootstrap.sessions_from(lambda: bootstrap.Session(limiter=limiter)):
        return CliRunner().invoke(app, ["buildings", "get", *args])


@pytest.fixture
def investments_cli(limiter: RequestLimiter) -> Callable[..., Any]:
    def run(*args: str) -> Any:
        factory = lambda: bootstrap.Session(limiter=limiter)  # noqa: E731
        return CliRunner().invoke(cli_app.app, list(args), obj=factory)

    return run


def run_cli(limiter: RequestLimiter, *args: str) -> Any:
    """``deweloperuch ARGS`` in-process, its session on the test's fast limiter."""
    return CliRunner().invoke(
        cli_app.app, list(args), obj=lambda: bootstrap.Session(limiter=limiter)
    )
