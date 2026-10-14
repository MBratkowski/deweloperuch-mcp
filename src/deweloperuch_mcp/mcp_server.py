"""The entry point of the ``deweloperuch-mcp`` script (``[project.scripts]``, kept so an
installed environment needs no reinstall): the server is ``consumers.mcp`` (D16)."""

from deweloperuch_mcp.consumers.mcp.server import main

__all__ = ["main"]
