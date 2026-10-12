"""deweloperuch.pl: HTTP transport, JSON and RSC adapters, DTOs (D1, D2), and the adapters
of the domain's ports over them (D13).

- ``transport``: one GET per call under the D2 policy, the cache and the STOP latch;
- ``json_api``, ``rsc``: one function per endpoint or page, returning DTOs (``dto``);
- ``params``: offer search criteria -> the page's query;
- ``mappers``: DTOs -> the domain;
- ``links``: the ``PageLinks`` port;
- ``locations``, ``offers``, ``statistics``: the other ports.

Backend names (``invest``, ``sale``, ``filterPrice``, prop names) stay in this package.
"""
