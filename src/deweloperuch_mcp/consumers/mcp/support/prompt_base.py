"""``PromptBase``: what every MCP prompt (``consumers/mcp/prompts/*_prompt.py``) is (D17).

A prompt is a conversation starter a person picks in the MCP client (a slash command, a
menu entry). Its ``name``, ``title`` and ``description`` are class attributes; its
arguments are the parameters of ``render``, each a text with a ``Field`` description
(the protocol passes prompt arguments as strings); ``render`` returns the text of the one
user message, which tells the model which tools to use, in what order, and what to
show. A prompt is only text: it calls no tool and sends no request (the conventions test
checks what it imports). The server registers ``render`` of each prompt (``PROMPTS``).
"""

from abc import ABC, abstractmethod
from typing import Any

from deweloperuch_mcp.consumers.shared.text import printable

ASK_USER = "(nie podano, zapytaj użytkownika)"
"""Stands for a required argument the client sent empty."""


class PromptBase(ABC):
    """The base of the ``*Prompt`` classes; subclasses set the attributes and ``render``."""

    name: str
    title: str
    description: str

    @abstractmethod
    def render(self, *args: Any, **kwargs: Any) -> str:
        """The prompt's arguments, as its listing names them; the user message's text."""

    @staticmethod
    def given(value: str | None) -> str | None:
        """An argument as the message quotes it: trimmed, on one line, without terminal
        sequences (``printable``); ``None`` when the client left it out or empty."""
        if value is None or not value.strip():
            return None
        return printable(value.strip())

    @classmethod
    def required(cls, value: str) -> str:
        """A required argument as the message quotes it; ``ASK_USER`` when it is empty
        (the client checks that the argument is there, not that it says anything)."""
        return cls.given(value) or ASK_USER
