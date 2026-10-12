"""The interfaces (D13): the ``deweloperuch`` command line (``cli``) and the MCP server
(``mcp``), over the use cases.

They parse their input with the application's parameter contract
(``application.arguments``), run the use cases of a session (``bootstrap``) and present
the results (``views``, ``cli.text``, ``mcp.presenters``). They import only the
application, the domain, the composition root, themselves and their libraries (typer,
mcp, pydantic): tests/test_layering.py.
"""
