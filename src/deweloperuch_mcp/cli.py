"""The entry point of the ``deweloperuch`` script (``[project.scripts]``, kept so an
installed environment needs no reinstall): the command line is ``consumers.cli`` (D16)."""

from deweloperuch_mcp.consumers.cli.app import main

__all__ = ["main"]
