"""Test infrastructure, no tests (tests/architecture/test_tests_layout.py checks it).

- ``fakes``: in-memory stand-ins of the use cases' ports and of the transport's seams;
- ``providers``: pytest fixtures (registered in tests/conftest.py), loaders of the real
  samples and fixtures, respx routes per resource, in-process MCP and CLI runners;
- ``builders``: test data per capability: payloads derived from real rows of the samples
  (copies, never values made up), and the domain objects and expected texts several test
  modules share;
- ``checks``: shared assertions (goldens, leaks, layering, locks);
- ``golden``: the golden matrices (``cli_cases``, ``mcp_cases``: one module per
  operation), how a case runs and is checked;
- ``e2e``: the harness of the live suite (tests/e2e);
- ``workers``: scripts the tests start as subprocesses.
"""
