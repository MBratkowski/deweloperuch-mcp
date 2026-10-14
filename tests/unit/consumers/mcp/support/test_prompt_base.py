"""Tests of ``deweloperuch_mcp.consumers.mcp.support.prompt_base``."""

import pytest

from deweloperuch_mcp.consumers.mcp.support.prompt_base import ASK_USER, PromptBase


@pytest.mark.parametrize(
    ("value", "seen"),
    [
        ("Kraków", "Kraków"),
        ("  Gdańsk \t", "Gdańsk"),
        ("", None),
        ("  ", None),
        (None, None),
        ("Łódź\x1b[31m\nx", "Łódź\\x1b[31m\\x0ax"),
    ],
)
def test_an_argument_is_trimmed_and_escaped_and_empty_is_not_given(
    value: str | None, seen: str | None
) -> None:
    """Clients send prompt arguments as text, an optional one left empty as ``""``; the
    message quotes the value on one line, without terminal sequences."""
    assert PromptBase.given(value) == seen


def test_a_required_argument_left_empty_asks_the_user() -> None:
    """The client checks that a required argument is there, not that it says anything."""
    assert PromptBase.required(" ") == ASK_USER == "(nie podano, zapytaj użytkownika)"
    assert PromptBase.required(" Sopot ") == "Sopot"
