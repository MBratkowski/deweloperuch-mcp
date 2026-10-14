"""Stand-ins of pytest's items and config, for the offline checks of the live suite's gate."""

from types import SimpleNamespace
from typing import Any

import pytest


class FakeItem:
    def __init__(self, marked_live: bool) -> None:
        self.marked_live = marked_live
        self.added: list[pytest.MarkDecorator] = []

    def get_closest_marker(self, name: str) -> object | None:
        return object() if name == "live" and self.marked_live else None

    def add_marker(self, marker: pytest.MarkDecorator) -> None:
        self.added.append(marker)


def fake_config(markexpr: str) -> Any:
    return SimpleNamespace(option=SimpleNamespace(markexpr=markexpr))
