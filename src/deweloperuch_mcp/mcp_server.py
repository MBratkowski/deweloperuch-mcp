"""The entry point of the ``deweloperuch-mcp`` script (``[project.scripts]``, kept so an
installed environment needs no reinstall): the server is ``interfaces.mcp`` (D13)."""

from deweloperuch_mcp.interfaces.mcp.server import main

__all__ = ["main"]
