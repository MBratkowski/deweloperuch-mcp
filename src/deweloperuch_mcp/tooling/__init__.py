"""Tooling of the CLI that is not about the service: the agent skill installer.

Apart from the business layers (``api``, ``models``, ``usecases``, ``consumers``,
``bootstrap``): it imports none of them, only the standard library, and only the CLI
(``consumers.cli``) uses it; the MCP server never does (import-linter, tests/architecture).
"""
