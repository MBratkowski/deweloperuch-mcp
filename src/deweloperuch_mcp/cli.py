"""The entry point of the ``deweloperuch`` script (``[project.scripts]``, kept so an
installed environment needs no reinstall): the command line is ``interfaces.cli`` (D13)."""

from deweloperuch_mcp.interfaces.cli.app import main

__all__ = ["main"]
