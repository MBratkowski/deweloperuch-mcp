"""Adapters of the domain's ports (D13): the service and the shared limiter's STOP record.

- ``deweloperuch``: the client of deweloperuch.pl (transport, JSON and RSC adapters,
  DTOs), the mapping of search criteria to its parameters and of its data to the domain,
  the links to its public pages, and the adapters of the ports over them.
- ``stop_record``: the STOP of the shared limiter (``deweloperuch_mcp.throttle``).

Infrastructure imports the domain, itself, the stdlib modules shared with ``recon/``
(``identity``, ``throttle``, ``http_policy``, ``retry_after``, ``allowlist``, ``flight``)
and third-party libraries; never the use cases nor the interfaces
(tests/test_layering.py).
"""
