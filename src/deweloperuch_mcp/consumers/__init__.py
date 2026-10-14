"""The consumers (D16, D17): the ``deweloperuch`` command line (``cli``) and the MCP server
(``mcp``), over the use cases.

- ``mcp``: ``server`` registers the tools of ``tools/`` (``*Tool`` classes); their
  ``presenters/`` shape the results for a model; ``support/`` holds the tool base, the
  input types, the runner and the base of the results;
- ``cli``: ``app`` registers the command groups of ``commands/``; their ``presenters/``
  print the results; ``support/`` runs a command in a session and writes Polish text;
- ``shared``: what both present (the views, the choices, the escaping of text).

A tool or a command parses its request (``usecases``: ``*Request.parse``), executes the
use case of a session (``bootstrap``) and hands the result to its presenter. Imports:
``usecases``, ``models``, the composition root, themselves and their libraries (typer,
mcp, pydantic); the CLI and the MCP server never import each other
(tests/architecture/test_layering.py).
"""
