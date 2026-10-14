"""Use cases (D13, D16, D17): one module per operation, named after it
(``search_offers.SearchOffers``), with its ``*Request`` (``parse``: the argument contract
shared by the CLI and the MCP server) and its ``*Result``; the ports they depend on
(``ports``); ``support/``: the wording of refused arguments (``arguments``) and of the
service's failures (``failures.ReportedAs``).

They take the models' values, call the ports, apply the models' rules and say in the
models' terms what a failure of the service is about. They know neither the service nor
its backend names; links to public pages come through the ``PageLinks`` port. Imports:
``models``, ``usecases`` and the standard library only (tests/architecture/test_layering.py).
"""
