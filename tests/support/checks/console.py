"""A fixed Rich console for the CLI's byte-for-byte golden comparisons."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from unittest.mock import patch

from rich.console import Console
from typer import rich_utils


@contextmanager
def stable_rich_console() -> Iterator[None]:
    """Keep the recorded 100 columns and box style even on legacy Windows consoles."""
    with (
        patch.object(rich_utils, "Console", partial(Console, legacy_windows=False)),
        patch.object(rich_utils, "MAX_WIDTH", 100),
    ):
        yield
