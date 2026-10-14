"""``ToolBase``: what every exposed MCP tool (``consumers/mcp/tools/*_tool.py``) is (D17).

A tool is a class: its ``name``, ``title``, ``description`` and ``annotations`` are class
attributes, its input schema is the signature of its ``async __call__`` (the SDK reads
the parameters' annotations, D11), and ``__call__`` parses the request, executes the use
case and hands the result to the tool's presenter (``consumers/mcp/presenters``), in a
worker thread (``calls.run``). The server registers ``handler()`` of each tool.
"""

import functools
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.types import CallToolResult, ToolAnnotations

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)
"""Read-only: nothing changes anywhere. Open world: the data comes from an outside service
and changes over time. idempotentHint and destructiveHint are left out: the spec gives
them meaning only for tools that are not read-only."""


class ToolBase(ABC):
    """The base of the ``*Tool`` classes; subclasses set the attributes and ``__call__``."""

    name: str
    title: str
    description: str
    annotations: ToolAnnotations = READ_ONLY

    @abstractmethod
    async def __call__(self, *args: Any, **kwargs: Any) -> CallToolResult:
        """The tool's arguments, as its input schema names them; the result for the model."""

    def handler(self) -> Callable[..., Awaitable[CallToolResult]]:
        """``__call__`` as the function the SDK registers, under the tool's name: the SDK
        names the input schema after the function (``<name>Arguments``) and reads the
        parameters from its signature (``__wrapped__``: without ``self``)."""
        call = self.__call__

        async def handler(*args: Any, **kwargs: Any) -> CallToolResult:
            return await call(*args, **kwargs)

        functools.update_wrapper(handler, call)
        handler.__name__ = handler.__qualname__ = self.name
        return handler
