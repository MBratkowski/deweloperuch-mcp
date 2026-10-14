"""Entry point of the Claude Desktop extension (``src/server.py`` inside the .mcpb).

The host runs ``uv run --directory <bundle> src/server.py``: uv installs the package and
its dependencies from the bundle's ``pyproject.toml`` and ``uv.lock``, and this script
starts the same stdio server as the ``deweloperuch-mcp`` command.
"""

from deweloperuch_mcp.mcp_server import main

if __name__ == "__main__":
    main()
